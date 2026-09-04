"""Integration tests for hive management endpoints, authorization, and validation."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.main import app
from app.models.enums import HiveStatus, UserRole
from app.models.hive import Hive
from app.models.identity import User

TEST_EMAIL_PREFIX = "hive-test-user-"
TEST_HIVE_PREFIX = "HIVE-TEST-"


@pytest.fixture
def session() -> Session:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as database_session:
        database_session.execute(delete(Hive).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%")))
        database_session.execute(delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%")))
        database_session.commit()
        try:
            yield database_session
        finally:
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


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_requests_are_rejected() -> None:
    client = TestClient(app)
    fake_id = uuid4()

    assert client.post("/hives", json={"hive_code": f"{TEST_HIVE_PREFIX}01", "location_region": "North"}).status_code == 401
    assert client.get("/hives").status_code == 401
    assert client.get(f"/hives/{fake_id}").status_code == 401
    assert client.patch(f"/hives/{fake_id}", json={"location_region": "South"}).status_code == 401


def test_authenticated_admin_can_create_hive(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin1@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper1@example.test", role=UserRole.BEEKEEPER)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(admin),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}ADM-01",
            "location_region": "Kashmir Valley",
            "beekeeper_id": str(beekeeper.id),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["hive_code"] == f"{TEST_HIVE_PREFIX}ADM-01"
    assert data["location_region"] == "Kashmir Valley"
    assert data["beekeeper_id"] == str(beekeeper.id)
    assert data["status"] == HiveStatus.ACTIVE.value
    assert data["is_active"] is True
    assert data["beekeeper"]["id"] == str(beekeeper.id)
    assert data["beekeeper"]["email"] == beekeeper.email


def test_admin_creation_without_beekeeper_id_is_rejected(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-no-bk@example.test", role=UserRole.ADMIN)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(admin),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}ADM-NO-BK",
            "location_region": "Himachal Hills",
        },
    )

    assert response.status_code == 422
    assert "beekeeper_id" in response.json()["detail"]


def test_admin_creation_with_non_existent_or_inactive_beekeeper_rejected_with_404(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-bk-404@example.test", role=UserRole.ADMIN)
    inactive_bk = _create_user(
        session,
        email=f"{TEST_EMAIL_PREFIX}inactive-bk@example.test",
        role=UserRole.BEEKEEPER,
        is_active=False,
    )

    client = TestClient(app)

    # Non-existent user
    res1 = client.post(
        "/hives",
        headers=_auth_headers(admin),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}ADM-NOTFOUND",
            "location_region": "Valley",
            "beekeeper_id": str(uuid4()),
        },
    )
    assert res1.status_code == 404
    assert res1.json()["detail"] == "Assigned beekeeper not found or inactive"

    # Inactive user
    res2 = client.post(
        "/hives",
        headers=_auth_headers(admin),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}ADM-INACTIVE",
            "location_region": "Valley",
            "beekeeper_id": str(inactive_bk.id),
        },
    )
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Assigned beekeeper not found or inactive"


def test_admin_creation_with_non_beekeeper_role_rejected_with_422(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-role-chk@example.test", role=UserRole.ADMIN)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-role-chk@example.test", role=UserRole.PROCESSOR)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(admin),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}ADM-BAD-ROLE",
            "location_region": "Valley",
            "beekeeper_id": str(processor.id),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Assigned user must have the BEEKEEPER role"


def test_authenticated_beekeeper_can_create_own_hive(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper2@example.test", role=UserRole.BEEKEEPER)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}BEE-01",
            "location_region": "Nilgiri Forests",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["hive_code"] == f"{TEST_HIVE_PREFIX}BEE-01"
    assert data["location_region"] == "Nilgiri Forests"
    assert data["beekeeper_id"] == str(beekeeper.id)
    assert data["status"] == HiveStatus.ACTIVE.value
    assert data["is_active"] is True


def test_beekeeper_cannot_assign_hive_to_another_user(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper3@example.test", role=UserRole.BEEKEEPER)
    other_user = _create_user(session, email=f"{TEST_EMAIL_PREFIX}other@example.test", role=UserRole.BEEKEEPER)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}BEE-FORBIDDEN",
            "location_region": "Deodar Woods",
            "beekeeper_id": str(other_user.id),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot assign hive to another user"


def test_processor_cannot_create_a_hive(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}processor1@example.test", role=UserRole.PROCESSOR)

    client = TestClient(app)
    response = client.post(
        "/hives",
        headers=_auth_headers(processor),
        json={
            "hive_code": f"{TEST_HIVE_PREFIX}PROC-01",
            "location_region": "Punjab Plains",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_duplicate_hive_code_is_rejected_cleanly(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper4@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)

    first = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_code": f"{TEST_HIVE_PREFIX}DUP-01", "location_region": "Sundarbans"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_code": f"{TEST_HIVE_PREFIX}DUP-01", "location_region": "Sundarbans West"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == f"Hive with code '{TEST_HIVE_PREFIX}DUP-01' already exists"


def test_beekeeper_cannot_view_another_beekeepers_hive(session: Session) -> None:
    beekeeper_a = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper-a@example.test", role=UserRole.BEEKEEPER)
    beekeeper_b = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper-b@example.test", role=UserRole.BEEKEEPER)

    client = TestClient(app)
    created = client.post(
        "/hives",
        headers=_auth_headers(beekeeper_a),
        json={"hive_code": f"{TEST_HIVE_PREFIX}OWNER-A", "location_region": "Region A"},
    )
    hive_id = created.json()["id"]

    response = client.get(f"/hives/{hive_id}", headers=_auth_headers(beekeeper_b))
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_admin_can_view_another_beekeepers_hive(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper5@example.test", role=UserRole.BEEKEEPER)
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin2@example.test", role=UserRole.ADMIN)

    client = TestClient(app)
    created = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_code": f"{TEST_HIVE_PREFIX}ADMIN-VIEW", "location_region": "Western Ghats"},
    )
    hive_id = created.json()["id"]

    response = client.get(f"/hives/{hive_id}", headers=_auth_headers(admin))
    assert response.status_code == 200
    assert response.json()["id"] == hive_id
    assert response.json()["hive_code"] == f"{TEST_HIVE_PREFIX}ADMIN-VIEW"


def test_list_filtering_and_ownership_behavior(session: Session) -> None:
    beekeeper_1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1@example.test", role=UserRole.BEEKEEPER)
    beekeeper_2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk2@example.test", role=UserRole.BEEKEEPER)
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-list@example.test", role=UserRole.ADMIN)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-list@example.test", role=UserRole.PROCESSOR)

    client = TestClient(app)
    c1 = client.post(
        "/hives",
        headers=_auth_headers(beekeeper_1),
        json={"hive_code": f"{TEST_HIVE_PREFIX}LIST-1", "location_region": "Zone 1"},
    )
    c2 = client.post(
        "/hives",
        headers=_auth_headers(beekeeper_2),
        json={"hive_code": f"{TEST_HIVE_PREFIX}LIST-2", "location_region": "Zone 2"},
    )
    assert c1.status_code == 201 and c2.status_code == 201

    # Beekeeper 1 sees only own hives
    bk1_res = client.get("/hives", headers=_auth_headers(beekeeper_1))
    assert bk1_res.status_code == 200
    bk1_codes = [h["hive_code"] for h in bk1_res.json()]
    assert f"{TEST_HIVE_PREFIX}LIST-1" in bk1_codes
    assert f"{TEST_HIVE_PREFIX}LIST-2" not in bk1_codes

    # Beekeeper 2 sees only own hives
    bk2_res = client.get("/hives", headers=_auth_headers(beekeeper_2))
    assert bk2_res.status_code == 200
    bk2_codes = [h["hive_code"] for h in bk2_res.json()]
    assert f"{TEST_HIVE_PREFIX}LIST-1" not in bk2_codes
    assert f"{TEST_HIVE_PREFIX}LIST-2" in bk2_codes

    # Admin sees all hives
    admin_res = client.get("/hives", headers=_auth_headers(admin))
    assert admin_res.status_code == 200
    admin_codes = [h["hive_code"] for h in admin_res.json()]
    assert f"{TEST_HIVE_PREFIX}LIST-1" in admin_codes
    assert f"{TEST_HIVE_PREFIX}LIST-2" in admin_codes

    # Processor sees all hives (for traceability)
    proc_res = client.get("/hives", headers=_auth_headers(processor))
    assert proc_res.status_code == 200
    proc_codes = [h["hive_code"] for h in proc_res.json()]
    assert f"{TEST_HIVE_PREFIX}LIST-1" in proc_codes
    assert f"{TEST_HIVE_PREFIX}LIST-2" in proc_codes


def test_single_hive_404_works(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin-404@example.test", role=UserRole.ADMIN)
    client = TestClient(app)

    response = client.get(f"/hives/{uuid4()}", headers=_auth_headers(admin))
    assert response.status_code == 404
    assert response.json()["detail"] == "Hive not found"


def test_authorized_hive_update_works(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper-up@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)

    created = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_code": f"{TEST_HIVE_PREFIX}UPDATE-01", "location_region": "Original Region"},
    )
    hive_id = created.json()["id"]

    # Beekeeper updates location_region and status to MAINTENANCE
    patch_res = client.patch(
        f"/hives/{hive_id}",
        headers=_auth_headers(beekeeper),
        json={"location_region": "Updated Region", "status": HiveStatus.MAINTENANCE.value},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["location_region"] == "Updated Region"
    assert data["status"] == HiveStatus.MAINTENANCE.value
    assert data["is_active"] is True


def test_unauthorized_hive_update_is_rejected(session: Session) -> None:
    owner = _create_user(session, email=f"{TEST_EMAIL_PREFIX}owner@example.test", role=UserRole.BEEKEEPER)
    other_bk = _create_user(session, email=f"{TEST_EMAIL_PREFIX}intruder@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc-up@example.test", role=UserRole.PROCESSOR)

    client = TestClient(app)
    created = client.post(
        "/hives",
        headers=_auth_headers(owner),
        json={"hive_code": f"{TEST_HIVE_PREFIX}UPDATE-SEC", "location_region": "Owner Grove"},
    )
    hive_id = created.json()["id"]

    # Other beekeeper rejected with 403
    other_res = client.patch(
        f"/hives/{hive_id}",
        headers=_auth_headers(other_bk),
        json={"location_region": "Tampered Region"},
    )
    assert other_res.status_code == 403
    assert other_res.json()["detail"] == "Insufficient permissions"

    # Processor rejected with 403
    proc_res = client.patch(
        f"/hives/{hive_id}",
        headers=_auth_headers(processor),
        json={"location_region": "Processor Tamper"},
    )
    assert proc_res.status_code == 403
    assert proc_res.json()["detail"] == "Insufficient permissions"


def test_hive_deactivation_and_reactivation_works(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}beekeeper-cycle@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)

    created = client.post(
        "/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_code": f"{TEST_HIVE_PREFIX}DEACT-01", "location_region": "Highland Orchard"},
    )
    hive_id = created.json()["id"]
    assert created.json()["is_active"] is True
    assert created.json()["status"] == HiveStatus.ACTIVE.value

    # Deactivate hive
    deact_res = client.patch(
        f"/hives/{hive_id}",
        headers=_auth_headers(beekeeper),
        json={"is_active": False, "status": HiveStatus.INACTIVE.value},
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False
    assert deact_res.json()["status"] == HiveStatus.INACTIVE.value

    # Reactivate hive
    react_res = client.patch(
        f"/hives/{hive_id}",
        headers=_auth_headers(beekeeper),
        json={"is_active": True, "status": HiveStatus.ACTIVE.value},
    )
    assert react_res.status_code == 200
    assert react_res.json()["is_active"] is True
    assert react_res.json()["status"] == HiveStatus.ACTIVE.value


def test_password_hash_is_never_exposed_in_hive_responses(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-leakcheck@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    create_res = client.post(
        "/hives",
        headers=headers,
        json={"hive_code": f"{TEST_HIVE_PREFIX}LEAK-01", "location_region": "Safe Zone"},
    )
    assert create_res.status_code == 201
    assert "password_hash" not in create_res.text
    hive_id = create_res.json()["id"]

    list_res = client.get("/hives", headers=headers)
    assert list_res.status_code == 200
    assert "password_hash" not in list_res.text

    get_res = client.get(f"/hives/{hive_id}", headers=headers)
    assert get_res.status_code == 200
    assert "password_hash" not in get_res.text

    patch_res = client.patch(f"/hives/{hive_id}", headers=headers, json={"location_region": "New Safe Zone"})
    assert patch_res.status_code == 200
    assert "password_hash" not in patch_res.text


def test_invalid_payloads_rejected_with_422(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-val@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)
    headers = _auth_headers(beekeeper)

    # Empty hive_code
    res1 = client.post("/hives", headers=headers, json={"hive_code": "   ", "location_region": "Valid"})
    assert res1.status_code == 422

    # Empty location_region
    res2 = client.post("/hives", headers=headers, json={"hive_code": f"{TEST_HIVE_PREFIX}VAL-1", "location_region": ""})
    assert res2.status_code == 422

    # Forbidden fields on update (e.g. attempting to change hive_code)
    created = client.post("/hives", headers=headers, json={"hive_code": f"{TEST_HIVE_PREFIX}VAL-2", "location_region": "East"})
    hive_id = created.json()["id"]
    res3 = client.patch(f"/hives/{hive_id}", headers=headers, json={"hive_code": "NEW-CODE"})
    assert res3.status_code == 422
