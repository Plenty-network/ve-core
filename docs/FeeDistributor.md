# FeeDistributor

**FeeDistributor** contract allows for the following user-facing operations:

- Addition of new AMM and associated token pair by admin, through `CoreFactory`.
- Claiming of AMM fees by voters for specific epochs.

## Storage

| Storage Item    | Type                                                                                                          | Description                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `voter`         | `address`                                                                                                     | Address of `Voter` contract.                                       |
| `core_factory`  | `address`                                                                                                     | Address of `CoreFactory` contract.                                 |
| `amm_to_tokens` | `(big_map address (set (pair (address %token_address) (pair %type nat nat))))`                                | Records whitelisted AMMs and their associated token pairs.         |
| `amm_epoch_fee` | `(big_map (pair (address %amm) (nat %epoch)) (map (pair (address %token_address) (pair %type nat nat)) nat))` | Records fee pulled in from an AMM during a specific epoch.         |
| `claim_ledger`  | `(big_map (pair (nat %token_id) (pair (address %amm) (nat %epoch))) unit)`                                    | Tracks if a voter has claimed fees of an AMM for a specific epoch. |

## Entrypoints

| Entrypoint   | Parameters                                                                                                     | Description                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `add_amm`    | `(pair (address %amm) (set %tokens (pair (address %token_address) (pair %type nat nat))))`                     | Called by `CoreFactory` to whitelist an AMM, and add associated token pairs.                   |
| `remove_amm` | `address`                                                                                                      | Called by `CoreFactory` to remove whitelisted AMM.                                             |
| `add_fees`   | `(pair (nat %epoch) (map %fees (pair (address %token_address) (pair %type nat nat)) nat))`                     | Called by a whitelisted AMM to add its fees for a specific epoch.                              |
| `claim`      | `(pair (nat %token_id) (pair (address %owner) (pair (address %amm) (pair (nat %epoch) (nat %weight_share)))))` | Called by `Voter` contract to transfer fees to owner, based on vote weigh-share of vePLY used. |

## Views

| View                    | Parameters                                                  | Return Type            | Description                                                             |
| ----------------------- | ----------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| `get_current_epoch`     | `unit`                                                      | `(pair nat timestamp)` | Returns currently on-going epoch with its ending timestamp.             |
| `get_epoch_end`         | `nat`                                                       | `nat`                  | Returns the ending timestamp of a specific epoch.                       |
| `get_token_amm_votes`   | `(pair (nat %token_id) (pair (address %amm) (nat %epoch)))` | `nat`                  | Returns total votes given to an AMM using a specific token in an epoch. |
| `get_total_amm_votes`   | `(pair (address %amm) (nat %epoch))`                        | `nat`                  | Returns total votes received by an AMM during an epoch. .               |
| `get_total_epoch_votes` | `nat`                                                       | `nat`                  | Returns total votes given to all AMMs, by all tokens, during an epoch.  |
| `get_total_token_votes` | `(pair (nat %token_id) (nat %epoch))`                       | `nat`                  | Returns total votes given by a specific token during an epoch.          |
