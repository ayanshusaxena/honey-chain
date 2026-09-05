"""Blockchain configuration and domain exception definitions."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BlockchainSettings(BaseSettings):
    """Runtime configuration for blockchain integration."""

    enabled: bool = False
    rpc_url: str | None = None
    contract_address: str | None = None
    chain_id: int | None = None
    network_name: str = "unconfigured"
    private_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_prefix="HONEY_CHAIN_BLOCKCHAIN_",
        extra="ignore",
    )

    def is_configured(self) -> bool:
        """Return True only if blockchain is explicitly enabled and minimally configured."""
        return bool(self.enabled and self.rpc_url and self.contract_address)


# ===========================================================================
# Domain Exceptions
# ===========================================================================

class BlockchainError(Exception):
    """Base exception for all blockchain-related failures."""


class BlockchainNotConfiguredError(BlockchainError):
    """Raised when blockchain operation is requested without required configuration."""


class BlockchainClientError(BlockchainError):
    """Raised when the underlying blockchain client / RPC call fails."""


class BlockchainTransactionError(BlockchainError):
    """Raised when a blockchain transaction is reverted or fails execution."""
