# Bribe

**Bribe** contract allows for the following user-facing operations:

- Addition of bribes for a specific epoch.
- Claiming of bribes for a specific epoch by the voters.

## Storage

| Storage Item   | Type                                                                                                                                                                      | Description                                                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `uid`          | `nat`                                                                                                                                                                     | A unique id for every added bribe.                                  |
| `voter`        | `address`                                                                                                                                                                 | Address of `Voter` contract.                                        |
| `epoch_bribes` | `(big_map (pair (nat %epoch) (nat %bribe_id)) (pair (address %provider) (pair %bribe (or %type (address %fa12) (or (pair %fa2 address nat) (unit %tez))) (nat %value))))` | Records the bribes (and associated token) added at specific epochs. |
| `claim_ledger` | `(big_map (pair (nat %token_id) (nat %bribe_id)) unit)`                                                                                                                   | Tracks if a voter has claimed a specific bribe.                     |

## Entrypoints

| Entrypoint     | Parameters                                                                                                    | Description                                                                                                                                                                                                                                         |
| -------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add_bribe`    | `(pair (nat %epoch) (pair (or %type (address %fa12) (or (pair %fa2 address nat) (unit %tez))) (nat %value)))` | Called by an individual or a protocol to insert a bribe for voters of parent AMM in a certain epoch. The bribe can be added in tez, FA1.2 & FA2 tokens.                                                                                             |
| `claim`        | `(pair (nat %token_id) (pair (address %owner) (pair (nat %epoch) (pair (nat %bribe_id) (nat %vote_share)))))` | Called by a voter to claim a specific bribe for a specific epoch. <ul><li><b>token_id:</b> The FA2 token-id of vePLY used to vote.</li><li><b>vote_share:</b> ratio of AMM votes for the epoch, that belongs to the provided vePLY token.</li></ul> |
| `return_bribe` | `(pair (nat %epoch) (nat %bribe_id))`                                                                         | Called through `claim` entrypoint `Voter` to return bribe to provider when no votes have been received by an AMM for an epoch                                                                                                                       |

## Additional Information

- `add_bribe` entrypoint requires token transfer approval to be given to Bribe contract for FA1.2 and FA2 tokens.
