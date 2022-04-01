# Bribe

**Bribe** contract allows for the following user-facing operations:

- Addition of bribes for a specific epoch.
- Claiming of bribes for a specific epoch by the voters.

## Storage

| Storage Item   | Type                                                                                                                      | Description                                     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `uid`          | `nat`                                                                                                                     | A unique id for every added bribe.              |
| `voter`        | `address`                                                                                                                 | Address of `Voter` contract.                    |
| `epoch_bribes` | `(big_map (pair (nat %epoch) (nat %bribe_id)) (pair (address %token_address) (pair (pair %type nat nat) (nat %amount))))` | Records the bribes added at specific epochs.    |
| `claim_ledger` | `(big_map (pair (nat %token_id) (nat %bribe_id)) unit)`                                                                   | Tracks if a voter has claimed a specific bribe. |

## Entrypoints

| Entrypoint  | Parameters                                                                                                      | Description                                                                                                                                               |
| ----------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add_bribe` | `(pair (nat %epoch) (pair (address %token_address) (pair (pair %type nat nat) (nat %amount))))`                 | Called by an individual or a protocol to insert a bribe for voters of parent AMM in a certain epoch. The bribe can be added in both FA1.2 and FA2 tokens. |
| `claim`     | `(pair (nat %token_id) (pair (address %owner) (pair (nat %epoch) (pair (nat %bribe_id) (nat %weight_share)))))` | Called by voter to claim a specific bribe for a specific epoch.                                                                                           |
