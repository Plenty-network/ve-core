# CoreFactory

**CoreFactory** contract allows for the following user-facing operations:

- The add-admin can add/whitelisted new AMMs in the vote-escrow system.
- The remove-admin can remove whitelisted AMMs.

## Storage

| Storage Item            | Type                     | Description                                                                                  |
| ----------------------- | ------------------------ | -------------------------------------------------------------------------------------------- |
| `add_admin`             | `address`                | Address that can add an AMM to ve-system. Initially a Multisig controlled by core team.      |
| `remove_admin`          | `address`                | Address that can remove an AMM from ve-system. Initially a Multisig controlled by core team. |
| `proposed_add_admin`    | `(option address)`       | New add-admin proposed by the former.                                                        |
| `proposed_remove_admin` | `(option address)`       | New remove-admin proposed by the former.                                                     |
| `voter`                 | `address`                | Address of `Voter` contract.                                                                 |
| `ply_address`           | `address`                | Address of PLY token contract.                                                               |
| `ve_address`            | `address`                | Address of `VoteEscrow` contract.                                                            |
| `fee_distributor`       | `address`                | Address of `FeeDistributor` contract.                                                        |
| `amm_registered`        | `(big_map address unit)` | Records inserted/whitelisted AMMs.                                                           |

## Entrypoints

| Entrypoint             | Parameters                                                                                                                             | Description                                                                                 |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `add_amm`              | `(pair (address %amm) (pair (address %lp_token_address) (set %tokens (or (address %fa12) (or (pair %fa2 address nat) (unit %tez))))))` | Called by the `admin` to insert a new AMM into the vote-escrow system                       |
| `remove_amm`           | `address`                                                                                                                              | Called by the `admin` to remove an AMM from the system.                                     |
| `set_fee_distributor`  | `address`                                                                                                                              | Called by the admin to set the `FeeDistributor` contract, once during origination sequence. |
| `propose_add_admin`    | `address`                                                                                                                              | Called by current add-admin to propose a new one.                                           |
| `propose_remove_admin` | `address`                                                                                                                              | Called by current remove-admin to propose a new one.                                        |
| `accept_add_admin`     | `unit`                                                                                                                                 | Called by the proposed add-admin to accept the role.                                        |
| `accept_remove_admin`  | `unit`                                                                                                                                 | Called by the proposed remove-admin to accept the role.                                     |
