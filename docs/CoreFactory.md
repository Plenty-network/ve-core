# CoreFactory

**CoreFactory** contract allows for the following user-facing operations:

- The admin can add/whitelisted new AMMs in the vote-escrow system.
- The admin can remove whitelisted AMMs.

## Storage

| Storage Item      | Type                     | Description                                                            |
| ----------------- | ------------------------ | ---------------------------------------------------------------------- |
| `admin`           | `address`                | Address of Plenty Admin. Initially a Multisig controlled by core team. |
| `voter`           | `address`                | Address of `Voter` contract.                                           |
| `ply_address`     | `address`                | Address of PLY token contract.                                         |
| `ve_address`      | `address`                | Address of `VoteEscrow` contract.                                      |
| `fee_distributor` | `address`                | Address of `FeeDistributor` contract.                                  |
| `amm_registered`  | `(big_map address unit)` | Records inserted/whitelisted AMMs.                                     |

## Entrypoints

| Entrypoint            | Parameters                                                                                                                             | Description                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `add_amm`             | `(pair (address %amm) (pair (address %lp_token_address) (set %tokens (or (address %fa12) (or (pair %fa2 address nat) (unit %tez))))))` | Called by the `admin` to insert a new AMM into the vote-escrow system                       |
| `remove_amm`          | `address`                                                                                                                              | Called by the `admin` to remove an AMM from the system.                                     |
| `set_fee_distributor` | `address`                                                                                                                              | Called by the admin to set the `FeeDistributor` contract, once during origination sequence. |
