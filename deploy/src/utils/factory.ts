import { TezosToolkit } from "@taquito/taquito";
import { InMemorySigner } from "@taquito/signer";

const tezos = new TezosToolkit(`https://${process.argv[2]}.smartpy.io`);

tezos.setProvider({
  signer: new InMemorySigner(process.env.PRIVATE_KEY as string),
});

const FACTORY = process.argv[3];
const AMM = process.argv[4];
const LP_TOKEN = process.argv[5];
const TOKEN_1 = process.argv[6];
const TOKEN_1_TYPE = process.argv[7];
const TOKEN_1_ID = process.argv[8];
const TOKEN_2 = process.argv[9];
const TOKEN_2_TYPE = process.argv[10];
const TOKEN_2_ID = process.argv[11];

(async () => {
  // Factory contract instance
  const factoryInstance = await tezos.contract.at(FACTORY);

  const tokenParams = [
    {
      token_address: TOKEN_1,
      type: { 1: parseInt(TOKEN_1_TYPE), 2: parseInt(TOKEN_1_ID) },
    },
    {
      token_address: TOKEN_2,
      type: { 1: parseInt(TOKEN_2_TYPE), 2: parseInt(TOKEN_2_ID) },
    },
  ];

  console.log("\n>> Inserting new AMM to the VE system\n");
  console.log("> Core Factory: ", FACTORY);
  console.log("> AMM: ", AMM);
  console.log("> LP Token: ", LP_TOKEN);
  console.log("> Token 1: ", TOKEN_1);
  console.log("> Token 1 type: ", TOKEN_1_TYPE == "0" ? "FA1.2" : "FA2");
  console.log("> Token 1 ID: ", TOKEN_1_ID);
  console.log("> Token 2: ", TOKEN_2);
  console.log("> Token 2 type: ", TOKEN_2_TYPE == "0" ? "FA1.2" : "FA2");
  console.log("> Token 2 ID: ", TOKEN_2_ID);

  try {
    // Insert new AMM in VE system
    const op = await factoryInstance.methods.add_amm(AMM, LP_TOKEN, tokenParams).send();
    await op.confirmation(1);
    console.log("\n>> AMM inserted. Operation Hash: ", op.hash);
  } catch (err) {
    console.log("\n>> Error occured: ", err.message);
  }
})();
