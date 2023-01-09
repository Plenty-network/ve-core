# Gauge

**Gauge** contract allows for the following user-facing operations:

- Staking and withdrawal of LP tokens of the parent AMM.
- Claiming PLY emission rewards for staking LP tokens.

## Storage

| Storage Item                 | Type                    | Description                                                                                                                                     |
| ---------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `lp_token_address`           | `address`               | Address of the LP token contract of the parent AMM.                                                                                             |
| `ply_address`                | `address`               | Address of PLY FA1.2 token contract.                                                                                                            |
| `ve_address`                 | `address`               | Address of `VoteEscrow` contract.                                                                                                               |
| `voter`                      | `address`               | Address of `Voter` contract.                                                                                                                    |
| `reward_rate`                | `nat`                   | Current PLY emission rate every second for the gauge.                                                                                           |
| `reward_per_token`           | `nat`                   | Reward share for every unit LP token staked.                                                                                                    |
| `last_update_time`           | `nat`                   | The last UNIX timestamp at which gauge's reward metrics were updated.                                                                           |
| `period_finish`              | `nat`                   | UNIX timestamp at which the current reward emission period gets completed.                                                                      |
| `recharge_ledger`            | `(big_map nat unit)`    | Tracks if the gauge has been recharged at a particular epoch.                                                                                   |
| `user_reward_per_token_debt` | `(big_map address nat)` | Reward per token adjustment factor for a staker. The staker has already received this share, or is not entitled to it.                          |
| `balances`                   | `big_map address nat)`  | Records staked balance of a user.                                                                                                               |
| `derived_balances`           | `(big_map address nat)` | Records the balance of a user that is factored in for reward calculation. This is 40%-100% of the staked balance, depending on boosting status. |
| `attached_tokens`            | `(big_map address nat)` | Records the vePLY token-id that is used for boosting a stake.                                                                                   |
| `rewards`                    | `(big_map address nat)` | Records the reward amount that a user is entitled to.                                                                                           |
| `total_supply`               | `nat`                   | Total supply of staked LP tokens.                                                                                                               |
| `derived_supply`             | `nat`                   | Total supply corressponding to `derived_balances`.                                                                                              |

## Entrypoints

| Entrypoint   | Parameters                                    | Description                                                                            |
| ------------ | --------------------------------------------- | -------------------------------------------------------------------------------------- |
| `stake`      | `(pair (nat %amount) (nat %token_id))`        | Called by an LP token holder to stake their tokens and start receiving PLY emissions . |
| `withdraw`   | `nat`                                         | Called a staker to remove their LP token stake.                                        |
| `get_reward` | `unit`                                        | Called a staker to retrieve rewards accrued.                                           |
| `recharge`   | `(pair %recharge (nat %amount) (nat %epoch))` | Called by `Voter` contract fill up the gauge with PLY emissions for a certain epoch.   |

## Additional Information

- `stake` entrypoint requires Gauge contract to be an `FA2 operator` for the ve-NFT to execute the `update_attachments` entrypoint in `VoteEscrow` contract.
- `stake` entrypoint requires Gauge contract to have token transfer approval for associated AMM LP token.
