"""Integration tests for telemetry ingestion, querying, validation, and role authorization."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.main import app
from app.models.enums import HiveStatus, TelemetryQuality, UserRole
from app.models.hive import Hive, Telemetry
from app.models.identity import User

TEST_EMAIL_PREFIX = "telem-test-user-"
TEST_HIVE_PREFIX = "TELEM-HIVE-"


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
    location_region: str = "Test Valley",
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


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# AUTHORIZATION TESTS
# ==============================================================================


def test_unauthenticated_requests_are_rejected() -> None:
    client = TestClient(app)
    fake_id = uuid4()
    dummy_payload = {
        "device_timestamp": datetime.now(UTC).isoformat(),
        "weight_kg": 25.5,
        "temperature_c": 34.0,
        "humidity_pct": 55.0,
        "quality": "VALID",
    }

    assert client.post("/telemetry", json={"hive_id": str(fake_id), **dummy_payload}).status_code == 401
    assert client.get("/telemetry").status_code == 401
    assert client.get(f"/telemetry/{fake_id}").status_code == 401
    assert client.post(f"/hives/{fake_id}/telemetry", json=dummy_payload).status_code == 401
    assert client.get(f"/hives/{fake_id}/telemetry").status_code == 401


def test_admin_can_submit_and_read_telemetry(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}ADM-01", beekeeper=beekeeper)

    client = TestClient(app)
    device_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)

    # Admin submits via POST /telemetry
    response = client.post(
        "/telemetry",
        headers=_auth_headers(admin),
        json={
            "hive_id": str(hive.id),
            "device_timestamp": device_time.isoformat(),
            "weight_kg": 28.5,
            "temperature_c": 35.2,
            "humidity_pct": 52.0,
            "quality": "VALID",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["hive_id"] == str(hive.id)
    assert data["weight_kg"] == 28.5
    assert data["quality"] == "VALID"
    telem_id = data["id"]

    # Admin reads via GET /telemetry
    list_res = client.get("/telemetry", headers=_auth_headers(admin))
    assert list_res.status_code == 200
    ids = [item["id"] for item in list_res.json()]
    assert telem_id in ids

    # Admin reads via GET /hives/{hive_id}/telemetry
    hive_telem_res = client.get(f"/hives/{hive.id}/telemetry", headers=_auth_headers(admin))
    assert hive_telem_res.status_code == 200
    assert any(item["id"] == telem_id for item in hive_telem_res.json())

    # Admin reads single record
    single_res = client.get(f"/telemetry/{telem_id}", headers=_auth_headers(admin))
    assert single_res.status_code == 200
    assert single_res.json()["id"] == telem_id


def test_beekeeper_can_submit_and_read_own_hive_telemetry(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-own@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}OWN-01", beekeeper=beekeeper)

    client = TestClient(app)
    device_time = datetime(2026, 9, 4, 14, 30, 0, tzinfo=UTC)

    # Submit via POST /hives/{hive_id}/telemetry
    submit_res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": device_time.isoformat(),
            "weight_kg": 30.0,
            "temperature_c": 34.5,
            "humidity_pct": 60.0,
            "quality": "VALID",
        },
    )
    assert submit_res.status_code == 201
    data = submit_res.json()
    telem_id = data["id"]
    assert data["hive_id"] == str(hive.id)

    # Read via GET /hives/{hive_id}/telemetry
    get_res = client.get(f"/hives/{hive.id}/telemetry", headers=_auth_headers(beekeeper))
    assert get_res.status_code == 200
    assert len(get_res.json()) == 1
    assert get_res.json()[0]["id"] == telem_id

    # Read via GET /telemetry
    list_res = client.get("/telemetry", headers=_auth_headers(beekeeper))
    assert list_res.status_code == 200
    assert any(item["id"] == telem_id for item in list_res.json())


def test_beekeeper_cannot_submit_telemetry_to_another_beekeepers_hive(session: Session) -> None:
    owner = _create_user(session, email=f"{TEST_EMAIL_PREFIX}owner@example.test", role=UserRole.BEEKEEPER)
    intruder = _create_user(session, email=f"{TEST_EMAIL_PREFIX}intruder@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}INT-01", beekeeper=owner)

    client = TestClient(app)
    payload = {
        "device_timestamp": datetime.now(UTC).isoformat(),
        "weight_kg": 20.0,
        "temperature_c": 33.0,
        "humidity_pct": 50.0,
        "quality": "VALID",
    }

    # Attempt via POST /telemetry
    res1 = client.post(
        "/telemetry",
        headers=_auth_headers(intruder),
        json={"hive_id": str(hive.id), **payload},
    )
    assert res1.status_code == 403
    assert res1.json()["detail"] == "Insufficient permissions"

    # Attempt via POST /hives/{hive_id}/telemetry
    res2 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(intruder),
        json=payload,
    )
    assert res2.status_code == 403
    assert res2.json()["detail"] == "Insufficient permissions"


def test_beekeeper_cannot_read_another_beekeepers_hive_telemetry(session: Session) -> None:
    owner = _create_user(session, email=f"{TEST_EMAIL_PREFIX}owner-r@example.test", role=UserRole.BEEKEEPER)
    intruder = _create_user(session, email=f"{TEST_EMAIL_PREFIX}intruder-r@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}READ-01", beekeeper=owner)

    client = TestClient(app)
    submit_res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(owner),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 22.0,
            "temperature_c": 32.0,
            "humidity_pct": 55.0,
            "quality": "VALID",
        },
    )
    assert submit_res.status_code == 201
    telem_id = submit_res.json()["id"]

    # Intruder tries GET /hives/{hive_id}/telemetry -> 403
    res1 = client.get(f"/hives/{hive.id}/telemetry", headers=_auth_headers(intruder))
    assert res1.status_code == 403
    assert res1.json()["detail"] == "Insufficient permissions"

    # Intruder tries GET /telemetry?hive_id={hive_id} -> 403
    res2 = client.get(f"/telemetry?hive_id={hive.id}", headers=_auth_headers(intruder))
    assert res2.status_code == 403
    assert res2.json()["detail"] == "Insufficient permissions"

    # Intruder tries GET /telemetry/{telemetry_id} -> 403
    res3 = client.get(f"/telemetry/{telem_id}", headers=_auth_headers(intruder))
    assert res3.status_code == 403
    assert res3.json()["detail"] == "Insufficient permissions"

    # Intruder calls GET /telemetry without filter -> must NOT leak owner's telemetry
    res4 = client.get("/telemetry", headers=_auth_headers(intruder))
    assert res4.status_code == 200
    returned_ids = [item["id"] for item in res4.json()]
    assert telem_id not in returned_ids


def test_processor_cannot_submit_telemetry(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-sub@example.test", role=UserRole.PROCESSOR)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-proc@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}PROC-01", beekeeper=beekeeper)

    client = TestClient(app)
    payload = {
        "device_timestamp": datetime.now(UTC).isoformat(),
        "weight_kg": 25.0,
        "temperature_c": 35.0,
        "humidity_pct": 50.0,
        "quality": "VALID",
    }

    res1 = client.post("/telemetry", headers=_auth_headers(processor), json={"hive_id": str(hive.id), **payload})
    assert res1.status_code == 403
    assert res1.json()["detail"] == "Insufficient permissions"

    res2 = client.post(f"/hives/{hive.id}/telemetry", headers=_auth_headers(processor), json=payload)
    assert res2.status_code == 403
    assert res2.json()["detail"] == "Insufficient permissions"


def test_processor_can_read_telemetry_across_all_hives(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-read@example.test", role=UserRole.PROCESSOR)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-read@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}PROC-R01", beekeeper=beekeeper)

    client = TestClient(app)
    submit_res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 27.5,
            "temperature_c": 33.5,
            "humidity_pct": 58.0,
            "quality": "VALID",
        },
    )
    assert submit_res.status_code == 201
    telem_id = submit_res.json()["id"]

    # Processor reads via /hives/{hive_id}/telemetry
    res1 = client.get(f"/hives/{hive.id}/telemetry", headers=_auth_headers(processor))
    assert res1.status_code == 200
    assert any(item["id"] == telem_id for item in res1.json())

    # Processor reads via /telemetry
    res2 = client.get("/telemetry", headers=_auth_headers(processor))
    assert res2.status_code == 200
    assert any(item["id"] == telem_id for item in res2.json())

    # Processor reads single record
    res3 = client.get(f"/telemetry/{telem_id}", headers=_auth_headers(processor))
    assert res3.status_code == 200
    assert res3.json()["id"] == telem_id


# ==============================================================================
# VALIDATION TESTS
# ==============================================================================


def test_negative_weight_rejected_with_422(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-neg-wt@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-NEG-WT", beekeeper=beekeeper)

    client = TestClient(app)
    res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": -1.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "VALID",
        },
    )
    assert res.status_code == 422


def test_humidity_out_of_bounds_rejected_with_422(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-hum@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-HUM", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    # Humidity < 0
    res1 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 20.0,
            "temperature_c": 35.0,
            "humidity_pct": -0.1,
            "quality": "VALID",
        },
    )
    assert res1.status_code == 422

    # Humidity > 100
    res2 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 20.0,
            "temperature_c": 35.0,
            "humidity_pct": 100.1,
            "quality": "VALID",
        },
    )
    assert res2.status_code == 422


def test_malformed_required_fields_rejected_with_422(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-malformed@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-MAL", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    # Missing weight_kg
    res1 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
        },
    )
    assert res1.status_code == 422

    # Non-numeric temperature
    res2 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 25.0,
            "temperature_c": "very-hot",
            "humidity_pct": 50.0,
        },
    )
    assert res2.status_code == 422

    # Malformed timestamp
    res3 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": "invalid-date",
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
        },
    )
    assert res3.status_code == 422


def test_timezoneless_timestamp_rejected_with_422_and_not_persisted(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-tzless@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-TZLESS", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    count_before = session.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.hive_id == hive.id))

    # Timezone-less ISO datetime string (no Z or offset)
    naive_timestamp_str = "2026-09-04T12:00:00"
    res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": naive_timestamp_str,
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "VALID",
        },
    )
    assert res.status_code == 422
    assert "timezone" in str(res.json()["detail"])

    count_after = session.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.hive_id == hive.id))
    assert count_after == count_before


def test_timezone_aware_timestamp_normalized_to_utc(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-tzaware@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-TZAWARE", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    # Timezone with +05:30 offset
    offset_timestamp_str = "2026-09-04T17:30:00+05:30"
    res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": offset_timestamp_str,
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "VALID",
        },
    )
    assert res.status_code == 201
    returned_dt = datetime.fromisoformat(res.json()["device_timestamp"])
    expected_utc = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)
    assert returned_dt == expected_utc


def test_invalid_hive_id_rejected_appropriately(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-404@example.test", role=UserRole.ADMIN)
    client = TestClient(app)
    non_existent = uuid4()

    # POST to non-existent hive
    res1 = client.post(
        f"/hives/{non_existent}/telemetry",
        headers=_auth_headers(admin),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "VALID",
        },
    )
    assert res1.status_code == 404
    assert res1.json()["detail"] == "Hive not found"

    # GET non-existent hive telemetry
    res2 = client.get(f"/hives/{non_existent}/telemetry", headers=_auth_headers(admin))
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Hive not found"

    # GET non-existent telemetry record
    res3 = client.get(f"/telemetry/{non_existent}", headers=_auth_headers(admin))
    assert res3.status_code == 404
    assert res3.json()["detail"] == "Telemetry record not found"


def test_invalid_input_is_not_persisted(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-nopres@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}VAL-PERSIST", beekeeper=beekeeper)

    client = TestClient(app)
    count_before = session.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.hive_id == hive.id))

    client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": -99.0,  # Invalid
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "VALID",
        },
    )

    count_after = session.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.hive_id == hive.id))
    assert count_after == count_before


# ==============================================================================
# BEHAVIOR & INTEGRITY TESTS
# ==============================================================================


def test_received_at_is_generated_by_backend_and_client_cannot_override(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-recv@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}RECV-01", beekeeper=beekeeper)

    client = TestClient(app)
    before = datetime.now(UTC)

    # Attempting to supply received_at should be rejected by extra="forbid"
    res1 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 32.0,
            "temperature_c": 34.0,
            "humidity_pct": 55.0,
            "received_at": datetime(2020, 1, 1, tzinfo=UTC).isoformat(),
        },
    )
    assert res1.status_code == 422

    # Valid submission generates received_at automatically
    res2 = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=_auth_headers(beekeeper),
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 32.0,
            "temperature_c": 34.0,
            "humidity_pct": 55.0,
        },
    )
    assert res2.status_code == 201
    data = res2.json()
    after = datetime.now(UTC)
    received_at = datetime.fromisoformat(data["received_at"])
    assert before <= received_at <= after


def test_quality_values_accepted_only_from_valid_suspect_invalid(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-qual@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}QUAL-01", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    for valid_qual in ("VALID", "SUSPECT", "INVALID"):
        res = client.post(
            f"/hives/{hive.id}/telemetry",
            headers=headers,
            json={
                "device_timestamp": datetime.now(UTC).isoformat(),
                "weight_kg": 25.0,
                "temperature_c": 35.0,
                "humidity_pct": 50.0,
                "quality": valid_qual,
            },
        )
        assert res.status_code == 201
        assert res.json()["quality"] == valid_qual

    # Invalid quality string
    res_bad = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
            "quality": "EXCELLENT",
        },
    )
    assert res_bad.status_code == 422


def test_append_only_behavior_and_no_update_or_delete_endpoint(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-append@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}APPEND-01", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    # Ingest 3 distinct records
    for i in range(3):
        res = client.post(
            f"/hives/{hive.id}/telemetry",
            headers=headers,
            json={
                "device_timestamp": datetime(2026, 9, 4, 10, i, 0, tzinfo=UTC).isoformat(),
                "weight_kg": 20.0 + i,
                "temperature_c": 34.0,
                "humidity_pct": 50.0,
            },
        )
        assert res.status_code == 201

    # Verify all 3 exist
    records_res = client.get(f"/hives/{hive.id}/telemetry", headers=headers)
    assert records_res.status_code == 200
    records = records_res.json()
    assert len(records) == 3
    telem_id = records[0]["id"]

    # Verify no PUT, PATCH, or DELETE route exists
    assert client.put(f"/telemetry/{telem_id}", headers=headers, json={"weight_kg": 99.0}).status_code in (404, 405)
    assert client.patch(f"/telemetry/{telem_id}", headers=headers, json={"weight_kg": 99.0}).status_code in (404, 405)
    assert client.delete(f"/telemetry/{telem_id}", headers=headers).status_code in (404, 405)
    assert client.put(f"/hives/{hive.id}/telemetry", headers=headers, json={}).status_code in (404, 405)
    assert client.delete(f"/hives/{hive.id}/telemetry", headers=headers).status_code in (404, 405)


def test_password_hash_never_exposed_in_telemetry_responses(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-sec@example.test", role=UserRole.BEEKEEPER)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}SEC-01", beekeeper=beekeeper)

    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    post_res = client.post(
        f"/hives/{hive.id}/telemetry",
        headers=headers,
        json={
            "device_timestamp": datetime.now(UTC).isoformat(),
            "weight_kg": 25.0,
            "temperature_c": 35.0,
            "humidity_pct": 50.0,
        },
    )
    assert post_res.status_code == 201
    assert "password_hash" not in post_res.text
    telem_id = post_res.json()["id"]

    list_res = client.get("/telemetry", headers=headers)
    assert "password_hash" not in list_res.text

    get_res = client.get(f"/telemetry/{telem_id}", headers=headers)
    assert "password_hash" not in get_res.text
