import { TezosToolkit } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";

// Types and utlities
import { deploy, DeployParams } from "./deploy";

const tezos = new TezosToolkit(`https://${process.argv[2]}.smartpy.io`);

tezos.setProvider({
  signer: new InMemorySigner(process.env.PRIVATE_KEY as string),
});

// Admin for PLY FA1.2 contract
const PLY_ADMIN = "tz1ZczbHu1iLWRa88n9CUiCKDGex5ticp19S";

// Admin for core factory contract
const FACTORY_ADMIN = "tz1ZczbHu1iLWRa88n9CUiCKDGex5ticp19S";

const deployParams: DeployParams = {
  tezos,
  plyAdmin: PLY_ADMIN,
  factoryAdmin: FACTORY_ADMIN,
};

deploy(deployParams);
