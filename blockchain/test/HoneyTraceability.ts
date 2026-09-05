import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { network } from "hardhat";

describe("HoneyTraceability", async function () {

  async function deployContract() {
    const { viem } = await network.getOrCreate();

    const honey = await viem.deployContract("HoneyTraceability");
    const publicClient = await viem.getPublicClient();

    return { honey, publicClient };
  }

  // 1. Register batch
  it("should register a honey batch", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-001";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const txHash = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: txHash,
    });

    const batch = (await honey.read.getBatch([
      batchId,
    ])) as any;

    assert.equal(batch[0], batchId);
    assert.equal(batch[1], metadataHash);
    assert.equal(batch[2], 0);
    assert.equal(batch[5], true);
  });

  // 2. Add lab evidence
  it("should add lab evidence", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-002";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const evidenceHash =
      "0xabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd";

    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: registerTx,
    });

    const evidenceTx = await honey.write.addEvidence([
      batchId,
      evidenceHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: evidenceTx,
    });

    const count = await honey.read.getEvidenceCount([
      batchId,
    ]);

    assert.equal(count, 1n);

    const evidence = (await honey.read.getEvidence([
      batchId,
      0n,
    ])) as any;

    assert.equal(evidence[0], evidenceHash);
    assert.equal(evidence[2], true);
  });

  // 3. Link packaging
  it("should link packaging reference", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-003";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: registerTx,
    });

    const packagingTx = await honey.write.linkPackaging([
      batchId,
      "PKG-001",
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: packagingTx,
    });

    const batch = (await honey.read.getBatch([
      batchId,
    ])) as any;

    assert.equal(batch[3], "PKG-001");
  });

  // 4. Change status to HOLD
  it("should change status to HOLD", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-004";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: registerTx,
    });

    const statusTx = await honey.write.updateStatus([
      batchId,
      1,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: statusTx,
    });

    const batch = (await honey.read.getBatch([
      batchId,
    ])) as any;

    // 0 = ACTIVE
    // 1 = HOLD
    // 2 = RECALL

    assert.equal(batch[2], 1);
  });

  // 5. Change status to RECALL
  it("should change status to RECALL", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-005";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: registerTx,
    });

    const statusTx = await honey.write.updateStatus([
      batchId,
      2,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: statusTx,
    });

    const batch = (await honey.read.getBatch([
      batchId,
    ])) as any;

    assert.equal(batch[2], 2);
  });

  // 6. Reject duplicate batch
  it("should reject duplicate batch", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "BATCH-006";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const firstTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: firstTx,
    });

    await assert.rejects(
      honey.write.registerBatch([
        batchId,
        metadataHash,
      ])
    );
  });

  // 7. Full traceability flow
  it("should complete the full honey traceability flow", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "HONEY-TRACE-001";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const evidenceHash =
      "0xabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd";

    // 1. Register batch
    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: registerTx,
    });

    // 2. Add lab evidence
    const evidenceTx = await honey.write.addEvidence([
      batchId,
      evidenceHash,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: evidenceTx,
    });

    // 3. Link packaging
    const packagingTx = await honey.write.linkPackaging([
      batchId,
      "PKG-HONEY-001",
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: packagingTx,
    });

    // 4. Change status to HOLD
    const statusTx = await honey.write.updateStatus([
      batchId,
      1,
    ]);

    await publicClient.waitForTransactionReceipt({
      hash: statusTx,
    });

    // 5. Verify batch
    const batch = (await honey.read.getBatch([
      batchId,
    ])) as any;

    assert.equal(batch[0], batchId);
    assert.equal(batch[1], metadataHash);
    assert.equal(batch[2], 1);
    assert.equal(batch[3], "PKG-HONEY-001");
    assert.equal(batch[5], true);

    // 6. Verify evidence
    const count = await honey.read.getEvidenceCount([
      batchId,
    ]);

    assert.equal(count, 1n);

    const evidence = (await honey.read.getEvidence([
      batchId,
      0n,
    ])) as any;

    assert.equal(evidence[0], evidenceHash);
    assert.equal(evidence[2], true);
  });

  // 8. Traceability events
  it("should emit traceability events", async function () {
    const { honey, publicClient } = await deployContract();

    const batchId = "EVENT-001";

    const metadataHash =
      "0x1234567890123456789012345678901234567890123456789012345678901234";

    const evidenceHash =
      "0xabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd";

    // Register Batch
    const registerTx = await honey.write.registerBatch([
      batchId,
      metadataHash,
    ]);

    const registerReceipt =
      await publicClient.waitForTransactionReceipt({
        hash: registerTx,
      });

    assert.ok(registerReceipt.logs.length > 0);

    // Add Evidence
    const evidenceTx = await honey.write.addEvidence([
      batchId,
      evidenceHash,
    ]);

    const evidenceReceipt =
      await publicClient.waitForTransactionReceipt({
        hash: evidenceTx,
      });

    assert.ok(evidenceReceipt.logs.length > 0);

    // Link Packaging
    const packagingTx = await honey.write.linkPackaging([
      batchId,
      "PKG-EVENT-001",
    ]);

    const packagingReceipt =
      await publicClient.waitForTransactionReceipt({
        hash: packagingTx,
      });

    assert.ok(packagingReceipt.logs.length > 0);

    // Update Status
    const statusTx = await honey.write.updateStatus([
      batchId,
      1,
    ]);

    const statusReceipt =
      await publicClient.waitForTransactionReceipt({
        hash: statusTx,
      });

    assert.ok(statusReceipt.logs.length > 0);
  });
});