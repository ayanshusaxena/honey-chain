/**
 * Honey Chain Shared Contract Types
 * 
 * Technical Authority: Sealed Backend Source (commit a4d794eafa56274308e500ec99ac3cd95322ab2c)
 * Domain Coverage: Auth, Hives, Telemetry, Risk, Harvests, Collection Lots, Batches, Lab Evidence
 */

// ============================================================================
// Bounded Enums (app/models/enums.py)
// ============================================================================

export type UserRole = "ADMIN" | "BEEKEEPER" | "PROCESSOR";

export type HiveStatus = "ACTIVE" | "INACTIVE" | "MAINTENANCE";

export type TelemetryQuality = "VALID" | "SUSPECT" | "INVALID";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type RiskSource = "AI_MODEL" | "RULE_ENGINE" | "HYBRID";

export type BatchStatus = "ACTIVE" | "HOLD" | "RECALL";

export type LabEvidenceStatus = "ACTIVE" | "SUPERSEDED" | "REVOKED";

export type BlockchainStatus = "PENDING" | "CONFIRMED" | "FAILED";

export type PackagingUnit = "BOTTLES" | "JARS" | "PACKS" | "POUCHES";

export type QrStatus = "ACTIVE" | "REVOKED";

// ============================================================================
// 1. Auth Domain
// ============================================================================

export interface LoginCredentials {
  username: string; // Email or username (OAuth2PasswordRequestForm)
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface UserSummary {
  id: string; // UUID
  name: string;
  email: string;
  role: UserRole;
}

export interface UserProfile extends UserSummary {
  is_active: boolean;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

// ============================================================================
// 2. Hives Domain
// ============================================================================

export interface BeekeeperSummary {
  id: string; // UUID
  name: string;
  email: string;
  role: UserRole;
}

export interface HiveCreate {
  hive_code: string;
  location_region: string;
  beekeeper_id?: string | null; // UUID (Required for ADMIN, forbidden for BEEKEEPER if different)
  status?: HiveStatus;
  is_active?: boolean;
}

export interface HiveUpdate {
  location_region?: string | null;
  status?: HiveStatus | null;
  is_active?: boolean | null;
}

export interface HiveResponse {
  id: string; // UUID
  hive_code: string;
  beekeeper_id: string; // UUID
  location_region: string;
  status: HiveStatus;
  is_active: boolean;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  beekeeper?: BeekeeperSummary | null;
}

// ============================================================================
// 3. Telemetry Domain
// ============================================================================

export interface TelemetryBase {
  device_timestamp: string; // ISO datetime (must include timezone)
  weight_kg: number;
  temperature_c: number;
  humidity_pct: number;
  quality?: TelemetryQuality;
}

export interface TelemetryCreate extends TelemetryBase {
  hive_id: string; // UUID
}

export type HiveTelemetryCreate = TelemetryBase;

export interface TelemetryResponse {
  id: string; // UUID
  hive_id: string; // UUID
  device_timestamp: string; // ISO datetime
  received_at: string; // ISO datetime
  weight_kg: number;
  temperature_c: number;
  humidity_pct: number;
  quality: TelemetryQuality;
}

// ============================================================================
// 4. Risk Domain
// ============================================================================

export interface RiskEvaluationCreate {
  telemetry_id?: string | null; // UUID (optional, defaults to latest non-INVALID)
}

export interface RiskEventResponse {
  id: string; // UUID
  hive_id: string; // UUID
  telemetry_id: string | null; // UUID
  evaluated_at: string; // ISO datetime
  risk_score: number; // 0.0 to 1.0
  risk_level: RiskLevel;
  reason: string;
  source: RiskSource;
  model_name: string | null;
  model_version: string | null;
  created_at: string; // ISO datetime
}

// ============================================================================
// 5. Harvests Domain
// ============================================================================

export interface HarvestCreate {
  harvest_code: string;
  harvest_date: string; // YYYY-MM-DD
  quantity_kg: number;
  notes?: string | null;
  beekeeper_id?: string | null; // UUID (Required for ADMIN, auto for BEEKEEPER)
}

export interface HiveAllocationCreate {
  hive_id: string; // UUID
  quantity_used_kg: number;
}

export interface HiveAllocationResponse {
  hive_id: string; // UUID
  hive_code: string;
  location_region: string;
  quantity_used_kg: number;
}

export interface HarvestResponse {
  id: string; // UUID
  harvest_code: string;
  harvest_date: string; // YYYY-MM-DD
  quantity_kg: number;
  notes: string | null;
  created_by_id: string; // UUID
  is_finalized: boolean;
  finalized_at: string | null; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface HarvestDetailResponse extends HarvestResponse {
  allocated_quantity_kg: number;
  hives: HiveAllocationResponse[];
}

// ============================================================================
// 6. Collection Lots Domain
// ============================================================================

export interface CollectionLotCreate {
  lot_code: string;
  quantity_kg: number;
}

export interface HarvestAllocationCreate {
  harvest_id: string; // UUID
  quantity_used_kg: number;
}

export interface HarvestAllocationResponse {
  harvest_id: string; // UUID
  harvest_code: string;
  quantity_used_kg: number;
}

export interface CollectionLotResponse {
  id: string; // UUID
  lot_code: string;
  quantity_kg: number;
  is_finalized: boolean;
  finalized_at: string | null; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface CollectionLotDetailResponse extends CollectionLotResponse {
  allocated_quantity_kg: number;
  harvests: HarvestAllocationResponse[];
}

// ============================================================================
// 7. Processing Batches Domain
// ============================================================================

export interface BatchCreate {
  batch_code: string;
  processor_id?: string | null; // UUID (Required for ADMIN, auto for PROCESSOR)
}

export interface CollectionLotAllocationCreate {
  collection_lot_id: string; // UUID
  quantity_used_kg: number;
}

export interface BatchStatusUpdate {
  status: BatchStatus; // ACTIVE, HOLD, RECALL (ADMIN only, batch must be finalized)
}

export interface BatchResponse {
  id: string; // UUID
  batch_code: string;
  processor_id: string; // UUID
  status: BatchStatus;
  is_finalized: boolean;
  finalized_at: string | null; // ISO datetime
  derived_quantity_kg: number; // Dynamically computed from sum of allocated lots
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface HiveLineageInBatch {
  hive_id: string; // UUID
  hive_code: string;
  location_region: string;
  quantity_used_kg: number;
}

export interface HarvestLineageInBatch {
  harvest_id: string; // UUID
  harvest_code: string;
  harvest_date: string; // YYYY-MM-DD
  quantity_used_kg: number;
  hives: HiveLineageInBatch[];
}

export interface CollectionLotLineageInBatch {
  collection_lot_id: string; // UUID
  lot_code: string;
  quantity_used_kg: number;
  harvests: HarvestLineageInBatch[];
}

export interface BatchDetailResponse extends BatchResponse {
  collection_lots: CollectionLotLineageInBatch[];
}

// ============================================================================
// 8. Lab Evidence Domain
// ============================================================================

export interface LabEvidenceUploadData {
  certificate_id: string;
  test_summary: string;
  file: File;
}

export interface LabEvidenceResponse {
  id: string; // UUID
  batch_id: string; // UUID
  certificate_id: string;
  test_summary: string;
  file_name: string;
  file_hash_sha256: string; // 64-char lowercase hex
  status: LabEvidenceStatus;
  uploaded_at: string; // ISO datetime
}

export interface LabEvidenceVerifyResponse {
  id: string; // UUID
  evidence_id: string; // UUID
  batch_id: string; // UUID
  certificate_id: string;
  file_name: string;
  file_hash_sha256: string;
  computed_hash_sha256: string;
  is_hash_verified: boolean;
  is_verified: boolean;
  status: LabEvidenceStatus;
  claim: string;
  claim_statement: string;
}
