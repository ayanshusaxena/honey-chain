# Honey Chain (SIH 2026 - PS 26021)
> End-to-End Honey Supply Chain Traceability, Quality Verification, and Consumer Trust Platform

Honey Chain is an open-source prototype platform designed for Smart India Hackathon 2026 (Problem Statement 26021). It establishes a transparent, tamper-evident custody chain for raw honey from beekeeper hives to retail packaging, combining IoT telemetry anomaly screening, cryptographic lab evidence verification, dual off-chain/on-chain audit trails, and unique, hash-only consumer QR verification with dynamic status updates.

---

## 1. MVP Purpose & Architecture

### Core Design Philosophy: Dual-Layer Truth
Honey Chain separates operational business workflows from cryptographic proof notarization:

```
[ Beekeeper Hive ] -> [ IoT Telemetry ] -> [ Rule-Based Risk Engine ]
         |
         v
  [ Raw Harvest ]  ->  [ Collection Lot ]  ->  [ Processing Batch ]
                                                      |
                                      +---------------+---------------+
                                      |                               |
                                      v                               v
                             [ Lab Evidence PDF ]         [ Blockchain Notary ]
                             (SHA-256 Digest)            (HoneyTraceability.sol)
                                      |                               |
                                      +---------------+---------------+
                                                      |
                                                      v
                                             [ Packaging Lot ]
                                                      |
                                                      v
                                            [ Unique QR Token ]
                                                      |
                                                      v
                                         [ Consumer Verification ]
                                            (Public-Safe DTO)
```

1. **PostgreSQL as Operational Source of Truth**:
   - Serves all transactional business logic, relational mappings, and operational state.
   - Enforces strict foreign-key integrity, multi-stage volume conservation (preventing oversubscription), row-level concurrency locking (`FOR UPDATE`), and role-based access control (`ADMIN`, `BEEKEEPER`, `PROCESSOR`).
2. **FastAPI Backend Service**:
   - Python-based asynchronous REST API with structured domain layering (Auth, Hives, Telemetry, Risk, Traceability, Lab Evidence, Packaging, QR, Blockchain).
   - JWT bearer authentication with role-based permissions.
   - Immutable audit log (`audit_events`) tracking authenticated actor UUIDs across all operational lifecycle events.
3. **Blockchain as Immutable Notary & Evidence Layer**:
   - Ethereum JSON-RPC adapter interfacing with a local EVM runtime (`HoneyTraceability.sol` on Hardhat).
   - Records cryptographic proofs: on-chain batch identity (`registerBatch`) and exact 32-byte SHA-256 digests of verified digital lab reports (`addEvidence`).
   - Functions strictly as an append-only evidence witness and receipt log; does **not** replace PostgreSQL as the operational source of truth, nor does it automate business logic or governance.
   - Off-chain operations proceed cleanly when blockchain is disabled; when enabled, on-chain transactions provide independent third-party verification receipts.
4. **Rule-Based Risk Screening Engine**:
   - Evaluates incoming IoT hive telemetry against deterministic agronomic thresholds (temperature, humidity, weight changes).
   - Operates strictly as a prototype risk observation/anomaly screening tool; does **not** provide clinical veterinary, disease, or biological diagnosis.
   - Does **not** possess authority to transition batch business statuses; all administrative HOLD and RECALL actions require explicit intervention by an authorized `ADMIN`.

---

## 2. Technology Stack & Prerequisites

| Layer | Technology | Minimum Version |
| :--- | :--- | :--- |
| **Backend Runtime** | Python (FastAPI, SQLAlchemy 2.0, Pydantic v2, Web3.py) | Python 3.11+ |
| **Database** | PostgreSQL with `psycopg` (v3) driver | PostgreSQL 14+ |
| **Migrations** | Alembic | Latest |
| **Smart Contract** | Solidity 0.8.24 (OpenZeppelin Contracts v5) | Solc 0.8.24 |
| **Local EVM Node** | Hardhat (TypeScript) | Node.js 18+, npm 9+ |

---

## 3. Local Environment Setup

### A. Clone Repository
```powershell
git clone https://github.com/ayanshusaxena/honey-chain.git
cd honey-chain
```

### B. PostgreSQL Database Setup
Ensure PostgreSQL is running locally on port 5432 and create the application database and user:
```sql
CREATE USER honey_chain_app WITH PASSWORD 'your_secure_password';
CREATE DATABASE honey_chain OWNER honey_chain_app;
```

### C. Backend Setup
1. Create and activate a Python virtual environment:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   Copy `.env.example` to `.env`:
   ```powershell
   cp .env.example .env
   ```
   Edit `backend/.env` with your local settings:
   ```env
   HONEY_CHAIN_DATABASE_URL=postgresql+psycopg://honey_chain_app:your_secure_password@localhost:5432/honey_chain
   HONEY_CHAIN_JWT_SECRET=your-secure-random-jwt-secret-at-least-32-chars-long
   HONEY_CHAIN_DEMO_PASSWORD=your_secure_demo_password
   HONEY_CHAIN_PUBLIC_ORIGIN=http://localhost:8000
   ```
4. Run database migrations:
   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

---

## 4. Local EVM Blockchain Setup (Optional)

To enable real on-chain transaction execution and audit verification:

1. **Install Blockchain Dependencies & Start Local Node**:
   In a separate terminal window:
   ```powershell
   cd blockchain
   npm install
   npx hardhat node
   ```
   *The node will run on `http://127.0.0.1:8545` with Chain ID `31337` and 20 pre-funded test accounts.*

2. **Deploy the `HoneyTraceability` Contract**:
   In another terminal:
   ```powershell
   cd blockchain
   npx hardhat run scripts/deploy.ts --network localhost
   ```
   *Default deployed contract address: `0x5FbDB2315678afecb367f032d93F642f64180aa3`.*

3. **Configure Blockchain in `backend/.env`**:
   Add the local Hardhat parameters to `backend/.env`:
   ```env
   HONEY_CHAIN_BLOCKCHAIN_ENABLED=true
   HONEY_CHAIN_BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545
   HONEY_CHAIN_BLOCKCHAIN_CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
   HONEY_CHAIN_BLOCKCHAIN_CHAIN_ID=31337
   HONEY_CHAIN_BLOCKCHAIN_NETWORK_NAME=localhost
   HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY=<local-hardhat-account-private-key>
   ```
   *(Note: Set `HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY` to one of the development private keys output by `npx hardhat node`, such as Account #0).*

---

## 5. Running the Backend Server

Start the FastAPI application with Uvicorn:
```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Documentation (ReDoc)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: `GET http://127.0.0.1:8000/health`

---

## 6. Deterministic Demo Bootstrap & Safe Reset

The project includes an end-to-end demo bootstrap utility that creates a complete, verified honey journey without manual data entry.

### A. Run Demo Bootstrap (Off-Chain Mode)
Seeds demo users, creates a hive, telemetry, risk assessment, harvest, collection lot, batch, lab evidence PDF, packaging lot, and unique hash-only QR token:
```powershell
cd backend
.\.venv\Scripts\python.exe -m app.demo.bootstrap
```

### B. Run Demo Bootstrap with Real EVM Transactions
Executes the full journey AND mines real `registerBatch` and `addEvidence` transactions on the local Hardhat node:
```powershell
cd backend
.\.venv\Scripts\python.exe -m app.demo.bootstrap --with-blockchain
```

### C. Safe Demo Reset Only
Removes all `DEMO-*` records in strict foreign-key dependency order without touching any operational data:
```powershell
cd backend
.\.venv\Scripts\python.exe -m app.demo.bootstrap --reset-only
```

### Output Example
```text
--- DEMO DATASET INITIALIZED SUCCESSFULLY ---
Disclaimed:     DEMO / SYNTHETIC DATASET: All data in this record is simulated...
Hive:           DEMO-HIV-001 (DEMO / SIMULATED - Kashmir Valley Demonstration Apiary)
Harvest:        DEMO-HRV-001 (60 kg)
Collection Lot: DEMO-LOT-001 (60 kg)
Batch:          DEMO-BAT-001 (60.0 kg)
Lab Evidence:   DEMO-CERT-001 (SHA-256: cd5a7871fc7db50c...)
Packaging Lot:  DEMO-PKG-001 (50.0 kg)
QR Token Status:VERIFIED
------------------------------------------------------------
OPERATOR DEMO VERIFICATION URL (EPHEMERAL RAW TOKEN):
  http://localhost:8000/verify/58a62eae3383a68d87076e47f1ad152e2ef6145653d5dd9a8858d46551381667
------------------------------------------------------------
```

---

## 7. Packaging QR Generation & Public Consumer Verification

### Security & Token Lifecycle Design
- **Single-Issuance per Packaging Lot**: Exactly one QR token can be generated per retail packaging lot (enforced by a database `unique` constraint on `packaging_lot_id`). Attempting to issue a second token for the same lot raises HTTP `409 Conflict`.
- **Hash-Only Persistence**: The 256-bit cryptographically secure raw token (`secrets.token_hex(32)`) is delivered once to the packaging operator upon creation and is **never** stored in plaintext in the database or on disk. Only its cryptographic SHA-256 digest (`token_hash`) is persisted in `qr_tokens`.
- **Reusable, Idempotent Verification**: The consumer verification endpoint `GET /verify/{raw_token}` is an idempotent read operation. It does **not** burn or consume the token on first scan, allowing consumers, retailers, and auditors to verify product authenticity at any point throughout the product's shelf life.
- **Dynamic Batch Lifecycle Reflection**: Verification resolves the live batch status dynamically in real time:
  - `ACTIVE` → Displays status `VERIFIED` with complete provenance, lab evidence, and blockchain notary receipts.
  - `HOLD` → Displays status `HOLD` with alert warning: *"Notice: This honey batch is currently on administrative HOLD. Distribution is temporarily paused."*
  - `RECALL` → Displays status `RECALLED` with critical alert: *"WARNING: This honey batch has been RECALLED. Do not consume this product."*
- **Administrative Revocation**: Authorized administrators can permanently invalidate a compromised or damaged token via `POST /qr/{qr_id}/revoke`. Revoked tokens return HTTP `410 Gone`.
- **Physical Label Tamper Boundary**: While cryptographic tokens prevent digital forgery and database breach exploitation, software-level QR codes cannot physically prevent bad actors from copying or re-printing physical labels in an unmonitored retail environment.

### Batch Lifecycle & Administrative Governance
Batch status transitions follow a strict administrative state machine:
- `ACTIVE` → `HOLD` → `ACTIVE` is permitted (e.g. pending quality audits or cleared investigations).
- `ACTIVE` → `RECALL` is permitted.
- `RECALL` is **strictly terminal** and cannot be transitioned back to `ACTIVE` or `HOLD`.
- Status transitions are restricted exclusively to authenticated `ADMIN` users (`PATCH /batches/{batch_id}/status`).
- Neither the AI/risk evaluation engine nor the blockchain smart contract has authority to change operational batch states.

---

## 8. Automated Testing & Verification

The project enforces continuous quality gates across all domains:

```powershell
# Run entire backend test suite (192 tests)
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Run live real-EVM blockchain tests
.\.venv\Scripts\python.exe -m pytest tests/test_blockchain_live.py -v

# Run demo bootstrap repeatability & sentinel safety tests
.\.venv\Scripts\python.exe -m pytest tests/test_demo_bootstrap.py -v

# Verify zero database schema drift
.\.venv\Scripts\python.exe -m alembic check

# Verify Python syntax and bytecode compilation
.\.venv\Scripts\python.exe -m compileall app tests
```

---

## 9. Demo Data Disclaimer & Scope Boundaries

### Synthetic Data Notice
All data created by the demo bootstrap (`DEMO-*` codes, simulated temperatures/weights, Kashmiri Acacia honey purity parameters, and C4 screening values) are purely synthetic demonstration fixtures created solely for SIH 2026 PS 26021. They do NOT represent real-world commercial lab certificates, biological diagnostics, or registered agricultural facilities.

### MVP Scope & Known Limitations
- **Cryptographic Notarization vs. Chemical Truth**: The SHA-256 digest recorded on PostgreSQL and notarized on the EVM blockchain establishes digital integrity and evidence identity for the PDF lab report file; it does **not** scientifically prove the chemical correctness of the lab tests or guarantee biological honey purity.
- **Local EVM Demonstration Runtime**: The blockchain evidence layer is designed and validated against local Hardhat nodes (`http://127.0.0.1:8545`, Chain ID `31337`). It is not deployed to public Ethereum mainnets or government blockchains, and does not replace PostgreSQL as the operational source of truth.
- **Risk Screening Engine**: The risk evaluation engine uses deterministic prototype threshold rules for demonstration; it does **not** constitute a clinical veterinary or biological disease diagnostic tool, nor does it possess authority over business state transitions.
- **Artifact Storage**: Lab certificate PDF files are stored on the local filesystem (`backend/uploads/`); cloud object storage (S3/GCS/IPFS) is not configured in this MVP build.
- **No Production Overclaiming**: This platform is an educational and hackathon demonstration prototype.
