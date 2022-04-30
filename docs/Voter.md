# Voter

**Voter** contract allows for the following user-facing operations:

- Permissionlessly update the system epoch.
- Vote for PLY emission distribution across AMM pools.
- Claim bribes for an epoch.
- Claim AMM fee for an epoch.
- Permissionlessly recharge the `Gauges` for an epoch.
- Permissionlessly pull AMM fees for an epoch.

## Storage

| Storage Item         | Type                                                                      | Description                                                                                                                                                                                                                                                                                      |
| -------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `core_factory`       | `address`                                                                 | Address of `CoreFactory` contract.                                                                                                                                                                                                                                                               |
| `fee_distributor`    | `address`                                                                 | Address of `FeeDistributor` contract.                                                                                                                                                                                                                                                            |
| `ply_address`        | `address`                                                                 | Address of PLY FA1.2 token contract.                                                                                                                                                                                                                                                             |
| `ve_address`         | `address`                                                                 | Address of `VoteEscrow` contract.                                                                                                                                                                                                                                                                |
| `epoch`              | `nat`                                                                     | The id of the current voting epoch. Each voting epoch lasts for a week.                                                                                                                                                                                                                          |
| `epoch_end`          | `(big_map nat timestamp)`                                                 | Records the ending timestamp of each epoch.                                                                                                                                                                                                                                                      |
| `emission`           | `(pair (nat %base) (pair (nat %genesis) (nat %real)))`                    | Tracks system's PLY inflation rates based on circulating v/s locked supply. <ul><li><b>base: </b> Nominal PLY inflation for the week</li><b>real: </b> Real PLY inflation for the week, adjust to Ve(3,3) principle.</li><li> <b>genesis: </b> timestamp at which PLY emissions begun.</li></ul> |
| `amm_to_gauge_bribe` | `(big_map address (pair (address %gauge) (address %bribe)))`              | Stores the addresses of whitelisted AMMs alongside associated `Gauge` and `Bribe` contracts.                                                                                                                                                                                                     |
| `total_amm_votes`    | `(big_map (pair (address %amm) (nat %epoch)) nat)`                        | Tracks total votes received by an AMM during an epoch.                                                                                                                                                                                                                                           |
| `token_amm_votes`    | `(big_map (pair (nat %token_id) (pair (address %amm) (nat %epoch))) nat)` | Tracks total votes given to an AMM using a specific token in an epoch.                                                                                                                                                                                                                           |
| `total_token_votes`  | `((big_map (pair (nat %token_id) (nat %epoch)) nat)`                      | Tracks total votes given by a specific token during an epoch.                                                                                                                                                                                                                                    |
| `total_epoch_votes`  | `(big_map nat nat)`                                                       | Tracks total votes given across all AMMs, by all tokens, during an epoch.                                                                                                                                                                                                                        |

## Entrypoints

| Entrypoint                 | Parameters                                                                           | Description                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `next_epoch`               | `unit`                                                                               | Called permissionlessly by anyone to update the voting epoch.                                     |
| `set_factory_and_fee_dist` | `(pair (address %factory) (address %fee_dist))`                                      | Called once during origination sequence to set the address for `CoreFactory` & `FeeDistributor`   |
| `add_amm`                  | `(pair %add_amm (address %amm) (pair (address %gauge) (address %bribe)))`            | Called by `CoreFactory` to whitelist an AMM.                                                      |
| `remove_amm`               | `address`                                                                            | Called by `CoreFactory` to remove whitelisted AMM.                                                |
| `vote`                     | `(pair %vote (nat %token_id) (list %vote_items (pair (address %amm) (nat %votes))))` | Called by a vePLY holder to vote for emission distribution across AMM `Gauges`.                   |
| `claim_bribe`              | `(pair (nat %token_id) (pair (nat %epoch) (pair (address %amm) (nat %bribe_id))))`   | Called by a voter to claim available bribes for an epoch.                                         |
| `claim_fee`                | `(pair (nat %token_id) (pair (address %amm) (list %epochs nat)))`                    | Called by a voter to claim fees collected from an AMM during an epoch.                            |
| `pull_amm_fee`             | `(pair (address %amm) (nat %epoch))`                                                 | Called permissionlessly once during each epoch to pull fees out of an AMM into `FeeDistributor`.  |
| `recharge_gauge`           | `(pair (address %amm) (nat %epoch))`                                                 | Called permissionlessly once during each epoch to recharge a `Gauge` contract with PLY emissions. |

## Views

| View                    | Parameters                                                  | Return Type            | Description                                                             |
| ----------------------- | ----------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| `get_current_epoch`     | `unit`                                                      | `(pair nat timestamp)` | Returns currently on-going epoch with its ending timestamp.             |
| `get_epoch_end`         | `nat`                                                       | `nat`                  | Returns the ending timestamp of a specific epoch.                       |
| `get_token_amm_votes`   | `(pair (nat %token_id) (pair (address %amm) (nat %epoch)))` | `nat`                  | Returns total votes given to an AMM using a specific token in an epoch. |
| `get_total_amm_votes`   | `(pair (address %amm) (nat %epoch))`                        | `nat`                  | Returns total votes received by an AMM during an epoch. .               |
| `get_total_token_votes` | `(pair (nat %token_id) (nat %epoch))`                       | `nat`                  | Returns total votes given by a specific token during an epoch.          |
| `get_total_epoch_votes` | `nat`                                                       | `nat`                  | Returns total votes given to all AMMs, by all tokens, during an epoch.  |
