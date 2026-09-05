"""Integration tests for risk evaluation, anomaly detection, authorization, and isolation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.main import app
from app.models.enums import BatchStatus, HiveStatus, RiskLevel, RiskSource, TelemetryQuality, UserRole
from app.models.evidence import BlockchainRecord
from app.models.hive import Hive, RiskEvent, Telemetry
from app.models.identity import User
from app.models.traceability import Batch

TEST_EMAIL_PREFIX = "risk-test-user-"
TEST_HIVE_PREFIX = "RISK-HIVE-"


@pytest.fixture
def session() -> Session:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as database_session:
        _cleanup(database_session)
        try:
            yield database_session
        finally:
            _cleanup(database_session)


def _cleanup(database_session: Session) -> None:
    target_hive_ids = select(Hive.id).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%"))
    database_session.execute(delete(RiskEvent).where(RiskEvent.hive_id.in_(target_hive_ids)))
    database_session.execute(delete(Telemetry).where(Telemetry.hive_id.in_(target_hive_ids)))
    database_session.execute(delete(Hive).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%")))
    database_session.execute(delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%")))
    database_session.commit()


def _create_user(
    session: Session,
    *,
    email: str,
    role: UserRole,
    name: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        name=name or f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("secure-test-pass"),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_hive(
    session: Session,
    *,
    hive_code: str,
    beekeeper: User,
    location_region: str = "Test Apiary",
) -> Hive:
    hive = Hive(
        hive_code=hive_code,
        beekeeper_id=beekeeper.id,
        location_region=location_region,
        status=HiveStatus.ACTIVE,
        is_active=True,
    )
    session.add(hive)
    session.commit()
    session.refresh(hive)
    return hive


def _create_telemetry(
    session: Session,
    *,
    hive: Hive,
    weight_kg: float = 25.0,
    temperature_c: float = 34.0,
    humidity_pct: float = 55.0,
    quality: TelemetryQuality = TelemetryQuality.VALID,
    device_timestamp: datetime | None = None,
) -> Telemetry:
    telemetry = Telemetry(
        hive_id=hive.id,
        device_timestamp=device_timestamp or datetime.now(UTC),
        received_at=datetime.now(UTC),
        weight_kg=weight_kg,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        quality=quality,
    )
    session.add(telemetry)
    session.commit()
    session.refresh(telemetry)
    return telemetry


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# AUTHORIZATION TESTS
# ==============================================================================


def test_unauthenticated_requests_are_rejected() -> None:
    client = TestClient(app)
    fake_id = uuid4()

    assert client.post(f"/hives/{fake_id}/risk/evaluate", json={}).status_code == 401
    assert client.get(f"/hives/{fake_id}/risk").status_code == 401
    assert client.get(f"/risk/{fake_id}").status_code == 401


def test_admin_can_evaluate_and_read_risk_for_all_hives(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}ADM-01", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive, temperature_c=34.0, humidity_pct=55.0, weight_kg=25.0)

    client = TestClient(app)

    # Admin evaluates risk
    eval_res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(admin),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_res.status_code == 201
    data = eval_res.json()
    assert data["hive_id"] == str(hive.id)
    assert data["telemetry_id"] == str(telem.id)
    assert data["risk_level"] == RiskLevel.LOW.value
    event_id = data["id"]

    # Admin reads hive risk list
    list_res = client.get(f"/hives/{hive.id}/risk", headers=_auth_headers(admin))
    assert list_res.status_code == 200
    assert any(e["id"] == event_id for e in list_res.json())

    # Admin reads single risk event
    get_res = client.get(f"/risk/{event_id}", headers=_auth_headers(admin))
    assert get_res.status_code == 200
    assert get_res.json()["id"] == event_id


def test_beekeeper_can_evaluate_and_read_own_hive_risk(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-own@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}OWN-01", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive, temperature_c=41.5, humidity_pct=90.0, weight_kg=8.5)

    client = TestClient(app)

    # Beekeeper evaluates own hive
    eval_res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_res.status_code == 201
    data = eval_res.json()
    assert data["risk_level"] == RiskLevel.HIGH.value
    assert data["risk_score"] >= 0.70
    event_id = data["id"]

    # Beekeeper reads own risk events
    list_res = client.get(f"/hives/{hive.id}/risk", headers=_auth_headers(beekeeper))
    assert list_res.status_code == 200
    assert any(e["id"] == event_id for e in list_res.json())


def test_beekeeper_cannot_access_another_beekeepers_hive_risk(session: Session) -> None:
    owner = _create_user(session, email=f"{TEST_EMAIL_PREFIX}owner@example.test", role=UserRole.BEEKEEPER)
    intruder = _create_user(session, email=f"{TEST_EMAIL_PREFIX}intruder@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}ISO-01", beekeeper=owner)
    telem = _create_telemetry(session, hive=hive)

    client = TestClient(app)

    # Owner evaluates risk first
    eval_res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(owner),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_res.status_code == 201
    event_id = eval_res.json()["id"]

    # Intruder tries to evaluate owner's hive -> 403
    eval_fail = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(intruder),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_fail.status_code == 403
    assert eval_fail.json()["detail"] == "Insufficient permissions"

    # Intruder tries to list owner's hive risk events -> 403
    list_fail = client.get(f"/hives/{hive.id}/risk", headers=_auth_headers(intruder))
    assert list_fail.status_code == 403
    assert list_fail.json()["detail"] == "Insufficient permissions"

    # Intruder tries to get owner's single risk event -> 403
    get_fail = client.get(f"/risk/{event_id}", headers=_auth_headers(intruder))
    assert get_fail.status_code == 403
    assert get_fail.json()["detail"] == "Insufficient permissions"


def test_processor_cannot_evaluate_risk_but_can_read_risk(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc@example.test", role=UserRole.PROCESSOR)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-proc@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}PROC-01", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive)

    client = TestClient(app)

    # Beekeeper evaluates
    eval_res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_res.status_code == 201
    event_id = eval_res.json()["id"]

    # Processor attempts to evaluate -> 403
    eval_fail = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(processor),
        json={"telemetry_id": str(telem.id)},
    )
    assert eval_fail.status_code == 403
    assert eval_fail.json()["detail"] == "Insufficient permissions"

    # Processor reads hive risk events -> 200
    list_ok = client.get(f"/hives/{hive.id}/risk", headers=_auth_headers(processor))
    assert list_ok.status_code == 200
    assert any(e["id"] == event_id for e in list_ok.json())

    # Processor reads single risk event -> 200
    get_ok = client.get(f"/risk/{event_id}", headers=_auth_headers(processor))
    assert get_ok.status_code == 200
    assert get_ok.json()["id"] == event_id


# ==============================================================================
# VALIDATION TESTS
# ==============================================================================


def test_nonexistent_hive_handled_correctly(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-404@example.test", role=UserRole.ADMIN)
    client = TestClient(app)
    non_existent = uuid4()

    res1 = client.post(f"/hives/{non_existent}/risk/evaluate", headers=_auth_headers(admin), json={})
    assert res1.status_code == 404
    assert res1.json()["detail"] == "Hive not found"

    res2 = client.get(f"/hives/{non_existent}/risk", headers=_auth_headers(admin))
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Hive not found"


def test_nonexistent_telemetry_handled_correctly(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-notel@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}NO-TEL", beekeeper=beekeeper)
    non_existent_telem = uuid4()

    client = TestClient(app)

    # Telemetry specified explicitly does not exist
    res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(non_existent_telem)},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Telemetry record not found"


def test_telemetry_belonging_to_another_hive_rejected_with_422(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-mismatch@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-mismatch@example.test", role=UserRole.BEEKEEPER)
    hive_a = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}HIVE-A", beekeeper=beekeeper)
    hive_b = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}HIVE-B", beekeeper=beekeeper)
    telem_b = _create_telemetry(session, hive=hive_b)

    client = TestClient(app)

    # Evaluating hive_a with telemetry belonging to hive_b
    res = client.post(
        f"/hives/{hive_a.id}/risk/evaluate",
        headers=_auth_headers(admin),
        json={"telemetry_id": str(telem_b.id)},
    )
    assert res.status_code == 422
    assert "does not belong" in res.json()["detail"]


def test_invalid_telemetry_quality_is_rejected_from_evaluation(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-badq@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}BAD-Q", beekeeper=beekeeper)
    invalid_telem = _create_telemetry(session, hive=hive, quality=TelemetryQuality.INVALID)

    client = TestClient(app)

    res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(invalid_telem.id)},
    )
    assert res.status_code == 422
    assert "INVALID quality" in res.json()["detail"]


# ==============================================================================
# BEHAVIOR & INTEGRITY TESTS
# ==============================================================================


def test_deterministic_rule_evaluation_and_score_mapping(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-determ@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}DETERM", beekeeper=beekeeper)

    # 1. Nominal telemetry -> LOW risk
    t_low = _create_telemetry(session, hive=hive, temperature_c=34.0, humidity_pct=60.0, weight_kg=25.0)
    # 2. Moderate anomalies -> MEDIUM risk
    t_med = _create_telemetry(session, hive=hive, temperature_c=37.0, humidity_pct=78.0, weight_kg=14.0)
    # 3. Critical anomalies -> HIGH risk
    t_high = _create_telemetry(session, hive=hive, temperature_c=42.0, humidity_pct=90.0, weight_kg=8.0)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    res_low = client.post(f"/hives/{hive.id}/risk/evaluate", headers=headers, json={"telemetry_id": str(t_low.id)})
    assert res_low.status_code == 201
    d_low = res_low.json()
    assert d_low["risk_level"] == RiskLevel.LOW.value
    assert 0.0 <= d_low["risk_score"] < 0.40
    assert d_low["source"] == RiskSource.RULE_ENGINE.value
    assert d_low["model_name"] == "prototype-anomaly-rules"
    assert d_low["model_version"] == "1.0.0"

    res_med = client.post(f"/hives/{hive.id}/risk/evaluate", headers=headers, json={"telemetry_id": str(t_med.id)})
    assert res_med.status_code == 201
    d_med = res_med.json()
    assert d_med["risk_level"] == RiskLevel.MEDIUM.value
    assert 0.40 <= d_med["risk_score"] < 0.70

    res_high = client.post(f"/hives/{hive.id}/risk/evaluate", headers=headers, json={"telemetry_id": str(t_high.id)})
    assert res_high.status_code == 201
    d_high = res_high.json()
    assert d_high["risk_level"] == RiskLevel.HIGH.value
    assert 0.70 <= d_high["risk_score"] <= 1.0


def test_suspect_telemetry_adds_penalty_modifier(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-susp@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}SUSP", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive, temperature_c=34.0, humidity_pct=60.0, weight_kg=25.0, quality=TelemetryQuality.SUSPECT)

    client = TestClient(app)
    res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(telem.id)},
    )
    assert res.status_code == 201
    data = res.json()
    assert "SUSPECT" in data["reason"]
    assert data["risk_score"] > 0.05  # Base score 0.05 + 0.10 modifier


def test_evaluation_without_telemetry_id_picks_latest_usable_telemetry(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-latest@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}LATEST", beekeeper=beekeeper)

    t1 = _create_telemetry(session, hive=hive, temperature_c=34.0, device_timestamp=datetime(2026, 9, 1, 10, 0, tzinfo=UTC))
    t2 = _create_telemetry(session, hive=hive, temperature_c=42.0, humidity_pct=90.0, device_timestamp=datetime(2026, 9, 2, 10, 0, tzinfo=UTC))  # Latest

    client = TestClient(app)
    res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={},
    )
    assert res.status_code == 201
    assert res.json()["telemetry_id"] == str(t2.id)
    assert res.json()["risk_level"] == RiskLevel.HIGH.value


def test_ai_risk_does_not_mutate_batch_status_or_create_blockchain_records(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-nomut@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-nomut@example.test", role=UserRole.PROCESSOR)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}NOMUT", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive, temperature_c=45.0, humidity_pct=95.0, weight_kg=5.0)

    # Create an active batch to ensure it is untouched
    batch = Batch(
        batch_code="BATCH-TEST-NOMUT-01",
        processor_id=processor.id,
        status=BatchStatus.ACTIVE,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    client = TestClient(app)

    # Perform critical risk evaluation
    res = client.post(
        f"/hives/{hive.id}/risk/evaluate",
        headers=_auth_headers(beekeeper),
        json={"telemetry_id": str(telem.id)},
    )
    assert res.status_code == 201
    assert res.json()["risk_level"] == RiskLevel.HIGH.value

    # Verify Batch remains ACTIVE (not HOLD or RECALL)
    session.expire_all()
    reloaded_batch = session.get(Batch, batch.id)
    assert reloaded_batch is not None
    assert reloaded_batch.status == BatchStatus.ACTIVE

    # Verify zero blockchain records were created
    bc_count = session.scalar(select(func.count()).select_from(BlockchainRecord))
    assert bc_count == 0

    # Verify telemetry was NOT modified
    reloaded_telem = session.get(Telemetry, telem.id)
    assert reloaded_telem is not None
    assert float(reloaded_telem.temperature_c) == 45.0

    # Cleanup batch created in this test
    session.delete(batch)
    session.commit()


def test_multiple_evaluations_create_separate_riskevent_records(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-multi@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}MULTI", beekeeper=beekeeper)
    telem = _create_telemetry(session, hive=hive)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    res1 = client.post(f"/hives/{hive.id}/risk/evaluate", headers=headers, json={"telemetry_id": str(telem.id)})
    res2 = client.post(f"/hives/{hive.id}/risk/evaluate", headers=headers, json={"telemetry_id": str(telem.id)})

    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]

    events = client.get(f"/hives/{hive.id}/risk", headers=headers).json()
    assert len(events) == 2
