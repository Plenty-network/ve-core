import smartpy as sp

Errors = sp.io.import_script_from_url("file:utils/errors.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
VE = sp.io.import_script_from_url("file:helpers/dummy/ve.py").VE
Constants = sp.io.import_script_from_url("file:utils/constants.py")
Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")


############
# Constants
############

DAY = Constants.DAY
WEEK = Constants.WEEK
DECIMALS = Constants.DECIMALS
PRECISION = Constants.PRECISION

########
# Types
########


class Types:

    # Enumeration for voting power readers
    CURRENT = sp.nat(0)  # Curren timestamp
    WHOLE_WEEK = sp.nat(1)  # Timestamp rounded down to a whole week


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
        recharge_ledger=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TUnit,
        ),
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
            recharge_ledger=recharge_ledger,
            user_reward_per_token_debt=user_reward_per_token_debt,
            balances=balances,
            derived_balances=derived_balances,
            attached_tokens=attached_tokens,
            rewards=rewards,
            total_supply=total_supply,
            derived_supply=derived_supply,
        )

        self.init_type(
            sp.TRecord(
                lp_token_address=sp.TAddress,
                ply_address=sp.TAddress,
                ve_address=sp.TAddress,
                voter=sp.TAddress,
                reward_rate=sp.TNat,
                reward_per_token=sp.TNat,
                last_update_time=sp.TNat,
                period_finish=sp.TNat,
                recharge_ledger=sp.TBigMap(sp.TNat, sp.TUnit),
                user_reward_per_token_debt=sp.TBigMap(sp.TAddress, sp.TNat),
                balances=sp.TBigMap(sp.TAddress, sp.TNat),
                derived_balances=sp.TBigMap(sp.TAddress, sp.TNat),
                attached_tokens=sp.TBigMap(sp.TAddress, sp.TNat),
                rewards=sp.TBigMap(sp.TAddress, sp.TNat),
                total_supply=sp.TNat,
                derived_supply=sp.TNat,
            )
        )

    @sp.private_lambda(with_storage="read-write", wrap_call=True)
    def update_reward(self, address):
        sp.set_type(address, sp.TAddress)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        # Store as local variable to keep on stack
        period_finish = sp.compute(self.data.period_finish)

        # Calculate reward/token-staked based on derived supply
        reward_per_token_ = sp.local("reward_per_token_", self.data.reward_per_token)
        with sp.if_(self.data.total_supply != 0):
            d_ts = sp.as_nat(sp.min(now_, period_finish) - self.data.last_update_time)
            reward_per_token_.value += (d_ts * self.data.reward_rate * PRECISION) // self.data.derived_supply

        self.data.reward_per_token = reward_per_token_.value

        # Store as local variable to keep on stack
        reward_per_token = sp.compute(self.data.reward_per_token)

        # Update last update time
        self.data.last_update_time = sp.min(now_, period_finish)

        with sp.if_(address != Addresses.DUMMY):
            existing_rewards = self.data.rewards.get(address, 0)

            # Update already earned rewards for the user
            self.data.rewards[address] = (
                existing_rewards
                + (
                    self.data.derived_balances.get(address, 0)
                    * sp.as_nat(reward_per_token - self.data.user_reward_per_token_debt.get(address, 0))
                )
                // PRECISION
            )

            self.data.user_reward_per_token_debt[address] = reward_per_token

    @sp.private_lambda(with_storage="read-write", wrap_call=True)
    def update_derived(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, token_id=sp.TNat))

        balance_ = sp.compute(self.data.balances[params.address])

        derived_balance_ = sp.compute(self.data.derived_balances.get(params.address, 0))

        with sp.if_(derived_balance_ != 0):
            self.data.derived_supply = sp.as_nat(self.data.derived_supply - derived_balance_)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

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

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Update global and user specific reward metrics
        self.update_reward(sp.sender)

        # Set balance and supply
        balance = self.data.balances.get(sp.sender, 0)
        self.data.balances[sp.sender] = balance + params.amount
        self.data.total_supply += params.amount

        # Update derived balance and derived supply for boosting
        self.update_derived(sp.record(address=sp.sender, token_id=params.token_id))

        with sp.if_(params.token_id != 0):
            # If there is no token attached
            with sp.if_(~self.data.attached_tokens.contains(sp.sender)):
                # Attach first token
                self.data.attached_tokens[sp.sender] = params.token_id

                # Attach tokens in ve
                TokenUtils.update_token_attachments(
                    sp.record(
                        attachments=[sp.variant("add_attachment", params.token_id)],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )
            # If a new token is being attached
            with sp.if_(self.data.attached_tokens[sp.sender] != params.token_id):
                # Remove current attachment and attach fresh token in ve
                TokenUtils.update_token_attachments(
                    sp.record(
                        attachments=[
                            sp.variant("remove_attachment", self.data.attached_tokens[sp.sender]),
                            sp.variant("add_attachment", params.token_id),
                        ],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )

                self.data.attached_tokens[sp.sender] = params.token_id
        with sp.else_():
            # If a token is attached, then detach it
            with sp.if_(self.data.attached_tokens.contains(sp.sender)):
                TokenUtils.update_token_attachments(
                    sp.record(
                        attachments=[
                            sp.variant("remove_attachment", self.data.attached_tokens[sp.sender]),
                        ],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )

                del self.data.attached_tokens[sp.sender]

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

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Verify that withdrawal amount is non zero
        sp.verify(amount > 0, Errors.ZERO_WITHDRAWAL_NOT_ALLOWED)

        # Verify that sender has a stake
        sp.verify(self.data.balances.get(sp.sender, 0) != 0, Errors.NO_STAKE_TO_WITHDRAW)

        # Update global and user specific reward metrics
        self.update_reward(sp.sender)

        # Store as local variable to keep on stack
        balance = sp.compute(self.data.balances[sp.sender])

        # Transfer withdrawn tokens back to sender
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.self_address,
                to_=sp.sender,
                value=sp.min(amount, balance),
                token_address=self.data.lp_token_address,
            )
        )

        # Modify balance and total supply
        self.data.total_supply = sp.as_nat(self.data.total_supply - sp.min(amount, balance))
        self.data.balances[sp.sender] = sp.as_nat(balance - sp.min(amount, balance))

        # Detach boost token if all balance is withdrawn
        with sp.if_(self.data.balances[sp.sender] == 0):
            with sp.if_(self.data.attached_tokens.contains(sp.sender)):
                # Detach tokens in ve
                TokenUtils.update_token_attachments(
                    sp.record(
                        attachments=[
                            sp.variant("remove_attachment", self.data.attached_tokens[sp.sender]),
                        ],
                        ve_address=self.data.ve_address,
                        owner=sp.sender,
                    )
                )

                del self.data.attached_tokens[sp.sender]

        # Update derived balance and derived supply for boosting
        self.update_derived(sp.record(address=sp.sender, token_id=self.data.attached_tokens.get(sp.sender, 0)))

    @sp.entry_point
    def get_reward(self):
        # Update global and user specific reward metrics
        self.update_reward(sp.sender)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

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
    def recharge(self, params):
        sp.set_type(params, sp.TRecord(amount=sp.TNat, epoch=sp.TNat))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Verify that the voter is the sender
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)

        # verify that recharge is not already done for required epoch
        sp.verify(~self.data.recharge_ledger.contains(params.epoch), Errors.ALREADY_RECHARGED_FOR_EPOCH)

        # Update global reward metrics
        self.update_reward(Addresses.DUMMY)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        final_amount = sp.local("final_amount", params.amount)

        # If period has not ended (possible only when a past missed recharge is being done)
        with sp.if_(now_ < self.data.period_finish):
            remaining_rewards = self.data.reward_rate * sp.as_nat(self.data.period_finish - now_)
            final_amount.value = remaining_rewards + params.amount

        # Calculate current finish period
        # NOTE: Since new recharge period must start after previous epoch ends, no two periods would overlap.
        # Missed past recharges are accumulated within the current period itself.
        self.data.period_finish = ((now_ + WEEK) // WEEK) * WEEK

        # Calculate duration of rewards distribution. Should be ~ 7 days
        duration = sp.as_nat(self.data.period_finish - now_)

        # Set new reward rate for the week
        self.data.reward_rate = final_amount.value // duration

        # Set last update time to now
        self.data.last_update_time = now_

        # Mark recharged for the epoch
        self.data.recharge_ledger[params.epoch] = sp.unit

    # Reject tez sent to the contract address
    @sp.entry_point
    def default(self):
        sp.failwith(Errors.CONTRACT_DOES_NOT_ACCEPT_TEZ)


if __name__ == "__main__":

    #####################
    # stake (valid test)
    #####################

    @sp.add_test(name="stake works correctly when multiple users stake their LP tokens")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        lp_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        gauge = Gauge(
            lp_token_address=lp_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=10,
            reward_rate=sp.nat(500),
        )

        scenario += lp_token
        scenario += ve
        scenario += gauge

        # Mint lp tokens for the stakers - ALICE and BOB
        scenario += lp_token.mint(
            address=Addresses.ALICE,
            value=sp.nat(50 * DECIMALS),
        ).run(sender=Addresses.ADMIN)
        scenario += lp_token.mint(
            address=Addresses.BOB,
            value=sp.nat(75 * DECIMALS),
        ).run(sender=Addresses.ADMIN)

        # Approve tokens for ALICE and BOB with gauge as spender
        scenario += lp_token.approve(
            spender=gauge.address,
            value=sp.nat(50 * DECIMALS),
        ).run(sender=Addresses.ALICE)
        scenario += lp_token.approve(
            spender=gauge.address,
            value=sp.nat(75 * DECIMALS),
        ).run(sender=Addresses.BOB)

        # When ALICE stakes her LP tokens using lock with token-id 1 to boost
        scenario += gauge.stake(amount=50 * DECIMALS, token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(DAY),
        )

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == 0)
        scenario.verify(gauge.data.last_update_time == DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 32 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 32 * DECIMALS)

        # Gauge retrieves the LP tokens
        scenario.verify(lp_token.data.balances[gauge.address].balance == 50 * DECIMALS)

        # When BOB stakes his LP tokens without any boost i.e using token_id 0
        scenario += gauge.stake(amount=75 * DECIMALS, token_id=0).run(
            sender=Addresses.BOB,
            now=sp.timestamp(2 * DAY),  # A day after ALICE stakes
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (32 * DECIMALS)

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 125 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.BOB] == 75 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.BOB] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.BOB] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.BOB] == 30 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 62 * DECIMALS)

        # Gauge retrieves the LP tokens
        scenario.verify(lp_token.data.balances[gauge.address].balance == 125 * DECIMALS)

    @sp.add_test(name="stake works correctly when already staked user stakes extra tokens")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        lp_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        gauge = Gauge(
            lp_token_address=lp_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=10,
            reward_rate=sp.nat(500),
        )

        scenario += lp_token
        scenario += ve
        scenario += gauge

        # Mint lp tokens for ALICE
        scenario += lp_token.mint(
            address=Addresses.ALICE,
            value=sp.nat(100 * DECIMALS),
        ).run(sender=Addresses.ADMIN)

        # Approve tokens for ALICE
        scenario += lp_token.approve(
            spender=gauge.address,
            value=sp.nat(100 * DECIMALS),
        ).run(sender=Addresses.ALICE)

        # When ALICE stakes her LP tokens using lock with token-id 1 to boost
        scenario += gauge.stake(amount=50 * DECIMALS, token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(DAY),
        )

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == 0)
        scenario.verify(gauge.data.last_update_time == DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 32 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 32 * DECIMALS)

        # Gauge retrieves the LP tokens
        scenario.verify(lp_token.data.balances[gauge.address].balance == 50 * DECIMALS)

        # When ALICE stakes more LP tokens using lock with token-id 2 to boost
        scenario += gauge.stake(amount=25 * DECIMALS, token_id=2).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * DAY),  # One day later to original stake
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_ = (reward_per_token_ * 32 * DECIMALS) // PRECISION

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 75 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 75 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == reward_)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 57 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 57 * DECIMALS)

        # Gauge retrieves the LP tokens
        scenario.verify(lp_token.data.balances[gauge.address].balance == 75 * DECIMALS)

        # When ALICE stakes more LP tokens and remove a boost lock
        scenario += gauge.stake(amount=25 * DECIMALS, token_id=0).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(3 * DAY),  # One day later to second stake
        )

        # Predicted values
        reward_per_token__ = reward_per_token_ + (DAY * 500 * PRECISION) // (57 * DECIMALS)
        reward__ = reward_ + ((reward_per_token__ - reward_per_token_) * 57 * DECIMALS) // PRECISION

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 100 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 100 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token__)
        scenario.verify(gauge.data.last_update_time == 3 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token__)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == reward__)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 40 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 40 * DECIMALS)

    @sp.add_test(name="stake works correctly when unboosted staked user attempts to boost")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        lp_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        gauge = Gauge(
            lp_token_address=lp_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=10,
            reward_rate=sp.nat(500),
        )

        scenario += lp_token
        scenario += ve
        scenario += gauge

        # Mint lp tokens for ALICE
        scenario += lp_token.mint(
            address=Addresses.ALICE,
            value=sp.nat(100 * DECIMALS),
        ).run(sender=Addresses.ADMIN)

        # Approve tokens for ALICE
        scenario += lp_token.approve(
            spender=gauge.address,
            value=sp.nat(100 * DECIMALS),
        ).run(sender=Addresses.ALICE)

        # When ALICE stakes her LP tokens without any boost
        scenario += gauge.stake(amount=50 * DECIMALS, token_id=0).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(DAY),
        )

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == 0)
        scenario.verify(gauge.data.last_update_time == DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 20 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 20 * DECIMALS)

        # Gauge retrieves the LP tokens
        scenario.verify(lp_token.data.balances[gauge.address].balance == 50 * DECIMALS)

        # When ALICE boosts by calling stake with 0 amount and adding a token only
        scenario += gauge.stake(amount=0 * DECIMALS, token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * DAY),  # One day later to original stake
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (20 * DECIMALS)
        reward_ = (reward_per_token_ * 20 * DECIMALS) // PRECISION

        # The storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == reward_)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 32 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 32 * DECIMALS)

    ########################
    # withdraw (valid test)
    ########################

    @sp.add_test(name="withdraw works correctly for partial withdrawal")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        lp_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        # Set gauge to relevant initial values with ALICE as a staker
        gauge = Gauge(
            lp_token_address=lp_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=DAY,
            reward_rate=sp.nat(500),
            user_reward_per_token_debt=sp.big_map(
                l={Addresses.ALICE: 0},
            ),
            reward_per_token=sp.nat(0),
            rewards=sp.big_map(
                l={
                    Addresses.ALICE: 0,
                }
            ),
            attached_tokens=sp.big_map(
                l={Addresses.ALICE: 1},
            ),
            balances=sp.big_map(
                l={Addresses.ALICE: 50 * DECIMALS},
            ),
            total_supply=50 * DECIMALS,
            derived_balances=sp.big_map(
                l={Addresses.ALICE: 32 * DECIMALS},
            ),
            derived_supply=32 * DECIMALS,
        )

        scenario += lp_token
        scenario += ve
        scenario += gauge

        # Mint L.P tokens for the gauge
        scenario += lp_token.mint(
            address=gauge.address,
            value=sp.nat(50 * DECIMALS),
        ).run(sender=Addresses.ADMIN)

        # When ALICE withdraws her stake
        scenario += gauge.withdraw(25 * DECIMALS).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * DAY),  # a DAY after staking
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_ = (reward_per_token_ * 32 * DECIMALS) // PRECISION

        # Storage is updated correctly
        scenario.verify(gauge.data.total_supply == 25 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 25 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == reward_)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 16 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 16 * DECIMALS)
        scenario.verify(gauge.data.attached_tokens[Addresses.ALICE] == 1)

        # ALICE received withdrawn LP tokens
        scenario.verify(lp_token.data.balances[Addresses.ALICE].balance == 25 * DECIMALS)

    @sp.add_test(name="withdraw works correctly for complete withdrawal")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        lp_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        # Set gauge to relevant initial values with ALICE as a staker
        gauge = Gauge(
            lp_token_address=lp_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=DAY,
            reward_rate=sp.nat(500),
            user_reward_per_token_debt=sp.big_map(
                l={Addresses.ALICE: 0},
            ),
            reward_per_token=sp.nat(0),
            rewards=sp.big_map(
                l={
                    Addresses.ALICE: 0,
                }
            ),
            attached_tokens=sp.big_map(
                l={Addresses.ALICE: 1},
            ),
            balances=sp.big_map(
                l={Addresses.ALICE: 50 * DECIMALS},
            ),
            total_supply=50 * DECIMALS,
            derived_balances=sp.big_map(
                l={Addresses.ALICE: 32 * DECIMALS},
            ),
            derived_supply=32 * DECIMALS,
        )

        scenario += lp_token
        scenario += ve
        scenario += gauge

        # Mint L.P tokens for the gauge
        scenario += lp_token.mint(
            address=gauge.address,
            value=sp.nat(50 * DECIMALS),
        ).run(sender=Addresses.ADMIN)

        # When ALICE withdraws her stake completely (passing > than staked value)
        scenario += gauge.withdraw(51 * DECIMALS).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * DAY),  # a DAY after staking
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_ = (reward_per_token_ * 32 * DECIMALS) // PRECISION

        # Storage is updated correctly
        scenario.verify(gauge.data.total_supply == 0)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == reward_)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_supply == 0)
        scenario.verify(~gauge.data.attached_tokens.contains(Addresses.ALICE))

        # ALICE received withdrawn LP tokens
        scenario.verify(lp_token.data.balances[Addresses.ALICE].balance == 50 * DECIMALS)

    ##########################
    # withdraw (failure test)
    ##########################

    @sp.add_test(name="withdraw fails for zero amount withdrawals")
    def test():
        scenario = sp.test_scenario()

        gauge = Gauge()

        scenario += gauge

        # When ALICE tries to withdraw 0 L.P tokens, the txn fails
        scenario += gauge.withdraw(0 * DECIMALS).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(DAY),
            valid=False,
            exception=Errors.ZERO_WITHDRAWAL_NOT_ALLOWED,
        )

    @sp.add_test(name="withdraw fails if the sender does not have a stake")
    def test():
        scenario = sp.test_scenario()

        gauge = Gauge()

        scenario += gauge

        # When ALICE tries to withdraw 0 L.P tokens, the txn fails
        scenario += gauge.withdraw(25 * DECIMALS).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(DAY),
            valid=False,
            exception=Errors.NO_STAKE_TO_WITHDRAW,
        )

    ##########################
    # get_reward (valid test)
    ##########################

    @sp.add_test(name="get_reward works correctly for retrievals in the middle of a period")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        ply_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        # Set gauge to relevant initial values with ALICE as a staker
        gauge = Gauge(
            ply_address=ply_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=DAY,
            reward_rate=sp.nat(500),
            user_reward_per_token_debt=sp.big_map(
                l={Addresses.ALICE: 0},
            ),
            reward_per_token=sp.nat(0),
            rewards=sp.big_map(
                l={
                    Addresses.ALICE: 0,
                }
            ),
            attached_tokens=sp.big_map(
                l={Addresses.ALICE: 1},
            ),
            balances=sp.big_map(
                l={Addresses.ALICE: 50 * DECIMALS},
            ),
            total_supply=50 * DECIMALS,
            derived_balances=sp.big_map(
                l={Addresses.ALICE: 32 * DECIMALS},
            ),
            derived_supply=32 * DECIMALS,
        )

        scenario += ply_token
        scenario += ve
        scenario += gauge

        # Mint PLY tokens for the gauge
        scenario += ply_token.mint(
            address=gauge.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)

        # When ALICE retrieves her reward at 2 * DAY
        scenario += gauge.get_reward().run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * DAY),
        )

        # Predicted values
        reward_per_token_ = (DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_ = (reward_per_token_ * 32 * DECIMALS) // PRECISION

        # Storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == 2 * DAY)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 32 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 32 * DECIMALS)

        # ALICE receives her ply reward
        scenario.verify(ply_token.data.balances[Addresses.ALICE].balance == reward_)

    @sp.add_test(name="get_reward works correctly for retrievals after the end of a period")
    def test():
        scenario = sp.test_scenario()

        # Staking LP token
        ply_token = FA12(admin=Addresses.ADMIN)

        # Initialize dummy voting powers for token id's 1 and 2 in ve
        ve = VE(
            powers=sp.big_map(l={1: sp.nat(100 * DECIMALS), 2: sp.nat(150 * DECIMALS)}),
            total_power=sp.nat(250 * DECIMALS),
        )

        # Set gauge to relevant initial values with ALICE as a staker
        gauge = Gauge(
            ply_address=ply_token.address,
            ve_address=ve.address,
            period_finish=WEEK,
            last_update_time=DAY,
            reward_rate=sp.nat(500),
            user_reward_per_token_debt=sp.big_map(
                l={Addresses.ALICE: 0},
            ),
            reward_per_token=sp.nat(0),
            rewards=sp.big_map(
                l={
                    Addresses.ALICE: 0,
                }
            ),
            attached_tokens=sp.big_map(
                l={Addresses.ALICE: 1},
            ),
            balances=sp.big_map(
                l={Addresses.ALICE: 50 * DECIMALS},
            ),
            total_supply=50 * DECIMALS,
            derived_balances=sp.big_map(
                l={Addresses.ALICE: 32 * DECIMALS},
            ),
            derived_supply=32 * DECIMALS,
        )

        scenario += ply_token
        scenario += ve
        scenario += gauge

        # Mint PLY tokens for the gauge
        scenario += ply_token.mint(
            address=gauge.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)

        # When ALICE retrieves her reward at 9 * DAY (After end of period i.e WEEK)
        scenario += gauge.get_reward().run(
            sender=Addresses.ALICE,
            now=sp.timestamp(9 * DAY),
        )

        # Predicted values
        reward_per_token_ = (6 * DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_ = (reward_per_token_ * 32 * DECIMALS) // PRECISION

        # Storage is updated correctly
        scenario.verify(gauge.data.total_supply == 50 * DECIMALS)
        scenario.verify(gauge.data.balances[Addresses.ALICE] == 50 * DECIMALS)
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == WEEK)
        scenario.verify(gauge.data.user_reward_per_token_debt[Addresses.ALICE] == reward_per_token_)
        scenario.verify(gauge.data.rewards[Addresses.ALICE] == 0)
        scenario.verify(gauge.data.derived_balances[Addresses.ALICE] == 32 * DECIMALS)
        scenario.verify(gauge.data.derived_supply == 32 * DECIMALS)

        # ALICE receives her ply reward
        scenario.verify(ply_token.data.balances[Addresses.ALICE].balance == reward_)

    ########################
    # recharge (valid test)
    ########################

    @sp.add_test(name="recharge correctly updates the reward metrics")
    def test():
        scenario = sp.test_scenario()

        # Set gauge to relevant initial values with ALICE as a staker
        gauge = Gauge(
            period_finish=WEEK,
            last_update_time=DAY,
            reward_rate=sp.nat(500),
            user_reward_per_token_debt=sp.big_map(
                l={Addresses.ALICE: 0},
            ),
            reward_per_token=sp.nat(0),
            rewards=sp.big_map(
                l={
                    Addresses.ALICE: 0,
                }
            ),
            attached_tokens=sp.big_map(
                l={Addresses.ALICE: 1},
            ),
            balances=sp.big_map(
                l={Addresses.ALICE: 50 * DECIMALS},
            ),
            total_supply=50 * DECIMALS,
            derived_balances=sp.big_map(
                l={Addresses.ALICE: 32 * DECIMALS},
            ),
            derived_supply=32 * DECIMALS,
        )

        scenario += gauge

        # When the gauge is recharged with 10 PLY tokens after epoch completion
        scenario += gauge.recharge(amount=10 * DECIMALS, epoch=2).run(
            sender=Addresses.CONTRACT,
            now=sp.timestamp(WEEK + 5),  # 5 is random. Timestamp must be higher than a week
        )

        # Predicted values
        reward_per_token_ = (6 * DAY * 500 * PRECISION) // (32 * DECIMALS)
        reward_rate_ = (10 * DECIMALS) // (WEEK - 5)

        # Storage is updated correctly
        scenario.verify(gauge.data.reward_per_token == reward_per_token_)
        scenario.verify(gauge.data.last_update_time == WEEK + 5)
        scenario.verify(gauge.data.reward_rate == reward_rate_)

        # When the gauge is recharged with 10 PLY tokens for a past missed epoch 1
        scenario += gauge.recharge(amount=10 * DECIMALS, epoch=1).run(
            sender=Addresses.CONTRACT,
            now=sp.timestamp(WEEK + 7),  # 7 is random. Timestamp must be higher than a week and previous recharge
        )

        # Predicted values
        reward_per_token__ = reward_per_token_ + ((7 - 5) * reward_rate_ * PRECISION) // (32 * DECIMALS)
        reward_rate__ = (10 * DECIMALS + ((WEEK - 7) * reward_rate_)) // (WEEK - 7)

        # Storage is updated correctly
        scenario.verify(gauge.data.reward_per_token == reward_per_token__)
        scenario.verify(gauge.data.last_update_time == WEEK + 7)
        scenario.verify(gauge.data.reward_rate == reward_rate__)

    ##########################
    # recharge (failure test)
    ##########################

    @sp.add_test(name="recharge fails if the gauge is already recharged for an epoch")
    def test():
        scenario = sp.test_scenario()

        gauge = Gauge(
            recharge_ledger=sp.big_map(
                l={1: sp.unit},
            ),
        )

        scenario += gauge

        # When the gauge is recharged again for epoch 1, the txn fails
        scenario += gauge.recharge(amount=10 * DECIMALS, epoch=1).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.ALREADY_RECHARGED_FOR_EPOCH,
        )

    sp.add_compilation_target("gauge", Gauge())
