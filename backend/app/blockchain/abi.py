"""Contract ABI representation for HoneyTraceability.

Source / Provenance:
- Contract: contracts/HoneyTraceability.sol
- Compiled Artifact: blockchain/artifacts/contracts/HoneyTraceability.sol/HoneyTraceability.json
- Solidity Version: ^0.8.24 / ^0.8.28 (OpenZeppelin Ownable 5.x)
- Generated: Chunk 11 Phase 1 Integration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ABI_FILE = Path(__file__).resolve().parent / "abi.json"

with open(_ABI_FILE, encoding="utf-8") as _f:
    HONEY_TRACEABILITY_ABI: list[dict[str, Any]] = json.load(_f)

__all__ = ["HONEY_TRACEABILITY_ABI"]
