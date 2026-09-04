"""Bounded database enum values for the Honey Chain schema."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    BEEKEEPER = "BEEKEEPER"
    PROCESSOR = "PROCESSOR"


class HiveStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"


class TelemetryQuality(str, Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskSource(str, Enum):
    AI_MODEL = "AI_MODEL"
    RULE_ENGINE = "RULE_ENGINE"
    HYBRID = "HYBRID"


class BatchStatus(str, Enum):
    ACTIVE = "ACTIVE"
    HOLD = "HOLD"
    RECALL = "RECALL"


class LabEvidenceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class BlockchainStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PackagingUnit(str, Enum):
    BOTTLES = "BOTTLES"
    JARS = "JARS"
    PACKS = "PACKS"
    POUCHES = "POUCHES"


class QrStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
