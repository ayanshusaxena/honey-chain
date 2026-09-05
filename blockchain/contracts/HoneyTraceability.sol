// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

contract HoneyTraceability is Ownable {

    enum Status {
        ACTIVE,
        HOLD,
        RECALL
    }

    struct Batch {
        string batchId;
        bytes32 metadataHash;
        Status status;
        string packagingRef;
        uint256 createdAt;
        bool exists;
    }

    struct Evidence {
        bytes32 evidenceHash;
        uint256 timestamp;
        bool exists;
    }

    mapping(string => Batch) private batches;

    mapping(string => mapping(uint256 => Evidence)) private evidences;

    mapping(string => uint256) private evidenceCount;

    // Events
    event BatchRegistered(
        string indexed batchId,
        bytes32 metadataHash,
        uint256 timestamp
    );

    event EvidenceAdded(
        string indexed batchId,
        bytes32 evidenceHash,
        uint256 timestamp
    );

    event PackagingLinked(
        string indexed batchId,
        string packagingRef,
        uint256 timestamp
    );

    event StatusUpdated(
        string indexed batchId,
        Status status,
        uint256 timestamp
    );

    constructor() Ownable(msg.sender) {}

    // 1. Register Honey Batch
    function registerBatch(
        string calldata batchId,
        bytes32 metadataHash
    ) external onlyOwner {

        require(
            bytes(batchId).length > 0,
            "Batch ID required"
        );

        require(
            !batches[batchId].exists,
            "Batch already exists"
        );

        batches[batchId] = Batch({
            batchId: batchId,
            metadataHash: metadataHash,
            status: Status.ACTIVE,
            packagingRef: "",
            createdAt: block.timestamp,
            exists: true
        });

        emit BatchRegistered(
            batchId,
            metadataHash,
            block.timestamp
        );
    }

    // 2. Add Lab Evidence
    function addEvidence(
        string calldata batchId,
        bytes32 evidenceHash
    ) external onlyOwner {

        require(
            batches[batchId].exists,
            "Batch does not exist"
        );

        require(
            evidenceHash != bytes32(0),
            "Evidence hash required"
        );

        uint256 index = evidenceCount[batchId];

        evidences[batchId][index] = Evidence({
            evidenceHash: evidenceHash,
            timestamp: block.timestamp,
            exists: true
        });

        evidenceCount[batchId] = index + 1;

        emit EvidenceAdded(
            batchId,
            evidenceHash,
            block.timestamp
        );
    }

    // 3. Link Packaging
    function linkPackaging(
        string calldata batchId,
        string calldata packagingRef
    ) external onlyOwner {

        require(
            batches[batchId].exists,
            "Batch does not exist"
        );

        require(
            bytes(packagingRef).length > 0,
            "Packaging reference required"
        );

        batches[batchId].packagingRef = packagingRef;

        emit PackagingLinked(
            batchId,
            packagingRef,
            block.timestamp
        );
    }

    // 4. Update Batch Status
    function updateStatus(
        string calldata batchId,
        Status newStatus
    ) external onlyOwner {

        require(
            batches[batchId].exists,
            "Batch does not exist"
        );

        batches[batchId].status = newStatus;

        emit StatusUpdated(
            batchId,
            newStatus,
            block.timestamp
        );
    }

    // 5. Get Batch Details
    function getBatch(
        string calldata batchId
    )
        external
        view
        returns (
            string memory,
            bytes32,
            Status,
            string memory,
            uint256,
            bool
        )
    {
        Batch memory batch = batches[batchId];

        return (
            batch.batchId,
            batch.metadataHash,
            batch.status,
            batch.packagingRef,
            batch.createdAt,
            batch.exists
        );
    }

    // 6. Get Evidence Count
    function getEvidenceCount(
        string calldata batchId
    )
        external
        view
        returns (uint256)
    {
        require(
            batches[batchId].exists,
            "Batch does not exist"
        );

        return evidenceCount[batchId];
    }

    // 7. Get Evidence
    function getEvidence(
        string calldata batchId,
        uint256 index
    )
        external
        view
        returns (
            bytes32,
            uint256,
            bool
        )
    {
        require(
            batches[batchId].exists,
            "Batch does not exist"
        );

        require(
            index < evidenceCount[batchId],
            "Invalid evidence index"
        );

        Evidence memory evidence = evidences[batchId][index];

        return (
            evidence.evidenceHash,
            evidence.timestamp,
            evidence.exists
        );
    }
}