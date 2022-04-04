# VoteEscrow

**VoteEscrow** contract allows for the following user-facing operations:

- Lock PLY FA1.2 token for a specified period of time to get back a vePLY NFT that can be used to vote.
- Modify PLY lock by
  - Increasing lock value
  - Increasing lock time
- Withdraw PLY from a lock after expiry,
- FA2 transfer & update operators
- Attaching tokens

## Storage

| Storage Item            | Type                                                                                | Description                                                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `ledger`                | `(big_map (pair address nat) nat)`                                                  | Stores the vePLY token balance of Tezos addresses. Each vePLY is unique, so a ledger balance record can be either 1 or 0       |
| `operators`             | `(big_map (pair (address %owner) (pair (address %operator) (nat %token_id))) unit)` | Stores the FA2 operators for a token                                                                                           |
| `locks`                 | `(big_map nat (pair (nat %base_value) (nat %end)))`                                 | Stores the base PLY value and expiry timestamp of PLY locks                                                                    |
| `attached`              | `(big_map nat unit)`                                                                | Keeps track of attached locks. Attached tokens/locks cannot be transferred using FA2 Transfer                                  |
| `token_checkpoints`     | `(big_map (pair nat nat) (pair (nat %slope) (pair (nat %bias) (nat %ts))))`         | Records **bias** and **slope** values for the linearly decreasing voting power for a specific token-id at different timestamps |
| `num_token_checkpoints` | `(big_map nat nat)`                                                                 | Tracks the number of checkpoints for a specific token-id                                                                       |
| `global_checkpoints`    | `(big_map nat (pair (nat %slope) (pair (nat %bias) (nat %ts))))`                    | Records a global **bias** and **slope** values for the total voting power of the system at different timestamps                |
| `gc_index`              | `nat`                                                                               | Tracks the number of global checkpoints                                                                                        |
| `slope_changes`         | `(big_map nat nat)`                                                                 | Records changes in slopes at timestamps when a lock is expiring. These slope changes are used during global bias calculation   |
| `epoch_inflation`       | `(big_map nat nat)`                                                                 | Stores the PLY inflation for lockers are different epochs                                                                      |
| `claim_ledger`          | `(big_map (pair (nat %token_id) (nat %epoch)) unit)`                                | Tracks if a token holder has claimed the inflation for a certain epoch                                                         |
| `voter`                 | `address`                                                                           | Address of the `Voter` contract                                                                                                |
| `base_token`            | `address`                                                                           | Address of the PLY token contract                                                                                              |
| `locked_supply`         | `nat`                                                                               | Total PLY supply locked up under vePLY                                                                                         |

## Entrypoints

| Entrypoint            | Parameters                                                                                        | Description                                                                                                                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `transfer`            | FA2 transfer parameters                                                                           | FA2 transfer                                                                                                                                                                                    |
| `balance_of`          | FA2 balance_of parameters                                                                         | FA2 balance_of                                                                                                                                                                                  |
| `update_operators`    | FA2 update_operators parameters                                                                   | FA2 update_operators                                                                                                                                                                            |
| `update_attachments`  | `(pair (list %attachments (or (nat %add_attachment) (nat %remove_attachment))) (address %owner))` | Called by a `Gauge` contract to attach a token/lock to an LP stake for boosting. Attached tokens are non-transferrable.                                                                         |
| `create_lock`         | `(pair (address %user_address) (pair (nat %base_value) (nat %end)))`                              | Called by a PLY holder to create a new lock and retrieve a vePLY NFT in exchange. <ul><li><b>user_address: </b>The Tezos address where the vePLY associated to the lock must be sent.</li></ul> |
| `withdraw`            | `nat`                                                                                             | Called by a vePLY holder to withdraw base value from a lock after expiry.                                                                                                                       |
| `increase_lock_value` | `(pair (nat %token_id) (nat %value))`                                                             | Called by a vePLY holder to increase the base value of a lock.                                                                                                                                  |
| `increase_lock_end`   | `(pair (nat %token_id) (nat %end))`                                                               | Called by a vePLY holder to increase the expiry of a lock.                                                                                                                                      |
| `set_voter`           | `address`                                                                                         | Called once during the origination sequence to set the address of voter contract.                                                                                                               |
| `add_inflation`       | `(pair (nat %epoch) (nat %value))`                                                                | Called by the `Voter`contract once every epoch to set the PLY inflation.                                                                                                                        |
| `claim_inflation`     | `(pair (nat %token_id) (nat %epoch))`                                                             | Called by a vePLY holder to add inflation to the base value of a lock.                                                                                                                          |

## Views

| View                     | Parameters                                            | Return Type | Description                                                                                                                                                                                                                         |
| ------------------------ | ----------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_token_voting_power` | `(pair (nat %time) (pair (nat %token_id) (nat %ts)))` | `nat`       | Calculates and returns the voting power for a token at any timestamp. <ul><li><b>time: </b> 0- Get voting power at supplied timestamp. 1- Get voting power by rounding down the ts to a whole week (Thursday 12 AM (UTC))</li></ul> |
| `get_total_voting_power` | `(pair (nat %time) (nat %ts))`                        | `nat`       | Calculates and returns the total global voting power at any timestamp.                                                                                                                                                              |
| `is_owner`               | `(pair (address %address) (nat %token_id))`           | `bool`      | Returns boolean true if an address owns a specified lock/token.                                                                                                                                                                     |
| `get_locked_supply`      | `unit`                                                | `nat`       | Returns the total locked PLY supply in `VoteEscrow`.                                                                                                                                                                                |
