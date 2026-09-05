"""Integration tests for EthereumJsonRpcAdapter against a live EVM node (e.g. Hardhat).

These tests run against a running JSON-RPC node (default http://127.0.0.1:8545).
If the node is not running or unreachable, tests are cleanly skipped to preserve
fast, isolated unit testing without external network/daemon requirements.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import SecretStr
import pytest
from web3 import Web3

from app.blockchain.abi import HONEY_TRACEABILITY_ABI
from app.blockchain.adapter import EthereumJsonRpcAdapter
from app.blockchain.config import BlockchainSettings
from app.blockchain.schemas import EMPTY_METADATA_HASH
from app.models.enums import BlockchainStatus

# Standard local Hardhat node account #0
DEFAULT_HARDHAT_RPC_URL = "http://127.0.0.1:8545"
DEFAULT_HARDHAT_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEFAULT_HARDHAT_DEPLOYER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
DEFAULT_CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"


def is_live_node_available(rpc_url: str) -> bool:
    """Check if the local RPC port is open and accepting HTTP connections."""
    try:
        parsed = urlparse(rpc_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8545
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not is_live_node_available(os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)),
    reason=f"Live JSON-RPC node not available at {DEFAULT_HARDHAT_RPC_URL}",
)


@pytest.fixture(scope="module")
def live_w3() -> Web3:
    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        pytest.skip(f"Web3 cannot connect to RPC at {rpc_url}")
    return w3


@pytest.fixture(scope="module")
def contract_address(live_w3: Web3) -> str:
    addr = os.getenv("HONEY_CHAIN_BLOCKCHAIN_CONTRACT_ADDRESS", DEFAULT_CONTRACT_ADDRESS)
    checksum_addr = Web3.to_checksum_address(addr)
    code = live_w3.eth.get_code(checksum_addr)
    if not code or code == b"" or code == b"\x00":
        pytest.skip(f"No contract bytecode deployed at {checksum_addr}")
    return checksum_addr


def test_live_node_and_contract_bytecode(live_w3: Web3, contract_address: str) -> None:
    """Verify chain ID, deployed bytecode presence, and contract owner."""
    assert live_w3.eth.chain_id == 31337
    code = live_w3.eth.get_code(contract_address)
    assert len(code) > 0, "Bytecode must be present at contract address"

    contract = live_w3.eth.contract(address=contract_address, abi=HONEY_TRACEABILITY_ABI)
    owner = contract.functions.owner().call()
    assert owner.lower() == DEFAULT_HARDHAT_DEPLOYER.lower()


def test_live_adapter_register_batch_and_add_evidence(
    live_w3: Web3, contract_address: str
) -> None:
    """Verify real transaction submission and on-chain state queries via EthereumJsonRpcAdapter."""
    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    priv_key = os.getenv("HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY", DEFAULT_HARDHAT_PRIVATE_KEY)

    settings = BlockchainSettings(
        enabled=True,
        rpc_url=rpc_url,
        contract_address=contract_address,
        chain_id=live_w3.eth.chain_id,
        network_name="localhost",
        private_key=SecretStr(priv_key),
    )

    adapter = EthereumJsonRpcAdapter(settings=settings)
    assert adapter.is_configured() is True

    # 1. Register Batch
    unique_batch_code = f"LIVE-BAT-{uuid4().hex[:8].upper()}"
    reg_result = adapter.register_batch(
        batch_code=unique_batch_code,
        metadata_hash=EMPTY_METADATA_HASH,
    )

    assert reg_result.status == BlockchainStatus.CONFIRMED
    assert reg_result.transaction_hash.startswith("0x")
    assert reg_result.block_number is not None
    assert reg_result.block_number > 0
    assert reg_result.contract_address == contract_address

    # 2. Add Evidence
    evidence_digest = bytes.fromhex(
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    ev_result = adapter.add_evidence(
        batch_code=unique_batch_code,
        evidence_hash=evidence_digest,
    )

    assert ev_result.status == BlockchainStatus.CONFIRMED
    assert ev_result.transaction_hash.startswith("0x")
    assert ev_result.block_number is not None

    # 3. On-chain query verification
    contract = live_w3.eth.contract(address=contract_address, abi=HONEY_TRACEABILITY_ABI)

    batch_data = contract.functions.getBatch(unique_batch_code).call()
    batch_id_ret, meta_hash_ret, status_ret, packaging_ref_ret, created_at_ret, exists_ret = batch_data

    assert exists_ret is True
    assert batch_id_ret == unique_batch_code
    assert status_ret == 0  # Status.ACTIVE
    assert meta_hash_ret == EMPTY_METADATA_HASH

    ev_count = contract.functions.getEvidenceCount(unique_batch_code).call()
    assert ev_count == 1

    ev_0 = contract.functions.getEvidence(unique_batch_code, 0).call()
    ev_hash_ret, ev_ts_ret, ev_exists_ret = ev_0
    assert ev_exists_ret is True
    assert ev_hash_ret == evidence_digest
    assert ev_ts_ret > 0
