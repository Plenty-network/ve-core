# FeeDistributor

**FeeDistributor** contract allows for the following user-facing operations:

- Addition of new AMM and associated token pair by admin, through `CoreFactory`.
- Claiming of AMM fees by voters for specific epochs.

## Storage

| Storage Item    | Type                                                                                                                  | Description                                                        |
| --------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `voter`         | `address`                                                                                                             | Address of `Voter` contract.                                       |
| `core_factory`  | `address`                                                                                                             | Address of `CoreFactory` contract.                                 |
| `amm_to_tokens` | `(big_map (pair (address %amm) (nat %epoch)) (map (or (address %fa12) (or (pair %fa2 address nat) (unit %tez))) nat)` | Records whitelisted AMMs and their associated token pairs.         |
| `amm_epoch_fee` | `(big_map (pair (address %amm) (nat %epoch)) (map (pair (address %token_address) (pair %type nat nat)) nat))`         | Records fee pulled in from an AMM during a specific epoch.         |
| `claim_ledger`  | `(big_map (pair (nat %token_id) (pair (address %amm) (nat %epoch))) unit)`                                            | Tracks if a voter has claimed fees of an AMM for a specific epoch. |

## Entrypoints

| Entrypoint   | Parameters                                                                                                                        | Description                                                                                                                                                                                                                                                            |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add_amm`    | `(pair (address %amm) (set %tokens (or (address %fa12) (or (pair %fa2 address nat) (unit %tez)))))`                               | Called by `CoreFactory` to whitelist an AMM, and add associated token pairs.                                                                                                                                                                                           |
| `remove_amm` | `address`                                                                                                                         | Called by `CoreFactory` to remove whitelisted AMM.                                                                                                                                                                                                                     |
| `add_fees`   | `(pair (nat %epoch) (map %fees (or (address %fa12) (or (pair %fa2 address nat) (unit %tez))) nat))`                               | Called by a whitelisted AMM to add its fees for a specific epoch.                                                                                                                                                                                                      |
| `claim`      | `(pair (nat %token_id) (pair (address %owner) (pair (address %amm) (list %epoch_vote_shares (pair (nat %epoch) (nat %share))))))` | Called by `Voter` contract to transfer fees to owner, based on vote share of vePLY used. <ul><li><b>token_id:</b> The FA2 token-id of vePLY used to vote.</li><li><b>epoch_vote_shares:</b> Vote share across different epochs for the provided vePLY token.</li></ul> |
