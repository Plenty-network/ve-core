# Overview

Plenty's PLY/vePLY system consists of several core and associated contracts working in tandem, to play out a model that enables bootstraping of liquidity through a vote-escrow mechanism.

The core contracts handle the base token minting and distribution across `Gauges`, vote escrow lockups, governance, AMM fee distribution, and deployment of the related core contracts. The Gauge and Bribe contracts are tied to the AMMs, with each AMM having one Gauge and one Bribe contract associated with it.

The AMMs (Standard-swap and stable-swap) are the associated contracts, and they are the primary store of liquidity. From a top level view, the AMMs (associated contracts) are the entities through which all liquidity flows through, and the ve-system (core contracts) can direct this flow through its incentivisation model.

## Core Contracts

| Contract         | Description                                                                                                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PLY FA1.2`      | Base token of the system that is emitted weekly. It is based on the FA1.2 standard on Tezos.                                                                                 |
| `VoteEscrow`     | Allows locking up of PLY tokens as vePLY NFTs. These vePLY tokens are based on the FA2 standard on Tezos. vePLY forms the primary governance token in the vote-escrow model. |
| `Voter`          | Handles the voting for distribution of weekly PLY emissions across the gauges of the AMMs.                                                                                   |
| `FeeDistributor` | Collects and distributes fees from whitelisted Plenty AMMs to the weekly voters.                                                                                             |
| `CoreFactory`    | Assists in addition (whitelisting) of new AMMs to the vote-escrow system by deploying the related core contracts mentioned below.                                            |

## Related Core Contracts

| Contract | Description                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------------- |
| `Gauge`  | Distributes weekly PLY emissions to the stakers of LP tokens of Plenty AMMs. Every whitelisted AMM has an associated gauge. |
| `Bribe`  | Allows bribing (rewarding) voters of a specific AMM in a specific voting period (epoch).                                    |

## Associated Contracts

| Contract        | Description                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------- |
| `AMM`           | A constant product market maker contract that charges a small fee for swaps between a token pair. |
| `FlatCurve AMM` | A stableswap contract that allows near 0 slippage swaps between co-related token pairs.           |

## Supplementary Contracts

| Contract | Description                                                                 |
| -------- | --------------------------------------------------------------------------- |
| `VESwap` | Allows for exchanging existing PLENTY and WRAP tokens to the new PLY token. |
