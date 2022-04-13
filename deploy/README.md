# Deploy

The scripts provided in this folder can be used to deploy a complete instance of the PLY/vePLY system with all the base contracts.

### Install Dependencies

Install the node dependencies using yarn:

```
$ yarn install
```

### Deploy the Contracts

First, set the values of the configuration fields in the `index.ts` file in `src` folder. The fields to be set are

- `PLY_ADMIN` : Admin address for the PLY FA1.2 token.
- `FACTORY_ADMIN` : Admin address for the Core Factory.
- `DEPLOY_VE_SWAP`: True if PLENTY/WRAP to PLY swapping contract needs to be deployed.
- `PLENTY_ADDRESS`: Tezos address of PLENTY token contract.
- `WRAP_ADDRESS`: Tezos address of WRAP token contract.
- `VE_SWAP_GENESIS`: Timestamp at which swapping begins.
- `VE_SWAP_END`: Timestamp at which swap vesting ends.
- `PLENTY_EXCHANGE_VAL`: PLY/PLENTY swap rate.
- `WRAP_EXCHANGE_VAL`: PLY/WRAP swap rate.

Once the configuration fields are prepared, the deployment can be done by providing a private key as an environment variable and running `deploy:testnet` script:

```
$ PRIVATE_KEY=<Your private key> yarn deploy:testnet
```
