import { TezosToolkit } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";

// Types and utlities
import { deploy, DeployParams } from "./deploy";

const tezos = new TezosToolkit(`https://${process.argv[2]}.smartpy.io`);

tezos.setProvider({
  signer: new InMemorySigner(process.env.PRIVATE_KEY as string),
});

// Admin for PLY FA1.2 contract
const PLY_ADMIN = "tz1WDRu8H4dHbUwygocLsmaXgHthGiV6JGJG";

// Admin for core factory contract
const FACTORY_ADMIN = "tz1WDRu8H4dHbUwygocLsmaXgHthGiV6JGJG";

// True if initial plenty/wrap to PLY swap contract needs to be deployed
const DEPLOY_VE_SWAP = true;

// Address of PLENTY token contract
const PLENTY_ADDRESS = "KT1EJo3R1AT1XUZxNer8TgaTeM8p5ippMUqW";

// Address of WRAP token contract
const WRAP_ADDRESS = "KT1PzM3a5P6rq5882B5prfpyCfTbrYzpiNmK";

// Unix timestamp at which swapping starts
const VE_SWAP_GENESIS = "2022-12-01T00:00:00Z";

// Unix timestamp at which swapping vesting ends
const VE_SWAP_END = "2024-12-01T00:00:00Z";

// PLY / PLENTY exchange rate
const PLENTY_EXCHANGE_VAL = 6 * 10 ** 18;

// PLY / WRAP exchange rate
const WRAP_EXCHANGE_VAL = "30000000000000000000000000000";

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
