# Plenty PLY/vePLY Core

## Folder Structure

- `helpers` : Consists of test helpers like dummy addresses and token contracts.
- `michelson` : Compiled michelson code.
- `utils` : Utilities like token transfer calls.
- `deploy` : Scripts to assist contract deployment.
- `docs` : Elaborate documentation explaining the system and contract design.
- `flat-curve`: Submodule linked to Plenty's flat curve AMM contracts that would be connected to VE system.

## Contract Files

All contracts are written in [SmartPy](https://smartpy.io) version `0.9.0`. Refer to their elaborate [documentation](https://smartpy.io/docs) for further understanding.

- `ply_fa12` : The base emission token PLY that follows the [FA1.2](https://tezos.gitlab.io/user/fa12.html) standard on Tezos.
- `vote_escrow` : Allows locking of PLY as vePLY NFTs that are used in voting for emission distributions.
- `voter` : Handles voting for PLY emission distribution across gauges of different Plenty AMMs.
- `gauge` : A farming contract that emits PLY to staker of LP tokens of a specfic AMM.
- `bribe` : Allows bribing (rewarding) of the voters of a specific AMM during a particular voting period.
- `core_factory` : Deploys gauge and bribe contracts and connects them to other relevant contracts.
- `ve_swap`: A supplementary contract to allow for exchanging existing PLENTY and WRAP tokens to PLY.

## Compilation

A shell script has been provided to assist compilation and testing of the contracts. The script can be run using-

```shell
$ bash compile.sh
```

**NOTE:** You must have smartpy-cli `0.9.0` installed at the default global location.
