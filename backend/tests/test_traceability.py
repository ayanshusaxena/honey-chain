"""Comprehensive test suite for Honey Chain Harvest, Collection Lot, and Batch Traceability."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Generator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, HiveStatus, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, Hive, HiveHarvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest

TEST_EMAIL_PREFIX = "test-trc-"
TEST_HIVE_PREFIX = "TRC-HIV-"
TEST_HARVEST_PREFIX = "TRC-HRV-"
TEST_LOT_PREFIX = "TRC-LOT-"
TEST_BATCH_PREFIX = "TRC-BAT-"


def _cleanup(database_session: Session) -> None:
    batch_ids = database_session.scalars(
        select(Batch.id).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%"))
    ).all()
    lot_ids = database_session.scalars(
        select(CollectionLot.id).where(CollectionLot.lot_code.like(f"{TEST_LOT_PREFIX}%"))
    ).all()
    harvest_ids = database_session.scalars(
        select(Harvest.id).where(Harvest.harvest_code.like(f"{TEST_HARVEST_PREFIX}%"))
    ).all()
    hive_ids = database_session.scalars(
        select(Hive.id).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%"))
    ).all()
    user_ids = database_session.scalars(
        select(User.id).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))
    ).all()

    # Clean up child junction records first, scoped strictly to test-owned IDs
    if batch_ids:
        database_session.execute(
            delete(BatchCollectionLot).where(BatchCollectionLot.batch_id.in_(batch_ids))
        )
    if lot_ids:
        database_session.execute(
            delete(BatchCollectionLot).where(BatchCollectionLot.collection_lot_id.in_(lot_ids))
        )
        database_session.execute(
            delete(CollectionLotHarvest).where(CollectionLotHarvest.collection_lot_id.in_(lot_ids))
        )
    if harvest_ids:
        database_session.execute(
            delete(CollectionLotHarvest).where(CollectionLotHarvest.harvest_id.in_(harvest_ids))
        )
        database_session.execute(
            delete(HiveHarvest).where(HiveHarvest.harvest_id.in_(harvest_ids))
        )
    if hive_ids:
        database_session.execute(
            delete(HiveHarvest).where(HiveHarvest.hive_id.in_(hive_ids))
        )

    # Scoped AuditEvents
    audit_conditions = []
    if user_ids:
        audit_conditions.append(AuditEvent.actor_user_id.in_(user_ids))
    entity_ids = set(batch_ids) | set(lot_ids) | set(harvest_ids) | set(hive_ids)
    if entity_ids:
        audit_conditions.append(AuditEvent.entity_id.in_(list(entity_ids)))
    if audit_conditions:
        database_session.execute(delete(AuditEvent).where(or_(*audit_conditions)))

    # Clean up primary entities
    if batch_ids:
        database_session.execute(delete(Batch).where(Batch.id.in_(batch_ids)))
    if lot_ids:
        database_session.execute(delete(CollectionLot).where(CollectionLot.id.in_(lot_ids)))
    if harvest_ids:
        database_session.execute(delete(Harvest).where(Harvest.id.in_(harvest_ids)))
    if hive_ids:
        database_session.execute(delete(Hive).where(Hive.id.in_(hive_ids)))
    if user_ids:
        database_session.execute(delete(User).where(User.id.in_(user_ids)))
    database_session.commit()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as database_session:
        _cleanup(database_session)
        try:
            yield database_session
        finally:
            _cleanup(database_session)


# ===========================================================================
# Helper Factories
# ===========================================================================

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
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _create_hive(
    session: Session,
    *,
    hive_code: str,
    beekeeper: User,
    location_region: str = "Pampore Valley",
    is_active: bool = True,
) -> Hive:
    hive = Hive(
        hive_code=hive_code,
        beekeeper_id=beekeeper.id,
        location_region=location_region,
        status=HiveStatus.ACTIVE,
        is_active=is_active,
    )
    session.add(hive)
    session.commit()
    session.refresh(hive)
    return hive


# ===========================================================================
# Authorization Tests
# ===========================================================================

def test_unauthenticated_requests_are_rejected() -> None:
    client = TestClient(app)
    fake_id = uuid4()

    assert client.post("/harvests", json={}).status_code == 401
    assert client.get("/harvests").status_code == 401
    assert client.get(f"/harvests/{fake_id}").status_code == 401
    assert client.post(f"/harvests/{fake_id}/hives", json={}).status_code == 401
    assert client.post(f"/harvests/{fake_id}/finalize").status_code == 401

    assert client.post("/collection-lots", json={}).status_code == 401
    assert client.get("/collection-lots").status_code == 401
    assert client.get(f"/collection-lots/{fake_id}").status_code == 401
    assert client.post(f"/collection-lots/{fake_id}/harvests", json={}).status_code == 401
    assert client.post(f"/collection-lots/{fake_id}/finalize").status_code == 401

    assert client.post("/batches", json={}).status_code == 401
    assert client.get("/batches").status_code == 401
    assert client.get(f"/batches/{fake_id}").status_code == 401
    assert client.post(f"/batches/{fake_id}/collection-lots", json={}).status_code == 401
    assert client.post(f"/batches/{fake_id}/finalize").status_code == 401
    assert client.patch(f"/batches/{fake_id}/status", json={}).status_code == 401


def test_role_boundaries_for_creations_and_mutations(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-roles@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-roles@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-roles@example.test", role=UserRole.PROCESSOR)
    client = TestClient(app)

    # 1. PROCESSOR cannot create Harvest (403)
    res = client.post(
        "/harvests",
        headers=_auth_headers(processor),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}PR-FAIL", "harvest_date": "2026-09-01", "quantity_kg": 50.0},
    )
    assert res.status_code == 403

    # 2. BEEKEEPER cannot create Collection Lot (403)
    res = client.post(
        "/collection-lots",
        headers=_auth_headers(beekeeper),
        json={"lot_code": f"{TEST_LOT_PREFIX}BK-FAIL", "quantity_kg": 50.0},
    )
    assert res.status_code == 403

    # 3. BEEKEEPER cannot create Batch (403)
    res = client.post(
        "/batches",
        headers=_auth_headers(beekeeper),
        json={"batch_code": f"{TEST_BATCH_PREFIX}BK-FAIL"},
    )
    assert res.status_code == 403

    # 4. PROCESSOR can create Collection Lot (201)
    res = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}PR-OK", "quantity_kg": 100.0},
    )
    assert res.status_code == 201

    # 5. PROCESSOR can create Batch (201)
    res = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": f"{TEST_BATCH_PREFIX}PR-OK"},
    )
    assert res.status_code == 201
    assert res.json()["processor_id"] == str(processor.id)

    # 6. BEEKEEPER / PROCESSOR cannot transition batch status (403)
    batch_id = res.json()["id"]
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(processor),
        json={"status": "HOLD"},
    )
    assert res.status_code == 403

    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(beekeeper),
        json={"status": "HOLD"},
    )
    assert res.status_code == 403


# ===========================================================================
# Harvest Domain Tests
# ===========================================================================

def test_harvest_lifecycle_allocation_and_finalization(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-hrv@example.test", role=UserRole.ADMIN)
    beekeeper1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1-hrv@example.test", role=UserRole.BEEKEEPER)
    beekeeper2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk2-hrv@example.test", role=UserRole.BEEKEEPER)

    hive1 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}001", beekeeper=beekeeper1)
    hive2 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}002", beekeeper=beekeeper1)
    hive_other = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}OTHER", beekeeper=beekeeper2)
    hive_inactive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}INACT", beekeeper=beekeeper1, is_active=False)

    client = TestClient(app)

    # 1. Beekeeper creates harvest
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper1),
        json={
            "harvest_code": f"{TEST_HARVEST_PREFIX}001",
            "harvest_date": "2026-09-05",
            "quantity_kg": 50.0,
            "notes": "Acacia honey harvest",
        },
    )
    assert res.status_code == 201
    harvest_data = res.json()
    harvest_id = harvest_data["id"]
    assert harvest_data["created_by_id"] == str(beekeeper1.id)
    assert harvest_data["is_finalized"] is False

    # 2. Duplicate harvest code rejected
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper1),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}001", "harvest_date": "2026-09-05", "quantity_kg": 20.0},
    )
    assert res.status_code == 409

    # 3. Invalid quantity rejected (<= 0)
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper1),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}NEG", "harvest_date": "2026-09-05", "quantity_kg": 0.0},
    )
    assert res.status_code == 422

    # 4. Beekeeper cannot allocate another beekeeper's hive (cross-tenant composition rejected)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive_other.id), "quantity_used_kg": 10.0},
    )
    assert res.status_code in (403, 422)

    # 5. Inactive hive allocation rejected
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive_inactive.id), "quantity_used_kg": 10.0},
    )
    assert res.status_code == 422

    # 6. Valid partial allocation from hive1 (30 kg)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive1.id), "quantity_used_kg": 30.0},
    )
    assert res.status_code == 201
    assert res.json()["allocated_quantity_kg"] == 30.0

    # 7. Allocation exceeding total harvest capacity rejected (already 30kg, adding 25kg > 50kg)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive2.id), "quantity_used_kg": 25.0},
    )
    assert res.status_code == 422

    # 8. Attempting to finalize with partial allocation fails (allocated 30kg != 50kg)
    res = client.post(
        f"/harvests/{harvest_id}/finalize",
        headers=_auth_headers(beekeeper1),
    )
    assert res.status_code == 422

    # 9. Complete allocation from hive2 (20 kg -> total 50 kg)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive2.id), "quantity_used_kg": 20.0},
    )
    assert res.status_code == 201
    assert res.json()["allocated_quantity_kg"] == 50.0

    # 10. Finalize harvest succeeds
    res = client.post(
        f"/harvests/{harvest_id}/finalize",
        headers=_auth_headers(beekeeper1),
    )
    assert res.status_code == 200
    assert res.json()["is_finalized"] is True
    assert res.json()["finalized_at"] is not None

    # 11. Finalized harvest is immutable (cannot add new allocation)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper1),
        json={"hive_id": str(hive1.id), "quantity_used_kg": 1.0},
    )
    assert res.status_code == 422


def test_admin_harvest_creation_requires_beekeeper_id(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-harv2@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-harv2@example.test", role=UserRole.BEEKEEPER)
    client = TestClient(app)

    # Missing beekeeper_id for admin returns 422
    res = client.post(
        "/harvests",
        headers=_auth_headers(admin),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}ADM-01", "harvest_date": "2026-09-05", "quantity_kg": 40.0},
    )
    assert res.status_code == 422

    # Admin successfully specifies beekeeper
    res = client.post(
        "/harvests",
        headers=_auth_headers(admin),
        json={
            "harvest_code": f"{TEST_HARVEST_PREFIX}ADM-01",
            "harvest_date": "2026-09-05",
            "quantity_kg": 40.0,
            "beekeeper_id": str(beekeeper.id),
        },
    )
    assert res.status_code == 201
    assert res.json()["created_by_id"] == str(beekeeper.id)


# ===========================================================================
# Collection Lot Domain Tests
# ===========================================================================

def test_collection_lot_lifecycle_and_oversubscription_prevention(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-lot@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-lot@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-lot@example.test", role=UserRole.PROCESSOR)

    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}LOT", beekeeper=beekeeper)
    client = TestClient(app)

    # Create & finalize harvest (100 kg)
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}LOT-H1", "harvest_date": "2026-09-01", "quantity_kg": 100.0},
    )
    harvest_id = res.json()["id"]

    # Allocate hive and finalize harvest
    client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": 100.0},
    )
    client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))

    # Create Collection Lot 1 (60 kg)
    res = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}001", "quantity_kg": 60.0},
    )
    lot1_id = res.json()["id"]

    # Allocate 60 kg from harvest to Lot 1 (partial harvest consumption)
    res = client.post(
        f"/collection-lots/{lot1_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 60.0},
    )
    assert res.status_code == 201

    # Finalize Lot 1
    res = client.post(f"/collection-lots/{lot1_id}/finalize", headers=_auth_headers(processor))
    assert res.status_code == 200
    assert res.json()["is_finalized"] is True

    # Create Collection Lot 2 (50 kg)
    res = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}002", "quantity_kg": 50.0},
    )
    lot2_id = res.json()["id"]

    # Attempting to allocate 50 kg from harvest fails because only 40 kg remains in harvest! (100 - 60 = 40)
    res = client.post(
        f"/collection-lots/{lot2_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 50.0},
    )
    assert res.status_code == 422
    assert "exceeds available source harvest quantity" in res.json()["detail"]

    # Allocate exactly remaining 40 kg
    res = client.post(
        f"/collection-lots/{lot2_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 40.0},
    )
    assert res.status_code == 201


# ===========================================================================
# Batch Domain & Status Lifecycle Tests
# ===========================================================================

def test_batch_lifecycle_derived_quantity_and_status_transitions(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-bat@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-bat@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-bat@example.test", role=UserRole.PROCESSOR)

    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}BAT", beekeeper=beekeeper)
    client = TestClient(app)

    # Setup upstream finalized Harvest (80 kg)
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}BAT", "harvest_date": "2026-09-02", "quantity_kg": 80.0},
    )
    harvest_id = res.json()["id"]
    client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": 80.0},
    )
    client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))

    # Setup upstream finalized Collection Lot (80 kg)
    res = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}BAT", "quantity_kg": 80.0},
    )
    lot_id = res.json()["id"]
    client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 80.0},
    )
    client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))

    # 1. Create Batch
    res = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": f"{TEST_BATCH_PREFIX}001"},
    )
    assert res.status_code == 201
    batch_data = res.json()
    batch_id = batch_data["id"]
    assert batch_data["status"] == BatchStatus.ACTIVE.value
    assert batch_data["is_finalized"] is False
    assert batch_data["derived_quantity_kg"] == 0.0

    # 2. Cannot finalize batch with 0 allocations
    res = client.post(f"/batches/{batch_id}/finalize", headers=_auth_headers(processor))
    assert res.status_code == 422

    # 3. Unfinalized batch cannot transition status (e.g. to HOLD)
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "HOLD"},
    )
    assert res.status_code == 422

    # 4. Allocate 50 kg from collection lot (partial lot allocation)
    res = client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": 50.0},
    )
    assert res.status_code == 201
    assert res.json()["derived_quantity_kg"] == 50.0

    # 5. Finalize Batch
    res = client.post(f"/batches/{batch_id}/finalize", headers=_auth_headers(processor))
    assert res.status_code == 200
    assert res.json()["is_finalized"] is True
    assert res.json()["derived_quantity_kg"] == 50.0

    # 6. Status transition: ACTIVE -> HOLD (by Admin)
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "HOLD"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == BatchStatus.HOLD.value

    # 7. Illegal transition: HOLD -> RECALL is rejected
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "RECALL"},
    )
    assert res.status_code == 422

    # 8. Status transition: HOLD -> ACTIVE (by Admin)
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "ACTIVE"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == BatchStatus.ACTIVE.value

    # 9. Status transition: ACTIVE -> RECALL (by Admin)
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "RECALL"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == BatchStatus.RECALL.value

    # 10. RECALL is terminal: RECALL -> ACTIVE or HOLD is rejected
    res = client.patch(
        f"/batches/{batch_id}/status",
        headers=_auth_headers(admin),
        json={"status": "ACTIVE"},
    )
    assert res.status_code == 422

    # 11. Verify AuditEvent recorded for transitions
    audit_count = session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == UUID(batch_id))
    )
    assert audit_count >= 3  # (ACTIVE->HOLD, HOLD->ACTIVE, ACTIVE->RECALL)


# ===========================================================================
# Lineage Traversal & Downstream Isolation Tests
# ===========================================================================

def test_full_lineage_and_cross_beekeeper_isolation(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-lin@example.test", role=UserRole.ADMIN)
    beekeeper1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1-lin@example.test", role=UserRole.BEEKEEPER)
    beekeeper2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk2-lin@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-lin@example.test", role=UserRole.PROCESSOR)

    hive1 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}LIN1", beekeeper=beekeeper1, location_region="Kashmir")
    hive2 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}LIN2", beekeeper=beekeeper2, location_region="Jammu")
    client = TestClient(app)

    # Harvest 1 (Beekeeper 1, 40 kg)
    res1 = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper1),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}LIN1", "harvest_date": "2026-09-01", "quantity_kg": 40.0},
    )
    h1_id = res1.json()["id"]
    client.post(f"/harvests/{h1_id}/hives", headers=_auth_headers(beekeeper1), json={"hive_id": str(hive1.id), "quantity_used_kg": 40.0})
    client.post(f"/harvests/{h1_id}/finalize", headers=_auth_headers(beekeeper1))

    # Harvest 2 (Beekeeper 2, 60 kg)
    res2 = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper2),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}LIN2", "harvest_date": "2026-09-02", "quantity_kg": 60.0},
    )
    h2_id = res2.json()["id"]
    client.post(f"/harvests/{h2_id}/hives", headers=_auth_headers(beekeeper2), json={"hive_id": str(hive2.id), "quantity_used_kg": 60.0})
    client.post(f"/harvests/{h2_id}/finalize", headers=_auth_headers(beekeeper2))

    # Collection Lot blending both harvests (100 kg)
    res_lot = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}BLEND", "quantity_kg": 100.0},
    )
    lot_id = res_lot.json()["id"]
    client.post(f"/collection-lots/{lot_id}/harvests", headers=_auth_headers(processor), json={"harvest_id": h1_id, "quantity_used_kg": 40.0})
    client.post(f"/collection-lots/{lot_id}/harvests", headers=_auth_headers(processor), json={"harvest_id": h2_id, "quantity_used_kg": 60.0})
    client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))

    # Batch consuming Collection Lot (100 kg)
    res_batch = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": f"{TEST_BATCH_PREFIX}BLEND"},
    )
    batch_id = res_batch.json()["id"]
    client.post(f"/batches/{batch_id}/collection-lots", headers=_auth_headers(processor), json={"collection_lot_id": lot_id, "quantity_used_kg": 100.0})
    client.post(f"/batches/{batch_id}/finalize", headers=_auth_headers(processor))

    # 1. Admin reads full lineage (sees both Beekeeper 1 and Beekeeper 2 harvests)
    res = client.get(f"/batches/{batch_id}", headers=_auth_headers(admin))
    assert res.status_code == 200
    batch_detail = res.json()
    assert len(batch_detail["collection_lots"]) == 1
    harvests_in_lot = batch_detail["collection_lots"][0]["harvests"]
    assert len(harvests_in_lot) == 2

    # 2. Beekeeper 1 reads lineage: only sees Beekeeper 1's harvest! (Beekeeper 2 is masked)
    res = client.get(f"/batches/{batch_id}", headers=_auth_headers(beekeeper1))
    assert res.status_code == 200
    b1_view = res.json()
    b1_harvests = b1_view["collection_lots"][0]["harvests"]
    assert len(b1_harvests) == 1
    assert b1_harvests[0]["harvest_id"] == h1_id
    assert b1_harvests[0]["hives"][0]["hive_code"] == f"{TEST_HIVE_PREFIX}LIN1"

    # 3. Third unrelated beekeeper cannot access batch (403)
    unrelated_beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk3-unrel@example.test", role=UserRole.BEEKEEPER)
    res = client.get(f"/batches/{batch_id}", headers=_auth_headers(unrelated_beekeeper))
    assert res.status_code == 403


def test_downstream_domain_isolation(session: Session) -> None:
    # Ensure zero records created in downstream tables for traceability entities:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-iso@example.test", role=UserRole.PROCESSOR)
    client = TestClient(app)
    res_b = client.post("/batches", headers=_auth_headers(processor), json={"batch_code": f"{TEST_BATCH_PREFIX}ISO"})
    assert res_b.status_code == 201
    batch_id = UUID(res_b.json()["id"])

    assert session.scalar(select(func.count()).select_from(LabEvidence).where(LabEvidence.batch_id == batch_id)) == 0
    assert session.scalar(select(func.count()).select_from(BlockchainRecord).where(BlockchainRecord.batch_id == batch_id)) == 0
    assert session.scalar(select(func.count()).select_from(PackagingLot).where(PackagingLot.batch_id == batch_id)) == 0


def test_beekeeper_cannot_view_or_mutate_another_beekeepers_harvest(session: Session) -> None:
    beekeeper1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1-priv@example.test", role=UserRole.BEEKEEPER)
    beekeeper2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk2-priv@example.test", role=UserRole.BEEKEEPER)
    hive1 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}PRIV1", beekeeper=beekeeper1)
    hive2 = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}PRIV2", beekeeper=beekeeper2)
    client = TestClient(app)

    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper1),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}PRIV1", "harvest_date": "2026-09-01", "quantity_kg": 50.0},
    )
    harvest_id = res.json()["id"]

    # Beekeeper 2 cannot view Beekeeper 1's harvest (403)
    assert client.get(f"/harvests/{harvest_id}", headers=_auth_headers(beekeeper2)).status_code == 403

    # Beekeeper 2 cannot allocate hive to Beekeeper 1's harvest (403)
    res = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper2),
        json={"hive_id": str(hive2.id), "quantity_used_kg": 10.0},
    )
    assert res.status_code == 403

    # Beekeeper 2 cannot finalize Beekeeper 1's harvest (403)
    assert client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper2)).status_code == 403


def test_collection_lot_oversubscription_across_batches(session: Session) -> None:
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}adm-over@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-over@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-over@example.test", role=UserRole.PROCESSOR)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}OVER", beekeeper=beekeeper)
    client = TestClient(app)

    # Harvest (100 kg) & Lot (100 kg)
    res_h = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}OVER", "harvest_date": "2026-09-01", "quantity_kg": 100.0},
    )
    h_id = res_h.json()["id"]
    client.post(f"/harvests/{h_id}/hives", headers=_auth_headers(beekeeper), json={"hive_id": str(hive.id), "quantity_used_kg": 100.0})
    client.post(f"/harvests/{h_id}/finalize", headers=_auth_headers(beekeeper))

    res_l = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}OVER", "quantity_kg": 100.0},
    )
    lot_id = res_l.json()["id"]
    client.post(f"/collection-lots/{lot_id}/harvests", headers=_auth_headers(processor), json={"harvest_id": h_id, "quantity_used_kg": 100.0})
    client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))

    # Batch 1 consumes 70 kg
    res_b1 = client.post("/batches", headers=_auth_headers(processor), json={"batch_code": f"{TEST_BATCH_PREFIX}OVR1"})
    b1_id = res_b1.json()["id"]
    res = client.post(f"/batches/{b1_id}/collection-lots", headers=_auth_headers(processor), json={"collection_lot_id": lot_id, "quantity_used_kg": 70.0})
    assert res.status_code == 201

    # Batch 2 attempts to consume 40 kg (exceeds remaining 30 kg) -> 422
    res_b2 = client.post("/batches", headers=_auth_headers(processor), json={"batch_code": f"{TEST_BATCH_PREFIX}OVR2"})
    b2_id = res_b2.json()["id"]
    res = client.post(f"/batches/{b2_id}/collection-lots", headers=_auth_headers(processor), json={"collection_lot_id": lot_id, "quantity_used_kg": 40.0})
    assert res.status_code == 422
    assert "exceeds available collection lot quantity" in res.json()["detail"]

    # Batch 2 consumes exact remaining 30 kg -> 201
    res = client.post(f"/batches/{b2_id}/collection-lots", headers=_auth_headers(processor), json={"collection_lot_id": lot_id, "quantity_used_kg": 30.0})
    assert res.status_code == 201


def test_concurrent_allocations_prevent_oversubscription(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-conc@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-conc@example.test", role=UserRole.PROCESSOR)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}CONC", beekeeper=beekeeper)
    client = TestClient(app)

    # Setup finalized Harvest of 50 kg
    res = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}CONC", "harvest_date": "2026-09-01", "quantity_kg": 50.0},
    )
    harvest_id = res.json()["id"]
    client.post(f"/harvests/{harvest_id}/hives", headers=_auth_headers(beekeeper), json={"hive_id": str(hive.id), "quantity_used_kg": 50.0})
    client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))

    # Setup Collection Lot 1 (40 kg) and Collection Lot 2 (40 kg)
    res1 = client.post("/collection-lots", headers=_auth_headers(processor), json={"lot_code": f"{TEST_LOT_PREFIX}CNC1", "quantity_kg": 40.0})
    lot1_id = res1.json()["id"]
    res2 = client.post("/collection-lots", headers=_auth_headers(processor), json={"lot_code": f"{TEST_LOT_PREFIX}CNC2", "quantity_kg": 40.0})
    lot2_id = res2.json()["id"]

    # Attempt two concurrent allocations of 35 kg each from the 50 kg harvest
    def allocate(lot_id: str) -> int:
        c = TestClient(app)
        r = c.post(
            f"/collection-lots/{lot_id}/harvests",
            headers=_auth_headers(processor),
            json={"harvest_id": harvest_id, "quantity_used_kg": 35.0},
        )
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(allocate, lot1_id)
        f2 = executor.submit(allocate, lot2_id)
        status1 = f1.result()
        status2 = f2.result()

    statuses = [status1, status2]
    # Exactly one must succeed (201) and one must be rejected (422)
    assert 201 in statuses
    assert 422 in statuses

    # Verify that total consumed quantity in DB is exactly 35.0, NOT 70.0
    total_consumed = session.scalar(
        select(func.sum(CollectionLotHarvest.quantity_used_kg)).where(CollectionLotHarvest.harvest_id == UUID(harvest_id))
    )
    assert float(total_consumed) == 35.0


def test_unfinalized_source_allocations_allowed_and_provenance_immutability(session: Session) -> None:
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk-unfin@example.test", role=UserRole.BEEKEEPER)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}pr-unfin@example.test", role=UserRole.PROCESSOR)
    hive = _create_hive(session, hive_code=f"{TEST_HIVE_PREFIX}UNFIN", beekeeper=beekeeper)
    client = TestClient(app)

    # 1. Create Harvest (100 kg) - remain UNFINALIZED
    res_h = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}UNFIN", "harvest_date": "2026-09-01", "quantity_kg": 100.0},
    )
    harvest_id = res_h.json()["id"]
    assert res_h.json()["is_finalized"] is False

    # 2. Create Collection Lot (60 kg) - allocate from UNFINALIZED harvest
    res_l = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}UNFIN", "quantity_kg": 60.0},
    )
    lot_id = res_l.json()["id"]
    assert res_l.json()["is_finalized"] is False

    res_alloc_lot = client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 60.0},
    )
    assert res_alloc_lot.status_code == 201
    assert res_alloc_lot.json()["allocated_quantity_kg"] == 60.0

    # 3. Create Batch - allocate from UNFINALIZED collection lot
    res_b = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": f"{TEST_BATCH_PREFIX}UNFIN"},
    )
    batch_id = res_b.json()["id"]
    assert res_b.json()["is_finalized"] is False

    res_alloc_batch = client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": 40.0},
    )
    assert res_alloc_batch.status_code == 201
    assert res_alloc_batch.json()["derived_quantity_kg"] == 40.0

    # 4. Finalize Batch
    res_fin_batch = client.post(f"/batches/{batch_id}/finalize", headers=_auth_headers(processor))
    assert res_fin_batch.status_code == 200
    assert res_fin_batch.json()["is_finalized"] is True

    # 5. Provenance immutability: Cannot add allocations to finalized Batch
    res_fail_batch = client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": 10.0},
    )
    assert res_fail_batch.status_code == 422
    assert "Cannot add allocations to a finalized batch" in res_fail_batch.json()["detail"]

    # 6. Finalize Collection Lot (exact balance 60.0 == 60.0)
    res_fin_lot = client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))
    assert res_fin_lot.status_code == 200
    assert res_fin_lot.json()["is_finalized"] is True

    # 7. Provenance immutability: Cannot add allocations to finalized Collection Lot
    res_fail_lot = client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 1.0},
    )
    assert res_fail_lot.status_code == 422
    assert "Cannot add allocations to a finalized collection lot" in res_fail_lot.json()["detail"]

    # 8. Allocate exact 100 kg to harvest and finalize Harvest
    client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": 100.0},
    )
    res_fin_h = client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))
    assert res_fin_h.status_code == 200
    assert res_fin_h.json()["is_finalized"] is True

    # 9. Provenance immutability: Cannot add allocations to finalized Harvest
    res_fail_h = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": 1.0},
    )
    assert res_fail_h.status_code == 422
    assert "Cannot add allocations to a finalized harvest" in res_fail_h.json()["detail"]


def test_traceability_cleanup_preserves_sentinel_data(session: Session) -> None:
    """Validate that scoped cleanup does NOT delete unrelated sentinel records."""
    sentinel_user = User(
        id=uuid4(),
        name="Sentinel User",
        email=f"sentinel-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("SentinelPass123!"),
        role=UserRole.BEEKEEPER,
        is_active=True,
    )
    session.add(sentinel_user)
    session.commit()

    sentinel_hive = Hive(
        id=uuid4(),
        hive_code=f"SENTINEL-HIV-{uuid4().hex[:8]}",
        beekeeper_id=sentinel_user.id,
        location_region="Sentinel Test Region",
        status=HiveStatus.ACTIVE,
    )
    session.add(sentinel_hive)
    session.commit()

    sentinel_harvest = Harvest(
        id=uuid4(),
        harvest_code=f"SENTINEL-HRV-{uuid4().hex[:8]}",
        created_by_id=sentinel_user.id,
        quantity_kg=50.0,
        harvest_date=date(2026, 9, 1),
        is_finalized=False,
    )
    session.add(sentinel_harvest)
    session.commit()

    sentinel_audit = AuditEvent(
        id=uuid4(),
        event_type="SENTINEL_EVENT",
        entity_type="HARVEST",
        entity_id=sentinel_harvest.id,
        actor_user_id=sentinel_user.id,
        timestamp=datetime.now(UTC),
    )
    session.add(sentinel_audit)
    session.commit()

    try:
        _cleanup(session)

        surviving_user = session.get(User, sentinel_user.id)
        assert surviving_user is not None
        assert surviving_user.id == sentinel_user.id

        surviving_hive = session.get(Hive, sentinel_hive.id)
        assert surviving_hive is not None
        assert surviving_hive.id == sentinel_hive.id

        surviving_harvest = session.get(Harvest, sentinel_harvest.id)
        assert surviving_harvest is not None
        assert surviving_harvest.id == sentinel_harvest.id

        surviving_audit = session.get(AuditEvent, sentinel_audit.id)
        assert surviving_audit is not None
        assert surviving_audit.id == sentinel_audit.id
    finally:
        session.execute(delete(AuditEvent).where(AuditEvent.id == sentinel_audit.id))
        session.execute(delete(Harvest).where(Harvest.id == sentinel_harvest.id))
        session.execute(delete(Hive).where(Hive.id == sentinel_hive.id))
        session.execute(delete(User).where(User.id == sentinel_user.id))
        session.commit()
