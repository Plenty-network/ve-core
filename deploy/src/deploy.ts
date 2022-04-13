import { TezosToolkit, ParamsWithKind, OpKind } from "@taquito/taquito";

// Utils
import * as storageUtils from "./utils/storage";
import * as contractUtils from "./utils/contract";

export interface DeployParams {
  tezos: TezosToolkit;
  plyAdmin: string;
  factoryAdmin: string;
  deployVeSwap: boolean;
  plentyAddress: string;
  wrapAddress: string;
  plentyExchangeVal: number;
  wrapExchangeVal: number;
  veSwapGenesis: string;
  veSwapEnd: string;
}

export const deploy = async (deployParams: DeployParams) => {
  try {
    console.log("--------------------------------------");
    console.log(` Deploying PLY/vePLY System Contracts`);
    console.log("--------------------------------------");

    // Prepare storage and contract for PLY FA1.2
    const plyStorage = storageUtils.getPlyStorage({ admin: deployParams.plyAdmin });
    const plyContract = contractUtils.loadContract("ply_fa12");

    // Deploy PLY FA1.2
    console.log("\n>> [1 / 6] Deploying PLY FA1.2");
    const plyAddress = await contractUtils.deployContract(plyContract, plyStorage, deployParams.tezos);
    console.log(">>> PLY FA1.2 address: ", plyAddress);

    // Prepare storage and contract for Vote Escrow
    const veStorage = storageUtils.getVEStorage({ baseToken: plyAddress });
    const veContract = contractUtils.loadContract("vote_escrow");

    // Depoy Ve swap
    if (deployParams.deployVeSwap) {
      const veSwapStorage = storageUtils.getVESwapStorage({
        plyAddress,
        plentyAddress: deployParams.plentyAddress,
        wrapAddress: deployParams.wrapAddress,
        veSwapEnd: deployParams.veSwapEnd,
        veSwapGenesis: deployParams.veSwapGenesis,
        plentyExchangeVal: deployParams.plentyExchangeVal,
        wrapExchangeVal: deployParams.wrapExchangeVal,
      });
      const veSwapContract = contractUtils.loadContract("ve_swap");

      console.log("\n>> [x] Deploying VESwap contract");
      const veSwapAddress = await contractUtils.deployContract(veSwapContract, veSwapStorage, deployParams.tezos);
      console.log(">>> VE Swap address: ", veSwapAddress);
    }

    // Deploy Vote Escrow
    console.log("\n>> [2 / 6] Deploying Vote Escrow");
    const veAddress = await contractUtils.deployContract(veContract, veStorage, deployParams.tezos);
    console.log(">>> Vote Escrow address: ", veAddress);

    // Prepare storage and contract for Voter
    const voterStorage = storageUtils.getVoterStorage({ plyAddress, veAddress });
    const voterContract = contractUtils.loadContract("voter");

    // Deploy Voter
    console.log("\n>> [3 / 6] Deploying Voter");
    const voterAddress = await contractUtils.deployContract(voterContract, voterStorage, deployParams.tezos);
    console.log(">>> Voter address: ", voterAddress);

    // Prepare storage and contract for Core Factory
    const factoryStorage = storageUtils.getFactoryStorage({
      admin: deployParams.factoryAdmin,
      plyAddress,
      veAddress,
      voterAddress,
    });
    const factoryContract = contractUtils.loadContract("core_factory");

    // Deploy Factory
    console.log("\n>> [4 / 6] Deploying Core Factory");
    const factoryAddress = await contractUtils.deployContract(factoryContract, factoryStorage, deployParams.tezos);
    console.log(">>> Core Factory address: ", factoryAddress);

    // Prepare storage and contract for Fee Distributor
    const feeDistributorStorage = storageUtils.getFeeDistributorStorage({
      factoryAddress,
      voterAddress,
    });
    const feeDistributorContract = contractUtils.loadContract("fee_distributor");

    // Deploy Fee Distributor
    console.log("\n>> [5 / 6] Deploying Fee Distributor");
    const feeDistributorAddress = await contractUtils.deployContract(
      feeDistributorContract,
      feeDistributorStorage,
      deployParams.tezos
    );
    console.log(">>> Fee Distributor address: ", feeDistributorAddress);

    // Contract instance
    const factoryInstance = await deployParams.tezos.contract.at(factoryAddress);
    const voterInstance = await deployParams.tezos.contract.at(voterAddress);
    const veInstance = await deployParams.tezos.contract.at(veAddress);

    // Prepare batch operation list
    const opList: ParamsWithKind[] = [
      {
        kind: OpKind.TRANSACTION,
        ...factoryInstance.methods.set_fee_distributor(feeDistributorAddress).toTransferParams(),
      },
      {
        kind: OpKind.TRANSACTION,
        ...voterInstance.methods.set_factory_and_fee_dist(factoryAddress, feeDistributorAddress).toTransferParams(),
      },
      {
        kind: OpKind.TRANSACTION,
        ...veInstance.methods.set_voter(voterAddress).toTransferParams(),
      },
    ];

    // Configure inter contract connections
    console.log("\n>> [6 / 6] Configuring inter-contract connections");
    const batch = deployParams.tezos.contract.batch(opList);
    const batchOp = await batch.send();
    await batchOp.confirmation(1);
    console.log(">>> Inter-contract connections configured. Operation Hash: ", batchOp.hash);

    console.log("\n--------------------------------------");
    console.log(` Deployment Complete!`);
    console.log("--------------------------------------");
  } catch (err) {
    console.log(err.message);
  }
};
