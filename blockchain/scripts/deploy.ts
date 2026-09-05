import { network } from "hardhat";

async function main() {
  const connection = await network.getOrCreate();
  const { viem } = connection;
  const publicClient = await viem.getPublicClient();
  const [deployer] = await viem.getWalletClients();
  const chainId = await publicClient.getChainId();

  console.log("=========================================");
  console.log("HoneyTraceability Deployment");
  console.log("=========================================");
  console.log(`Network:   ${connection.networkName}`);
  console.log(`Chain ID:  ${chainId}`);
  console.log(`Deployer:  ${deployer ? deployer.account.address : "unknown"}`);

  const honey = await viem.deployContract("HoneyTraceability");

  console.log(`Contract:  ${honey.address}`);
  console.log("=========================================");
  console.log("Backend Environment Config:");
  console.log(`HONEY_CHAIN_BLOCKCHAIN_CONTRACT_ADDRESS=${honey.address}`);
  console.log(`HONEY_CHAIN_BLOCKCHAIN_CHAIN_ID=${chainId}`);
  console.log(`HONEY_CHAIN_BLOCKCHAIN_NETWORK=${connection.networkName}`);
  console.log("=========================================");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});