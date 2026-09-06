"""Comprehensive test suite for Packaging Lot domain and concurrency locking."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Generator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, HiveStatus, PackagingUnit, UserRole
from app.models.evidence import PackagingLot
from app.models.hive import Harvest, Hive, HiveHarvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest

TEST_EMAIL_PREFIX = "test-pkg-"
TEST_HIVE_PREFIX = "PKG-HIV-"
TEST_HARVEST_PREFIX = "PKG-HRV-"
TEST_LOT_PREFIX = "PKG-LOT-"
TEST_BATCH_PREFIX = "PKG-BAT-"
TEST_PACKAGE_LOT_PREFIX = "PKG-PKG-"


def _cleanup(database_session: Session) -> None:
    """Clean up test data across tables, strictly scoped to test-owned IDs."""
    pkg_ids = database_session.scalars(
        select(PackagingLot.id).where(PackagingLot.package_lot_code.like(f"{TEST_PACKAGE_LOT_PREFIX}%"))
    ).all()
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

    if pkg_ids:
        database_session.execute(delete(PackagingLot).where(PackagingLot.id.in_(pkg_ids)))

    # Scoped AuditEvents
    audit_conditions = []
    if user_ids:
        audit_conditions.append(AuditEvent.actor_user_id.in_(user_ids))
    entity_ids = set(pkg_ids) | set(batch_ids) | set(lot_ids) | set(harvest_ids) | set(hive_ids)
    if entity_ids:
        audit_conditions.append(AuditEvent.entity_id.in_(list(entity_ids)))
    if audit_conditions:
        database_session.execute(delete(AuditEvent).where(or_(*audit_conditions)))

    # Scoped child junction records
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

    # Scoped primary records
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
    db = SessionLocal()
    _cleanup(db)
    try:
        yield db
    finally:
        _cleanup(db)
        db.close()


def _create_user(session: Session, email: str, role: UserRole) -> User:
    user = User(
        name=f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _create_hive(session: Session, hive_code: str, beekeeper: User) -> Hive:
    hive = Hive(
        hive_code=hive_code,
        beekeeper_id=beekeeper.id,
        location_region="Black Forest",
        status=HiveStatus.ACTIVE,
    )
    session.add(hive)
    session.commit()
    session.refresh(hive)
    return hive


def _setup_traceability_lineage(
    session: Session,
    beekeeper: User,
    processor: User,
    batch_code: str,
    quantity_kg: float = 100.0,
    finalize_batch: bool = True,
    batch_status: BatchStatus = BatchStatus.ACTIVE,
) -> tuple[Batch, Hive, Harvest, CollectionLot]:
    """Helper to set up a full verified lineage up to a Batch."""
    unique_suffix = uuid4().hex[:6]
    client = TestClient(app)

    # 1. Hive
    hive = _create_hive(session, f"{TEST_HIVE_PREFIX}{unique_suffix}", beekeeper)

    # 2. Harvest
    res_h = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={
            "harvest_code": f"{TEST_HARVEST_PREFIX}{unique_suffix}",
            "harvest_date": str(date.today()),
            "quantity_kg": quantity_kg,
        },
    )
    assert res_h.status_code == 201, res_h.text
    harvest_id = res_h.json()["id"]

    res_h_alloc = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": quantity_kg},
    )
    assert res_h_alloc.status_code == 201, res_h_alloc.text

    res_h_fin = client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))
    assert res_h_fin.status_code == 200, res_h_fin.text

    # 3. Collection Lot
    res_lot = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={
            "lot_code": f"{TEST_LOT_PREFIX}{unique_suffix}",
            "quantity_kg": quantity_kg,
        },
    )
    assert res_lot.status_code == 201, res_lot.text
    lot_id = res_lot.json()["id"]

    res_lot_alloc = client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": quantity_kg},
    )
    assert res_lot_alloc.status_code == 201, res_lot_alloc.text

    res_lot_fin = client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))
    assert res_lot_fin.status_code == 200, res_lot_fin.text

    # 4. Batch
    res_b = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": batch_code},
    )
    assert res_b.status_code == 201, res_b.text
    batch_id = res_b.json()["id"]

    res_b_alloc = client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": quantity_kg},
    )
    assert res_b_alloc.status_code == 201, res_b_alloc.text

    if finalize_batch:
        res_b_fin = client.post(f"/batches/{batch_id}/finalize", headers=_auth_headers(processor))
        assert res_b_fin.status_code == 200, res_b_fin.text

    if batch_status != BatchStatus.ACTIVE:
        admin_user = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-status-{unique_suffix}@example.com", UserRole.ADMIN)
        res_b_status = client.patch(
            f"/batches/{batch_id}/status",
            headers=_auth_headers(admin_user),
            json={"status": batch_status.value},
        )
        assert res_b_status.status_code == 200, res_b_status.text

    batch = session.scalar(select(Batch).where(Batch.id == UUID(batch_id)))
    harvest = session.scalar(select(Harvest).where(Harvest.id == UUID(harvest_id)))
    collection_lot = session.scalar(select(CollectionLot).where(CollectionLot.id == UUID(lot_id)))

    assert batch is not None
    assert harvest is not None
    assert collection_lot is not None

    return batch, hive, harvest, collection_lot


# ---------------------------------------------------------------------------
# Test 1: Create PackagingLot success
# ---------------------------------------------------------------------------

def test_create_packaging_lot_success(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk1@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr1@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}001", 100.0)

    client = TestClient(app)
    lot_code = f"{TEST_PACKAGE_LOT_PREFIX}001"
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": lot_code,
            "quantity": 100,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["package_lot_code"] == lot_code
    assert data["batch_id"] == str(batch.id)
    assert data["quantity"] == 100
    assert data["unit"] == "JARS"
    assert data["package_size_grams"] == 500.0
    assert data["packaged_quantity_kg"] == 50.0
    assert "created_at" in data

    # Verify audit event
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "PACKAGING_LOT",
            AuditEvent.entity_id == UUID(data["id"]),
        )
    )
    assert audit is not None
    assert audit.event_type == "PACKAGING_LOT_CREATED"
    assert audit.actor_user_id == pr.id
    assert audit.metadata_json["package_lot_code"] == lot_code
    assert audit.metadata_json["packaged_quantity_kg"] == 50.0


# ---------------------------------------------------------------------------
# Test 2: ADMIN creation
# ---------------------------------------------------------------------------

def test_admin_creation(session: Session) -> None:
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm@example.com", UserRole.ADMIN)
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk2@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr2@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}002", 50.0)

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(admin),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}ADM",
            "quantity": 50,
            "unit": "BOTTLES",
            "package_size_grams": 250.0,
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["packaged_quantity_kg"] == 12.5


# ---------------------------------------------------------------------------
# Test 3: Owning PROCESSOR creation
# ---------------------------------------------------------------------------

def test_owning_processor_creation(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk3@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr3@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}003", 40.0)

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}OWN",
            "quantity": 40,
            "unit": "PACKS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["packaged_quantity_kg"] == 20.0


# ---------------------------------------------------------------------------
# Test 4: Non-owning PROCESSOR rejection
# ---------------------------------------------------------------------------

def test_non_owning_processor_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk4@example.com", UserRole.BEEKEEPER)
    pr1 = _create_user(session, f"{TEST_EMAIL_PREFIX}pr4a@example.com", UserRole.PROCESSOR)
    pr2 = _create_user(session, f"{TEST_EMAIL_PREFIX}pr4b@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr1, f"{TEST_BATCH_PREFIX}004", 40.0)

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr2),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}NOTOWN",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 403, res.text
    assert "Processors can only create packaging for their own batches" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 5: BEEKEEPER create rejection
# ---------------------------------------------------------------------------

def test_beekeeper_create_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk5@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr5@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}005", 40.0)

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(bk),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}BKREJ",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 403, res.text


# ---------------------------------------------------------------------------
# Test 6: Unfinalized Batch rejection
# ---------------------------------------------------------------------------

def test_unfinalized_batch_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk6@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr6@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(
        session, bk, pr, f"{TEST_BATCH_PREFIX}006", 40.0, finalize_batch=False
    )

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}UNFIN",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 422, res.text
    assert "Cannot create packaging for an unfinalized batch" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 7: HOLD Batch rejection
# ---------------------------------------------------------------------------

def test_hold_batch_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk7@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr7@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(
        session, bk, pr, f"{TEST_BATCH_PREFIX}007", 40.0, batch_status=BatchStatus.HOLD
    )

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}HOLD",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 422, res.text
    assert "HOLD" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 8: RECALL Batch rejection
# ---------------------------------------------------------------------------

def test_recall_batch_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk8@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr8@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(
        session, bk, pr, f"{TEST_BATCH_PREFIX}008", 40.0, batch_status=BatchStatus.RECALL
    )

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}RECALL",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 422, res.text
    assert "RECALL" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 9: Zero/negative quantity rejection
# ---------------------------------------------------------------------------

def test_zero_and_negative_quantity_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk9@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr9@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}009", 40.0)

    client = TestClient(app)
    # Zero quantity
    res0 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}QTY0",
            "quantity": 0,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res0.status_code == 422, res0.text

    # Negative quantity
    res_neg = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}QTYNEG",
            "quantity": -5,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res_neg.status_code == 422, res_neg.text


# ---------------------------------------------------------------------------
# Test 10: Zero/negative package size rejection
# ---------------------------------------------------------------------------

def test_zero_and_negative_package_size_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk10@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr10@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}010", 40.0)

    client = TestClient(app)
    # Zero size
    res0 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}SZ0",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 0.0,
        },
    )
    assert res0.status_code == 422, res0.text

    # Negative size
    res_neg = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}SZNEG",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": -100.0,
        },
    )
    assert res_neg.status_code == 422, res_neg.text


# ---------------------------------------------------------------------------
# Test 11: Exact quantity conversion to kg
# ---------------------------------------------------------------------------

def test_exact_quantity_conversion_to_kg(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk11@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr11@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}011", 100.0)

    client = TestClient(app)
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}CNV1",
            "quantity": 250,
            "unit": "POUCHES",
            "package_size_grams": 200.0,
        },
    )
    assert res.status_code == 201, res.text
    # (250 * 200) / 1000 = 50.0 kg
    assert res.json()["packaged_quantity_kg"] == 50.0

    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}CNV2",
            "quantity": 7,
            "unit": "JARS",
            "package_size_grams": 333.33,
        },
    )
    assert res2.status_code == 201, res2.text
    # (7 * 333.33) / 1000 = 2.33331 kg
    assert abs(res2.json()["packaged_quantity_kg"] - 2.33331) < 1e-4


# ---------------------------------------------------------------------------
# Test 12: Multiple PackagingLots under one Batch
# ---------------------------------------------------------------------------

def test_multiple_packaging_lots_under_one_batch(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk12@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr12@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}012", 100.0)

    client = TestClient(app)
    res1 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}MULT1",
            "quantity": 50,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res1.status_code == 201, res1.text
    assert res1.json()["packaged_quantity_kg"] == 25.0

    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}MULT2",
            "quantity": 100,
            "unit": "BOTTLES",
            "package_size_grams": 250.0,
        },
    )
    assert res2.status_code == 201, res2.text
    assert res2.json()["packaged_quantity_kg"] == 25.0

    res3 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}MULT3",
            "quantity": 50,
            "unit": "PACKS",
            "package_size_grams": 500.0,
        },
    )
    assert res3.status_code == 201, res3.text
    assert res3.json()["packaged_quantity_kg"] == 25.0

    # Total consumed: 75 kg <= 100 kg
    list_res = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(pr))
    assert list_res.status_code == 200
    assert len(list_res.json()) == 3


# ---------------------------------------------------------------------------
# Test 13: Partial packaging
# ---------------------------------------------------------------------------

def test_partial_packaging(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk13@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr13@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}013", 100.0)

    client = TestClient(app)
    # Only package 10 kg out of 100 kg
    res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}PART",
            "quantity": 20,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["packaged_quantity_kg"] == 10.0


# ---------------------------------------------------------------------------
# Test 14: Exact 100% packaging still allowed
# ---------------------------------------------------------------------------

def test_exact_100_percent_packaging_allowed(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk14@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr14@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}014", 60.0)

    client = TestClient(app)
    # First 30 kg
    res1 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}EX1",
            "quantity": 60,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res1.status_code == 201, res1.text
    assert res1.json()["packaged_quantity_kg"] == 30.0

    # Remaining exact 30 kg
    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}EX2",
            "quantity": 60,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res2.status_code == 201, res2.text
    assert res2.json()["packaged_quantity_kg"] == 30.0


# ---------------------------------------------------------------------------
# Test 15: Oversubscription rejection
# ---------------------------------------------------------------------------

def test_oversubscription_rejection(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk15@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr15@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}015", 50.0)

    client = TestClient(app)
    # Package 40 kg (80 jars of 500g)
    res1 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}OVR1",
            "quantity": 80,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res1.status_code == 201, res1.text

    # Attempt to package another 20 kg (40 jars of 500g) -> total 60 kg > 50 kg
    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}OVR2",
            "quantity": 40,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert res2.status_code == 422, res2.text
    assert "exceeds remaining batch quantity" in res2.json()["detail"]

    # Verify only 1 packaging lot exists
    count = session.scalar(
        select(func.count(PackagingLot.id)).where(PackagingLot.batch_id == batch.id)
    )
    assert count == 1


# ---------------------------------------------------------------------------
# Test 16: Concurrent quantity protection using row locking
# ---------------------------------------------------------------------------

def test_concurrent_quantity_protection_using_row_locking(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk16@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr16@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}016", 50.0)

    # Two concurrent requests to package 35 kg each from a 50 kg batch
    def package_batch(code_suffix: str) -> int:
        c = TestClient(app)
        r = c.post(
            f"/batches/{batch.id}/packaging",
            headers=_auth_headers(pr),
            json={
                "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}CNC{code_suffix}",
                "quantity": 70,
                "unit": "JARS",
                "package_size_grams": 500.0,  # 35.0 kg
            },
        )
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(package_batch, "1")
        f2 = executor.submit(package_batch, "2")
        status1 = f1.result()
        status2 = f2.result()

    statuses = [status1, status2]
    assert 201 in statuses
    assert 422 in statuses

    # Confirm exactly 1 lot in DB, totaling 35 kg
    total_qty = session.scalar(
        select(
            func.sum((PackagingLot.quantity * PackagingLot.package_size_grams) / 1000.0)
        ).where(PackagingLot.batch_id == batch.id)
    )
    assert float(total_qty) == 35.0


# ---------------------------------------------------------------------------
# Test 17: GET batch packaging authorization
# ---------------------------------------------------------------------------

def test_get_batch_packaging_authorization(session: Session) -> None:
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm17@example.com", UserRole.ADMIN)
    bk_lineage = _create_user(session, f"{TEST_EMAIL_PREFIX}bk17a@example.com", UserRole.BEEKEEPER)
    bk_other = _create_user(session, f"{TEST_EMAIL_PREFIX}bk17b@example.com", UserRole.BEEKEEPER)
    pr_own = _create_user(session, f"{TEST_EMAIL_PREFIX}pr17a@example.com", UserRole.PROCESSOR)
    pr_other = _create_user(session, f"{TEST_EMAIL_PREFIX}pr17b@example.com", UserRole.PROCESSOR)

    batch, _, _, _ = _setup_traceability_lineage(session, bk_lineage, pr_own, f"{TEST_BATCH_PREFIX}017", 50.0)

    client = TestClient(app)
    create_res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr_own),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}AUTH17",
            "quantity": 20,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert create_res.status_code == 201

    # 1. Admin: Allowed
    res_adm = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(admin))
    assert res_adm.status_code == 200
    assert len(res_adm.json()) == 1

    # 2. Owning Processor: Allowed
    res_pr = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(pr_own))
    assert res_pr.status_code == 200
    assert len(res_pr.json()) == 1

    # 3. Lineage Beekeeper: Allowed
    res_bk = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(bk_lineage))
    assert res_bk.status_code == 200
    assert len(res_bk.json()) == 1

    # 4. Non-owning Processor: 403
    res_pr_other = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(pr_other))
    assert res_pr_other.status_code == 403

    # 5. Non-lineage Beekeeper: 403
    res_bk_other = client.get(f"/batches/{batch.id}/packaging", headers=_auth_headers(bk_other))
    assert res_bk_other.status_code == 403


# ---------------------------------------------------------------------------
# Test 18: GET individual packaging authorization
# ---------------------------------------------------------------------------

def test_get_individual_packaging_authorization(session: Session) -> None:
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm18@example.com", UserRole.ADMIN)
    bk_lineage = _create_user(session, f"{TEST_EMAIL_PREFIX}bk18a@example.com", UserRole.BEEKEEPER)
    bk_other = _create_user(session, f"{TEST_EMAIL_PREFIX}bk18b@example.com", UserRole.BEEKEEPER)
    pr_own = _create_user(session, f"{TEST_EMAIL_PREFIX}pr18a@example.com", UserRole.PROCESSOR)
    pr_other = _create_user(session, f"{TEST_EMAIL_PREFIX}pr18b@example.com", UserRole.PROCESSOR)

    batch, _, _, _ = _setup_traceability_lineage(session, bk_lineage, pr_own, f"{TEST_BATCH_PREFIX}018", 50.0)

    client = TestClient(app)
    create_res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr_own),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}IND18",
            "quantity": 20,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert create_res.status_code == 201
    lot_id = create_res.json()["id"]

    # 1. Admin: Allowed (and includes batch reference)
    res_adm = client.get(f"/packaging/{lot_id}", headers=_auth_headers(admin))
    assert res_adm.status_code == 200
    data_adm = res_adm.json()
    assert data_adm["id"] == lot_id
    assert data_adm["batch"]["id"] == str(batch.id)
    assert data_adm["batch"]["batch_code"] == batch.batch_code
    assert data_adm["batch"]["derived_quantity_kg"] == 50.0

    # 2. Owning Processor: Allowed
    res_pr = client.get(f"/packaging/{lot_id}", headers=_auth_headers(pr_own))
    assert res_pr.status_code == 200
    assert res_pr.json()["id"] == lot_id

    # 3. Lineage Beekeeper: Allowed
    res_bk = client.get(f"/packaging/{lot_id}", headers=_auth_headers(bk_lineage))
    assert res_bk.status_code == 200
    assert res_bk.json()["id"] == lot_id

    # 4. Non-owning Processor: 403
    res_pr_other = client.get(f"/packaging/{lot_id}", headers=_auth_headers(pr_other))
    assert res_pr_other.status_code == 403

    # 5. Non-lineage Beekeeper: 403
    res_bk_other = client.get(f"/packaging/{lot_id}", headers=_auth_headers(bk_other))
    assert res_bk_other.status_code == 403

    # 6. Non-existent packaging lot: 404
    res_404 = client.get(f"/packaging/{uuid4()}", headers=_auth_headers(admin))
    assert res_404.status_code == 404


# ---------------------------------------------------------------------------
# Test 19: Immutability / No mutation endpoints
# ---------------------------------------------------------------------------

def test_immutability_no_mutation_endpoints(session: Session) -> None:
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm19@example.com", UserRole.ADMIN)
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk19@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr19@example.com", UserRole.PROCESSOR)
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}019", 50.0)

    client = TestClient(app)
    create_res = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}IMM19",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
    )
    assert create_res.status_code == 201
    lot_id = create_res.json()["id"]

    # PATCH /packaging/{lot_id} -> 405 Method Not Allowed
    res_patch = client.patch(f"/packaging/{lot_id}", headers=_auth_headers(admin), json={"quantity": 20})
    assert res_patch.status_code == 405

    # DELETE /packaging/{lot_id} -> 405 Method Not Allowed
    res_delete = client.delete(f"/packaging/{lot_id}", headers=_auth_headers(admin))
    assert res_delete.status_code == 405

    # PUT /packaging/{lot_id} -> 405 Method Not Allowed
    res_put = client.put(f"/packaging/{lot_id}", headers=_auth_headers(admin), json={"quantity": 20})
    assert res_put.status_code == 405

    # PATCH /batches/{batch_id}/packaging -> 405 Method Not Allowed
    res_b_patch = client.patch(f"/batches/{batch.id}/packaging", headers=_auth_headers(admin))
    assert res_b_patch.status_code == 405

    # DELETE /batches/{batch_id}/packaging -> 405 Method Not Allowed
    res_b_delete = client.delete(f"/batches/{batch.id}/packaging", headers=_auth_headers(admin))
    assert res_b_delete.status_code == 405


# ---------------------------------------------------------------------------
# Test 20: No schema drift
# ---------------------------------------------------------------------------

def test_no_schema_drift() -> None:
    alembic_cfg = Config("alembic.ini")
    # command.check raises if there is a difference between models and DB
    command.check(alembic_cfg)


# ---------------------------------------------------------------------------
# Test 21: Tiny fractional oversubscription is strictly rejected (Decimal precision)
# ---------------------------------------------------------------------------

def test_tiny_fractional_oversubscription_rejected(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk21@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr21@example.com", UserRole.PROCESSOR)
    # 50.0 kg batch
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}021", 50.0)

    client = TestClient(app)
    # Package 49.999 kg (e.g. 49999 jars * 1.0g = 49.999 kg)
    res1 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}PREC1",
            "quantity": 49999,
            "unit": "JARS",
            "package_size_grams": 1.0,
        },
    )
    assert res1.status_code == 201, res1.text
    # Remaining: exactly 0.001 kg = 1.0 gram

    # Attempt to package 1.0001 grams (0.0000001 kg over remaining capacity)
    # Under float rounding (round(..., 4)), 1.0001g would round to 1.0g and mistakenly pass.
    # Under Decimal arithmetic, it MUST be rejected with 422!
    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}PREC2",
            "quantity": 1,
            "unit": "JARS",
            "package_size_grams": 1.0001,
        },
    )
    assert res2.status_code == 422, res2.text
    assert "exceeds remaining batch quantity" in res2.json()["detail"]


# ---------------------------------------------------------------------------
# Test 22: Exactly equal Decimal boundary is accepted
# ---------------------------------------------------------------------------

def test_exact_equal_decimal_boundary_accepted(session: Session) -> None:
    bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk22@example.com", UserRole.BEEKEEPER)
    pr = _create_user(session, f"{TEST_EMAIL_PREFIX}pr22@example.com", UserRole.PROCESSOR)
    # Batch with fractional derived quantity: 50.125 kg
    batch, _, _, _ = _setup_traceability_lineage(session, bk, pr, f"{TEST_BATCH_PREFIX}022", 50.125)

    client = TestClient(app)
    # First lot: 50.0 kg
    res1 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}BDY1",
            "quantity": 50,
            "unit": "JARS",
            "package_size_grams": 1000.0,
        },
    )
    assert res1.status_code == 201, res1.text

    # Second lot: exactly 0.125 kg (1 jar of 125.0g) -> total 50.125 kg == 50.125 kg
    res2 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}BDY2",
            "quantity": 1,
            "unit": "JARS",
            "package_size_grams": 125.0,
        },
    )
    assert res2.status_code == 201, res2.text
    assert res2.json()["packaged_quantity_kg"] == 0.125

    # Any further allocation, even 0.0001g, must be rejected
    res3 = client.post(
        f"/batches/{batch.id}/packaging",
        headers=_auth_headers(pr),
        json={
            "package_lot_code": f"{TEST_PACKAGE_LOT_PREFIX}BDY3",
            "quantity": 1,
            "unit": "JARS",
            "package_size_grams": 0.0001,
        },
    )
    assert res3.status_code == 422, res3.text


def test_packaging_cleanup_preserves_sentinel_data(session: Session) -> None:
    """Validate that scoped cleanup does NOT delete unrelated sentinel packaging lots."""
    sentinel_user = User(
        id=uuid4(),
        name="Sentinel User",
        email=f"sentinel-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("SentinelPass123!"),
        role=UserRole.PROCESSOR,
        is_active=True,
    )
    session.add(sentinel_user)
    session.commit()

    sentinel_batch = Batch(
        id=uuid4(),
        batch_code=f"SENTINEL-BAT-{uuid4().hex[:8]}",
        status=BatchStatus.ACTIVE,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
        processor_id=sentinel_user.id,
    )
    session.add(sentinel_batch)
    session.commit()

    sentinel_pkg = PackagingLot(
        id=uuid4(),
        batch_id=sentinel_batch.id,
        package_lot_code=f"SENTINEL-PKG-{uuid4().hex[:8]}",
        quantity=10,
        unit=PackagingUnit.JARS,
        package_size_grams=500.0,
    )
    session.add(sentinel_pkg)
    session.commit()

    sentinel_audit = AuditEvent(
        id=uuid4(),
        event_type="SENTINEL_EVENT",
        entity_type="PACKAGING_LOT",
        entity_id=sentinel_pkg.id,
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

        surviving_batch = session.get(Batch, sentinel_batch.id)
        assert surviving_batch is not None
        assert surviving_batch.id == sentinel_batch.id

        surviving_pkg = session.get(PackagingLot, sentinel_pkg.id)
        assert surviving_pkg is not None
        assert surviving_pkg.id == sentinel_pkg.id

        surviving_audit = session.get(AuditEvent, sentinel_audit.id)
        assert surviving_audit is not None
        assert surviving_audit.id == sentinel_audit.id
    finally:
        session.execute(delete(AuditEvent).where(AuditEvent.id == sentinel_audit.id))
        session.execute(delete(PackagingLot).where(PackagingLot.id == sentinel_pkg.id))
        session.execute(delete(Batch).where(Batch.id == sentinel_batch.id))
        session.execute(delete(User).where(User.id == sentinel_user.id))
        session.commit()
