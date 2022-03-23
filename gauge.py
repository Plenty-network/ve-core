import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")

############
# Constants
############

DECIMALS = 10 ** 18
PRECISION = 10 ** 18

DAY = 86400
WEEK = 7 * DAY

########
# Types
########


class Types:
    CURRENT = 0
    WHOLE_WEEK = 1


#########
# Errors
#########


class Errors:
    SENDER_DOES_NOT_OWN_LOCK = "SENDER_DOES_NOT_OWN_LOCK"
    ZERO_WITHDRAWAL_NOT_ALLOWED = "ZERO_WITHDRAWAL_NOT_ALLOWED"
    ZERO_STAKE_NOT_ALLOWED = "ZERO_STAKE_NOT_ALLOWED"
    NO_STAKE_TO_WITHDRAW = "NO_STAKE_TO_WITHDRAW"

    # Generic
    INVALID_VIEW = "INVALID_VIEW"
    NOT_AUTHORISED = "NOT_AUTHORISED"


###########
# Contract
###########


class Gauge(sp.Contract):
    def __init__(
        self,
        lp_token_address=Addresses.TOKEN,
        ply_address=Addresses.TOKEN,
        ve_address=Addresses.CONTRACT,
        voter=Addresses.CONTRACT,
        reward_rate=sp.nat(0),
        reward_per_token=sp.nat(0),
        last_update_time=sp.nat(0),
        period_finish=sp.nat(0),
        user_reward_per_token_debt=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TNat,
        ),
        balances=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TNat,
        ),
        derived_balances=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TNat,
        ),
        attached_tokens=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TNat,
        ),
        rewards=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TNat,
        ),
        total_supply=sp.nat(0),
        derived_supply=sp.nat(0),
    ):
        self.init(
            lp_token_address=lp_token_address,
            ply_address=ply_address,
            ve_address=ve_address,
            voter=voter,
            reward_rate=reward_rate,
            reward_per_token=reward_per_token,
            last_update_time=last_update_time,
            period_finish=period_finish,
            user_reward_per_token_debt=user_reward_per_token_debt,
            balances=balances,
            derived_balances=derived_balances,
            attached_tokens=attached_tokens,
            rewards=rewards,
            total_supply=total_supply,
            derived_supply=derived_supply,
        )

    @sp.private_lambda(with_storage="read-write")
    def update_reward(self, address):
        sp.set_type(address, sp.TAddress)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Calculate reward/token-staked based on derived supply
        reward_per_token_ = sp.local("reward_per_token_", self.data.reward_per_token)
        with sp.if_(self.data.total_supply != 0):
            d_ts = sp.as_nat(sp.min(now_, self.data.period_finish) - self.data.last_update_time)
            reward_per_token_.value += (d_ts * self.data.reward_rate * PRECISION) // self.data.derived_supply

        self.data.reward_per_token = reward_per_token_.value

        # Update last update time
        self.data.last_update_time = sp.min(now_, self.data.period_finish)

        with sp.if_(address != Addresses.DUMMY):
            with sp.if_(~self.data.rewards.contains(address)):
                self.data.rewards[address] = 0

            # Update already earned rewards for the user
            self.data.rewards[address] += (
                self.data.derived_balances.get(address, 0)
                * sp.as_nat(self.data.reward_per_token - self.data.user_reward_per_token_debt.get(address, 0))
            ) // PRECISION

            self.data.user_reward_per_token_debt[address] = self.data.reward_per_token

    @sp.private_lambda(with_storage="read-write")
    def update_derived(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, token_id=sp.TNat))

        balance_ = self.data.balances[params.address]
        total_supply_ = self.data.total_supply

        derived_balance_ = self.data.derived_balances.get(params.address, 0)

        with sp.if_(derived_balance_ != 0):
            self.data.derived_supply = sp.as_nat(self.data.derived_supply - derived_balance_)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Calculate a mark_up if the user chooses to boost
        mark_up = sp.local("mark_up", sp.nat(0))

        with sp.if_(params.token_id != 0):
            # Get current voting power of token
            token_voting_power = sp.view(
                "get_token_voting_power",
                self.data.ve_address,
                sp.record(token_id=params.token_id, ts=now_, time=Types.CURRENT),
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            # Get total voting power of VE
            total_voting_power = sp.view(
                "get_total_voting_power",
                self.data.ve_address,
                sp.record(ts=now_, time=Types.CURRENT),
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            mark_up.value = (((self.data.total_supply * token_voting_power) // total_voting_power) * 60) // 100

        base_balance = (balance_ * 40) // 100
        self.data.derived_balances[params.address] = sp.min(base_balance + mark_up.value, balance_)
        self.data.derived_supply += self.data.derived_balances[params.address]

    @sp.entry_point
    def stake(self, params):
        sp.set_type(
            params,
            sp.TRecord(amount=sp.TNat, token_id=sp.TNat),
        )

        # Verify that staking amount is non zero
        sp.verify(params.amount > 0, Errors.ZERO_STAKE_NOT_ALLOWED)

        # Update global and user specific reward metrics
        self.data.update_reward(sp.sender)

        # Set balance and supply
        with sp.if_(~self.data.balances.contains(sp.sender)):
            self.data.balances[sp.sender] = sp.nat(0)
        self.data.balances[sp.sender] += params.amount
        self.data.total_supply += params.amount

        # Update derived balance and derived supply for boosting
        self.update_derived(sp.record(address=sp.sender, token_id=params.token_id))

        with sp.if_(params.token_id != 0):
            # Verify that the sender owns the specified token / lock
            is_owner = sp.view(
                "is_owner",
                self.data.ve_address,
                sp.record(address=sp.sender, token_id=params.token_id),
                sp.TBool,
            ).open_some(Errors.INVALID_VIEW)
            sp.verify(is_owner, Errors.SENDER_DOES_NOT_OWN_LOCK)

            with sp.if_(~self.data.attached_tokens.contains(sp.sender)):
                # Attach first token
                self.data.attached_tokens[sp.sender] = params.token_id

                # Attach tokens in ve
                TokenUtils.attach_tokens(
                    sp.record(
                        attachments=[(params.token_id, sp.bool(True))],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )
            with sp.if_(self.data.attached_tokens[sp.sender] != params.token_id):
                # Remove current attachment and attach fresh token in ve
                TokenUtils.attach_tokens(
                    sp.record(
                        attachments=[
                            (self.data.attached_tokens[sp.sender], sp.bool(False)),
                            (params.token_id, sp.bool(True)),
                        ],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )

                self.data.attached_tokens[sp.sender] = params.token_id

        # Retrieve lp tokens
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.sender,
                to_=sp.self_address,
                value=params.amount,
                token_address=self.data.lp_token_address,
            )
        )

    @sp.entry_point
    def withdraw(self, amount):
        sp.set_type(amount, sp.TNat)

        # Verify that withdrawal amount is non zero
        sp.verify(amount > 0, Errors.ZERO_WITHDRAWAL_NOT_ALLOWED)

        # Verify that sender has a stake
        sp.verify(self.data.balances[sp.sender] != 0, Errors.NO_STAKE_TO_WITHDRAW)

        # Update global and user specific reward metrics
        self.data.update_reward(sp.sender)

        # Transfer withdrawn tokens back to sender
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.self_address,
                to_=sp.sender,
                value=sp.min(amount, self.data.balances[sp.sender]),
                token_address=self.data.lp_token_address,
            )
        )

        # Modify balance and total supply
        self.data.balances[sp.sender] = sp.as_nat(
            self.data.balances[sp.sender] - sp.min(amount, self.data.balances[sp.sender])
        )
        self.data.total_supply = sp.as_nat(self.data.total_supply - sp.min(amount, self.data.balances[sp.sender]))

        # Update derived balance and derived supply for boosting
        self.update_derived(sp.record(address=sp.sender, token_id=self.data.attached_tokens.get(sp.sender, 0)))

        # Detach boost token if all balance is withdrawn
        with sp.if_(self.data.balances[sp.sender] == 0):
            with sp.if_(self.data.attached_tokens.contains(sp.sender)):
                # Detach tokens in ve
                TokenUtils.attach_tokens(
                    sp.record(
                        attachments=[(self.data.attached_tokens[sp.sender], sp.bool(False))],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )

                del self.data.attached_tokens[sp.sender]

    @sp.entry_point
    def get_reward(self):
        # Update global and user specific reward metrics
        self.data.update_reward(sp.sender)

        # If there is a non-zero reward to withdraw for the sender
        with sp.if_(self.data.rewards[sp.sender] != 0):
            # Transfer rewards to the user
            TokenUtils.transfer_FA12(
                sp.record(
                    from_=sp.self_address,
                    to_=sp.sender,
                    value=self.data.rewards[sp.sender],
                    token_address=self.data.ply_address,
                )
            )

            # Set rewards to 0
            self.data.rewards[sp.sender] = 0

    @sp.entry_point
    def recharge(self, amount):
        sp.set_type(amount, sp.TNat)

        # Verify that the voter is the sender
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)

        # Update global reward metrics
        self.data.update_reward(Addresses.DUMMY)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Calculate current finish period
        # NOTE: Since new recharge period must start after previous epoch ends, no two periods would overlap.
        self.data.period_finish = ((now_ + WEEK) // WEEK) * WEEK

        # Calculate duration of rewards distribution. Should be ~ 7 days
        duration = sp.as_nat(self.data.period_finish - now_)

        # Set new reward rate for the week
        self.data.reward_rate = amount // duration

        # Set last update time to now
        self.data.last_update_time = now_


if __name__ == "__main__":
    sp.add_compilation_target("gauge", Gauge())
