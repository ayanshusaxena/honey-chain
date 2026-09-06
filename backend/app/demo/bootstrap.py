"""Deterministic demo bootstrap and safe reset for the Honey Chain MVP.

Provides a reproducible, claim-safe, clearly labelled synthetic dataset spanning the
complete journey:
  Demo Users (Admin, Beekeeper, Processor)
  -> Hive (DEMO-HIV-001)
  -> Telemetry (Simulated valid IoT signals)
  -> Deterministic Risk Evaluation (LOW risk)
  -> Harvest (DEMO-HRV-001, finalized)
  -> Collection Lot (DEMO-LOT-001, finalized)
  -> Processing Batch (DEMO-BAT-001, finalized)
  -> Lab Evidence (DEMO-CERT-001 with synthetic PDF & verified SHA-256)
  -> Real Local Blockchain Records (if EVM configured / requested)
  -> Packaging Lot (DEMO-PKG-001, 100 jars * 500g = 50kg)
  -> Single-Use QR Token (ephemeral raw token, hash-only persistence)
  -> Consumer-Ready Public Verification
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import io
import os
from pathlib import Path
import socket
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.seed import DEMO_USERS, seed_demo_users
from app.auth.service import normalize_email
from app.blockchain.adapter import EthereumJsonRpcAdapter
from app.blockchain.config import BlockchainSettings
from app.blockchain.service import BlockchainService
from app.core.config import settings
from app.core.database import SessionLocal
from app.hives.schemas import HiveCreate
from app.hives.service import create_hive
from app.lab.service import (
    STORAGE_DIR as LAB_STORAGE_DIR,
    create_lab_evidence,
    verify_lab_evidence_hash,
)
from app.models.audit import AuditEvent
from app.models.enums import (
    BatchStatus,
    HiveStatus,
    LabEvidenceStatus,
    PackagingUnit,
    QrStatus,
    TelemetryQuality,
    UserRole,
)
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, Hive, HiveHarvest, RiskEvent, Telemetry
from app.models.identity import User
from app.models.traceability import (
    Batch,
    BatchCollectionLot,
    CollectionLot,
    CollectionLotHarvest,
)
from app.packaging.schemas import PackagingLotCreate
from app.packaging.service import create_packaging_lot
from app.qr.service import generate_qr_token, verify_consumer_token
from app.risk.service import evaluate_hive_risk
from app.telemetry.schemas import TelemetryBase
from app.telemetry.service import create_telemetry
from app.traceability.schemas import (
    BatchCreate,
    CollectionLotAllocationCreate,
    CollectionLotCreate,
    HarvestAllocationCreate,
    HarvestCreate,
    HiveAllocationCreate,
)
from app.traceability.service import (
    add_collection_lot_allocation,
    add_harvest_allocation,
    add_hive_allocation,
    create_batch,
    create_collection_lot,
    create_harvest,
    finalize_batch,
    finalize_collection_lot,
    finalize_harvest,
)

# Deterministic demo naming and prefix boundaries
DEMO_PREFIX = "DEMO-"
DEMO_HIVE_CODE = "DEMO-HIV-001"
DEMO_HARVEST_CODE = "DEMO-HRV-001"
DEMO_LOT_CODE = "DEMO-LOT-001"
DEMO_BATCH_PREFIX = "DEMO-BAT-"
DEMO_CERT_PREFIX = "DEMO-CERT-"
DEMO_PKG_PREFIX = "DEMO-PKG-"

DEMO_ADMIN_EMAIL = "demo.admin@honeychain.local"
DEMO_BEEKEEPER_EMAIL = "demo.beekeeper@honeychain.local"
DEMO_PROCESSOR_EMAIL = "demo.processor@honeychain.local"
DEFAULT_DEMO_PASSWORD = "DemoSecret123!"

SYNTHETIC_DISCLAIMER = (
    "DEMO / SYNTHETIC DATASET: All data in this record is simulated for prototype "
    "demonstration purposes only (SIH 2026 PS 26021). Not valid for commercial, clinical, "
    "or regulatory use."
)


@dataclass
class DemoBootstrapResult:
    """Encapsulates the complete result of a deterministic demo bootstrap run."""

    admin_id: UUID
    admin_email: str
    beekeeper_id: UUID
    beekeeper_email: str
    processor_id: UUID
    processor_email: str
    hive_id: UUID
    hive_code: str
    hive_region: str
    telemetry_id: UUID
    risk_event_id: UUID
    risk_level: str
    harvest_id: UUID
    harvest_code: str
    harvest_quantity_kg: float
    collection_lot_id: UUID
    lot_code: str
    lot_quantity_kg: float
    batch_id: UUID
    batch_code: str
    batch_derived_quantity_kg: float
    lab_evidence_id: UUID
    certificate_id: str
    file_hash_sha256: str
    blockchain_records: list[dict[str, str]]
    blockchain_status: str
    packaging_lot_id: UUID
    package_lot_code: str
    packaged_quantity_kg: float
    qr_token_id: UUID
    verification_url: str
    raw_verification_token: str
    consumer_verification_status: str
    synthetic_disclaimer: str = SYNTHETIC_DISCLAIMER


def is_node_online(rpc_url: str) -> bool:
    """Check if the local EVM JSON-RPC port is accepting TCP connections."""
    try:
        parsed = urlparse(rpc_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8545
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def reset_demo_data(session: Session) -> dict[str, int]:
    """Safely delete ONLY records owned by the demo dataset in strict foreign key order.

    GUARANTEES:
    - Never deletes or touches operational / sentinel records.
    - Scoped strictly to entities with DEMO- codes or demo user associations.
    - Zero global TRUNCATE or DROP calls.
    - Removes demo-generated PDF certificate files.
    """
    counts: dict[str, int] = {}

    # 1. Discover demo-owned parent IDs
    demo_pkg_ids = session.scalars(
        select(PackagingLot.id).where(PackagingLot.package_lot_code.like(f"{DEMO_PREFIX}%"))
    ).all()
    demo_batch_ids = session.scalars(
        select(Batch.id).where(Batch.batch_code.like(f"{DEMO_PREFIX}%"))
    ).all()
    demo_lab_ids = session.scalars(
        select(LabEvidence.id).where(LabEvidence.certificate_id.like(f"{DEMO_PREFIX}%"))
    ).all()
    demo_lot_ids = session.scalars(
        select(CollectionLot.id).where(CollectionLot.lot_code.like(f"{DEMO_PREFIX}%"))
    ).all()
    demo_harvest_ids = session.scalars(
        select(Harvest.id).where(Harvest.harvest_code.like(f"{DEMO_PREFIX}%"))
    ).all()
    demo_hive_ids = session.scalars(
        select(Hive.id).where(Hive.hive_code.like(f"{DEMO_PREFIX}%"))
    ).all()

    demo_qr_ids = (
        session.scalars(select(QrToken.id).where(QrToken.packaging_lot_id.in_(demo_pkg_ids))).all()
        if demo_pkg_ids
        else []
    )

    bc_conditions = []
    if demo_batch_ids:
        bc_conditions.append(BlockchainRecord.batch_id.in_(demo_batch_ids))
    if demo_lab_ids:
        bc_conditions.append(BlockchainRecord.lab_evidence_id.in_(demo_lab_ids))
    demo_bc_ids = (
        session.scalars(select(BlockchainRecord.id).where(or_(*bc_conditions))).all()
        if bc_conditions
        else []
    )

    all_demo_entity_ids = (
        set(demo_pkg_ids)
        | set(demo_batch_ids)
        | set(demo_lab_ids)
        | set(demo_lot_ids)
        | set(demo_harvest_ids)
        | set(demo_hive_ids)
        | set(demo_qr_ids)
        | set(demo_bc_ids)
    )

    # 2. Cascade deletions in strict reverse dependency order
    if demo_qr_ids:
        res = session.execute(delete(QrToken).where(QrToken.id.in_(demo_qr_ids)))
        counts["qr_tokens"] = res.rowcount

    if demo_bc_ids:
        res = session.execute(delete(BlockchainRecord).where(BlockchainRecord.id.in_(demo_bc_ids)))
        counts["blockchain_records"] = res.rowcount

    if demo_pkg_ids:
        res = session.execute(delete(PackagingLot).where(PackagingLot.id.in_(demo_pkg_ids)))
        counts["packaging_lots"] = res.rowcount

    if demo_lab_ids:
        res = session.execute(delete(LabEvidence).where(LabEvidence.id.in_(demo_lab_ids)))
        counts["lab_evidence"] = res.rowcount

    if all_demo_entity_ids:
        res = session.execute(
            delete(AuditEvent).where(AuditEvent.entity_id.in_(list(all_demo_entity_ids)))
        )
        counts["audit_events"] = res.rowcount

    if demo_batch_ids or demo_lot_ids:
        bcl_conditions = []
        if demo_batch_ids:
            bcl_conditions.append(BatchCollectionLot.batch_id.in_(demo_batch_ids))
        if demo_lot_ids:
            bcl_conditions.append(BatchCollectionLot.collection_lot_id.in_(demo_lot_ids))
        res = session.execute(delete(BatchCollectionLot).where(or_(*bcl_conditions)))
        counts["batch_collection_lots"] = res.rowcount

    if demo_batch_ids:
        res = session.execute(delete(Batch).where(Batch.id.in_(demo_batch_ids)))
        counts["batches"] = res.rowcount

    if demo_lot_ids or demo_harvest_ids:
        clh_conditions = []
        if demo_lot_ids:
            clh_conditions.append(CollectionLotHarvest.collection_lot_id.in_(demo_lot_ids))
        if demo_harvest_ids:
            clh_conditions.append(CollectionLotHarvest.harvest_id.in_(demo_harvest_ids))
        res = session.execute(delete(CollectionLotHarvest).where(or_(*clh_conditions)))
        counts["collection_lot_harvests"] = res.rowcount

    if demo_lot_ids:
        res = session.execute(delete(CollectionLot).where(CollectionLot.id.in_(demo_lot_ids)))
        counts["collection_lots"] = res.rowcount

    if demo_hive_ids or demo_harvest_ids:
        hh_conditions = []
        if demo_hive_ids:
            hh_conditions.append(HiveHarvest.hive_id.in_(demo_hive_ids))
        if demo_harvest_ids:
            hh_conditions.append(HiveHarvest.harvest_id.in_(demo_harvest_ids))
        res = session.execute(delete(HiveHarvest).where(or_(*hh_conditions)))
        counts["hive_harvests"] = res.rowcount

    if demo_harvest_ids:
        res = session.execute(delete(Harvest).where(Harvest.id.in_(demo_harvest_ids)))
        counts["harvests"] = res.rowcount

    if demo_hive_ids:
        res_risk = session.execute(delete(RiskEvent).where(RiskEvent.hive_id.in_(demo_hive_ids)))
        counts["risk_events"] = res_risk.rowcount

        res_tel = session.execute(delete(Telemetry).where(Telemetry.hive_id.in_(demo_hive_ids)))
        counts["telemetry"] = res_tel.rowcount

        res_hiv = session.execute(delete(Hive).where(Hive.id.in_(demo_hive_ids)))
        counts["hives"] = res_hiv.rowcount

    session.commit()

    # 3. Clean up physical lab files matching demo certificate IDs
    if LAB_STORAGE_DIR.exists():
        for file_path in LAB_STORAGE_DIR.glob(f"*{DEMO_PREFIX}*"):
            try:
                file_path.unlink()
            except OSError:
                pass

    return counts


def _get_or_create_demo_users(session: Session, password: str) -> tuple[User, User, User]:
    """Ensure standard demo users exist and return (admin, beekeeper, processor)."""
    admin_email = normalize_email(DEMO_ADMIN_EMAIL)
    bk_email = normalize_email(DEMO_BEEKEEPER_EMAIL)
    proc_email = normalize_email(DEMO_PROCESSOR_EMAIL)

    admin = session.scalar(select(User).where(func.lower(User.email) == admin_email))
    beekeeper = session.scalar(select(User).where(func.lower(User.email) == bk_email))
    processor = session.scalar(select(User).where(func.lower(User.email) == proc_email))

    if admin is None or beekeeper is None or processor is None:
        seed_demo_users(session, password)
        admin = session.scalar(select(User).where(func.lower(User.email) == admin_email))
        beekeeper = session.scalar(select(User).where(func.lower(User.email) == bk_email))
        processor = session.scalar(select(User).where(func.lower(User.email) == proc_email))

    if admin is None or beekeeper is None or processor is None:
        raise RuntimeError("Failed to initialize required demo users.")

    return admin, beekeeper, processor


def _determine_demo_batch_code(
    session: Session,
    include_blockchain: bool,
    run_id: str | None = None,
) -> str:
    """Determine a deterministic demo batch code that avoids on-chain revert collisions."""
    if run_id:
        return f"{DEMO_BATCH_PREFIX}{run_id}"

    base_code = f"{DEMO_BATCH_PREFIX}001"
    if not include_blockchain:
        return base_code

    # If blockchain is active, check if base_code already exists on-chain
    bc_settings = BlockchainSettings()
    if not bc_settings.is_configured():
        return base_code

    try:
        adapter = EthereumJsonRpcAdapter(settings=bc_settings)
        if adapter.is_configured():
            _, contract, _, _, _ = adapter._get_context()
            for idx in range(1, 1000):
                candidate = f"{DEMO_BATCH_PREFIX}{idx:03d}"
                data = contract.functions.getBatch(candidate).call()
                exists = bool(data[5])
                if not exists:
                    return candidate
    except Exception:
        pass

    return base_code


def bootstrap_demo_dataset(
    session: Session,
    include_blockchain: bool = False,
    public_origin: str = "http://localhost:8000",
    run_id: str | None = None,
) -> DemoBootstrapResult:
    """Execute the end-to-end deterministic demo bootstrap workflow.

    Workflow:
    1. Safely reset existing demo-owned state (reconciliation).
    2. Seed / retrieve demo users (Admin, Beekeeper, Processor).
    3. Create Demo Hive with Kashmir Valley demonstration apiary.
    4. Ingest simulated IoT telemetry.
    5. Execute deterministic AI/Rule-based risk evaluation.
    6. Create, allocate, and finalize Demo Harvest (60.0 kg).
    7. Create, allocate, and finalize Demo Collection Lot (60.0 kg).
    8. Create, allocate, and finalize Demo Processing Batch (60.0 kg).
    9. Upload and verify Demo Lab Evidence PDF with synthetic watermark & SHA-256.
    10. Execute real local EVM transactions (if include_blockchain=True).
    11. Create Demo Packaging Lot (100 jars * 500g = 50.0 kg).
    12. Generate single-use QR Token (hash-only storage in PostgreSQL).
    13. Verify consumer resolution of the generated QR token.
    14. Return DemoBootstrapResult.
    """
    # Step 1: Safe reconciliation
    reset_demo_data(session)

    # Step 2: Users
    try:
        pwd = settings.demo_password_value()
    except RuntimeError:
        pwd = DEFAULT_DEMO_PASSWORD
    admin, beekeeper, processor = _get_or_create_demo_users(session, pwd)

    # Step 3: Hive
    hive_payload = HiveCreate(
        hive_code=DEMO_HIVE_CODE,
        location_region="DEMO / SIMULATED - Kashmir Valley Demonstration Apiary",
    )
    hive = create_hive(session, hive_payload, beekeeper)

    # Step 4: Telemetry
    tel_payload = TelemetryBase(
        device_timestamp=datetime.now(UTC),
        weight_kg=34.5,
        temperature_c=34.2,
        humidity_pct=55.0,
        quality=TelemetryQuality.VALID,
    )
    telemetry = create_telemetry(session, hive.id, tel_payload, beekeeper)

    # Step 5: Risk Evaluation
    risk_event = evaluate_hive_risk(session, hive.id, beekeeper, telemetry.id)

    # Step 6: Harvest
    harvest_payload = HarvestCreate(
        harvest_code=DEMO_HARVEST_CODE,
        harvest_date=date.today(),
        quantity_kg=60.0,
        notes="DEMO / SIMULATED - Raw Acacia Honey Harvest (Demonstration dataset for SIH 2026 PS 26021)",
    )
    harvest = create_harvest(session, harvest_payload, beekeeper)
    add_hive_allocation(
        session,
        harvest.id,
        HiveAllocationCreate(hive_id=hive.id, quantity_used_kg=60.0),
        beekeeper,
    )
    finalize_harvest(session, harvest.id, beekeeper)

    # Step 7: Collection Lot
    lot_payload = CollectionLotCreate(lot_code=DEMO_LOT_CODE, quantity_kg=60.0)
    lot = create_collection_lot(session, lot_payload, processor)
    add_harvest_allocation(
        session,
        lot.id,
        HarvestAllocationCreate(harvest_id=harvest.id, quantity_used_kg=60.0),
        processor,
    )
    finalize_collection_lot(session, lot.id, processor)

    # Step 8: Processing Batch
    batch_code = _determine_demo_batch_code(session, include_blockchain, run_id)
    batch_payload = BatchCreate(batch_code=batch_code)
    batch = create_batch(session, batch_payload, processor)
    add_collection_lot_allocation(
        session,
        batch.id,
        CollectionLotAllocationCreate(collection_lot_id=lot.id, quantity_used_kg=60.0),
        processor,
    )
    fin_batch = finalize_batch(session, batch.id, processor)

    # Step 9: Lab Evidence
    suffix_code = batch_code.split("-")[-1]
    cert_id = f"{DEMO_CERT_PREFIX}{suffix_code}"
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"%===========================================================================\n"
        b"% HONEY CHAIN DEMO / SYNTHETIC LABORATORY REPORT\n"
        b"% THIS IS A SIMULATED RECORD FOR PROTOTYPE DEMONSTRATION PURPOSES ONLY.\n"
        b"% NOT VALID FOR COMMERCIAL, CLINICAL, OR REGULATORY USE.\n"
        b"%===========================================================================\n"
        + f"Batch Code: {batch_code}\n".encode("utf-8")
        + f"Certificate ID: {cert_id}\n".encode("utf-8")
        + b"Product: Raw Kashmiri Acacia Honey (Synthetic Demo)\n"
        b"Floral Purity: 99.8% (Target: >= 80%) -> PASS\n"
        b"Moisture Content: 17.2% (Target: <= 20%) -> PASS\n"
        b"HMF (Hydroxymethylfurfural): 12.4 mg/kg (Target: <= 40 mg/kg) -> PASS\n"
        b"C4 Sugars: Negative (< 7%) -> PASS\n"
        b"Verification SHA-256 Digest: Computed on ingest\n"
        b"%%EOF\n"
    )
    upload_file = UploadFile(file=io.BytesIO(pdf_bytes), filename=f"{cert_id}.pdf")
    test_summary = (
        "DEMO / SIMULATED Lab Certificate - Prototype C4 sugar screening and HMF freshness "
        "analysis (Demonstration data only, not a commercial or official lab certificate)"
    )
    evidence = create_lab_evidence(
        session=session,
        batch_id=batch.id,
        certificate_id=cert_id,
        test_summary=test_summary,
        file=upload_file,
        current_user=processor,
    )
    verify_lab_evidence_hash(session, evidence.id, processor)

    # Step 10: Blockchain Records (Real Local EVM or Explicit Off-Chain Notice)
    blockchain_records: list[dict[str, str]] = []
    blockchain_status = "OFF_CHAIN_DEMO (include_blockchain=False)"

    if include_blockchain:
        bc_settings = BlockchainSettings()
        if not bc_settings.is_configured():
            raise RuntimeError(
                "Real blockchain recording was requested (include_blockchain=True), "
                "but HONEY_CHAIN_BLOCKCHAIN configuration is incomplete or disabled. "
                "Silent fallback to mock is prohibited."
            )
        if not is_node_online(bc_settings.rpc_url or "http://127.0.0.1:8545"):
            raise RuntimeError(
                f"Local EVM node at '{bc_settings.rpc_url}' is not reachable. "
                "Real local blockchain execution is required when include_blockchain=True. "
                "Silent fallback to mock is prohibited."
            )

        bc_service = BlockchainService(settings=bc_settings)
        # Register batch on-chain
        rec_batch = bc_service.register_batch_on_chain(
            session=session,
            batch_id=batch.id,
            actor_user_id=admin.id,
        )
        blockchain_records.append(
            {
                "event_type": rec_batch.event_type,
                "status": rec_batch.status.value,
                "transaction_hash": rec_batch.transaction_hash or "none",
                "block_number": str(rec_batch.block_number),
            }
        )

        # Record lab evidence on-chain
        rec_ev = bc_service.add_evidence_on_chain(
            session=session,
            evidence_id=evidence.id,
            actor_user_id=admin.id,
        )
        blockchain_records.append(
            {
                "event_type": rec_ev.event_type,
                "status": rec_ev.status.value,
                "transaction_hash": rec_ev.transaction_hash or "none",
                "block_number": str(rec_ev.block_number),
            }
        )
        blockchain_status = f"REAL_LOCAL_EVM_CONFIRMED (Contract: {rec_batch.contract_address})"

    # Step 11: Packaging Lot
    pkg_code = f"{DEMO_PKG_PREFIX}{suffix_code}"
    pkg_payload = PackagingLotCreate(
        package_lot_code=pkg_code,
        quantity=100,
        unit=PackagingUnit.JARS,
        package_size_grams=500.0,
    )
    pkg_lot = create_packaging_lot(session, batch.id, pkg_payload, processor)

    # Step 12: QR Token (Single-Use, Ephemeral Raw Token)
    qr_res = generate_qr_token(session, pkg_lot.id, processor, public_origin)
    verification_url = qr_res.verification_url
    raw_token = verification_url.split("/verify/")[-1]

    # Step 13: Verify Consumer Verification
    consumer_res = verify_consumer_token(session, raw_token)
    consumer_status = consumer_res.verification_status

    return DemoBootstrapResult(
        admin_id=admin.id,
        admin_email=admin.email,
        beekeeper_id=beekeeper.id,
        beekeeper_email=beekeeper.email,
        processor_id=processor.id,
        processor_email=processor.email,
        hive_id=hive.id,
        hive_code=hive.hive_code,
        hive_region=hive.location_region,
        telemetry_id=telemetry.id,
        risk_event_id=risk_event.id,
        risk_level=risk_event.risk_level.value,
        harvest_id=harvest.id,
        harvest_code=harvest.harvest_code,
        harvest_quantity_kg=harvest.quantity_kg,
        collection_lot_id=lot.id,
        lot_code=lot.lot_code,
        lot_quantity_kg=lot.quantity_kg,
        batch_id=batch.id,
        batch_code=batch.batch_code,
        batch_derived_quantity_kg=fin_batch.derived_quantity_kg,
        lab_evidence_id=evidence.id,
        certificate_id=evidence.certificate_id,
        file_hash_sha256=evidence.file_hash_sha256,
        blockchain_records=blockchain_records,
        blockchain_status=blockchain_status,
        packaging_lot_id=pkg_lot.id,
        package_lot_code=pkg_lot.package_lot_code,
        packaged_quantity_kg=50.0,
        qr_token_id=qr_res.id,
        verification_url=verification_url,
        raw_verification_token=raw_token,
        consumer_verification_status=consumer_status,
    )


def main() -> None:
    """CLI entrypoint for demo bootstrap and safe reset."""
    parser = argparse.ArgumentParser(
        description="Honey Chain MVP Demo Bootstrap & Safe Reset Utility",
    )
    parser.add_argument(
        "--with-blockchain",
        action="store_true",
        help="Execute real transactions against the local EVM node (requires running node).",
    )
    parser.add_argument(
        "--reset-only",
        action="store_true",
        help="Safely remove all demo-owned data without recreating new records.",
    )
    parser.add_argument(
        "--public-origin",
        default="http://localhost:8000",
        help="Public base URL for QR verification links (default: http://localhost:8000).",
    )
    args = parser.parse_args()

    if SessionLocal is None:
        raise RuntimeError("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as session:
        if args.reset_only:
            deleted = reset_demo_data(session)
            print("============================================================")
            print("HONEY CHAIN DEMO STATE RESET COMPLETE")
            print("============================================================")
            for k, v in deleted.items():
                print(f"  - {k}: {v} row(s) deleted")
            return

        print("============================================================")
        print("HONEY CHAIN MVP - DETERMINISTIC DEMO BOOTSTRAP")
        print("============================================================")
        result = bootstrap_demo_dataset(
            session=session,
            include_blockchain=args.with_blockchain,
            public_origin=args.public_origin,
        )

        print("\n--- DEMO DATASET INITIALIZED SUCCESSFULLY ---")
        print(f"Disclaimed:     {result.synthetic_disclaimer}")
        print(f"Hive:           {result.hive_code} ({result.hive_region})")
        print(f"Harvest:        {result.harvest_code} ({result.harvest_quantity_kg} kg)")
        print(f"Collection Lot: {result.lot_code} ({result.lot_quantity_kg} kg)")
        print(f"Batch:          {result.batch_code} ({result.batch_derived_quantity_kg} kg)")
        print(f"Lab Evidence:   {result.certificate_id} (SHA-256: {result.file_hash_sha256[:16]}...)")
        print(f"Blockchain:     {result.blockchain_status}")
        for r in result.blockchain_records:
            print(f"                - {r['event_type']}: {r['status']} (Tx: {r['transaction_hash'][:18]}...)")
        print(f"Packaging Lot:  {result.package_lot_code} ({result.packaged_quantity_kg} kg)")
        print(f"QR Token Status:{result.consumer_verification_status}")
        print("------------------------------------------------------------")
        print("OPERATOR DEMO VERIFICATION URL (EPHEMERAL RAW TOKEN):")
        print(f"  {result.verification_url}")
        print(f"Raw Token: {result.raw_verification_token}")
        print("------------------------------------------------------------")
        print("Note: The raw verification token is NEVER stored in PostgreSQL.")
        print("Only its cryptographic SHA-256 hash is persisted in `qr_tokens`.")
        print("============================================================")


if __name__ == "__main__":
    main()
