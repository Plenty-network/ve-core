import { TezosToolkit } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";

// Types and utlities
import { deploy, DeployParams } from "./deploy";

const tezos = new TezosToolkit(`https://${process.argv[2]}.smartpy.io`);

tezos.setProvider({
  signer: new InMemorySigner(process.env.PRIVATE_KEY as string),
});

// Admin for PLY FA1.2 contract
const PLY_ADMIN = "tz1Y8cACwiwQYwLNzzHnBvLQBendT6DUR3Rn";

// Admin for core factory contract
const FACTORY_ADMIN = "tz1Y8cACwiwQYwLNzzHnBvLQBendT6DUR3Rn";

// True if initial plenty/wrap to PLY swap contract needs to be deployed
const DEPLOY_VE_SWAP = true;

// Address of PLENTY token contract
const PLENTY_ADDRESS = "KT1GRSvLoikDsXujKgZPsGLX8k8VvR2Tq95b";

// Address of WRAP token contract
const WRAP_ADDRESS = "KT1LRboPna9yQY9BrjtQYDS1DVxhKESK4VVd";

// Unix timestamp at which swapping starts
const VE_SWAP_GENESIS = "2023-01-05T00:00:00Z";

// Unix timestamp at which swapping vesting ends
const VE_SWAP_END = "2025-01-05T00:00:00Z";

// PLY / PLENTY exchange rate
const PLENTY_EXCHANGE_VAL = "5714285714285714285";

// PLY / WRAP exchange rate
const WRAP_EXCHANGE_VAL = "30927865055015100165151551528";

const deployParams: DeployParams = {
  tezos,
  plyAdmin: PLY_ADMIN,
  factoryAdmin: FACTORY_ADMIN,
  deployVeSwap: DEPLOY_VE_SWAP,
  plentyAddress: PLENTY_ADDRESS,
  wrapAddress: WRAP_ADDRESS,
  plentyExchangeVal: PLENTY_EXCHANGE_VAL,
  wrapExchangeVal: WRAP_EXCHANGE_VAL,
  veSwapGenesis: VE_SWAP_GENESIS,
  veSwapEnd: VE_SWAP_END,
};

deploy(deployParams);
