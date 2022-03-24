import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
VE = sp.io.import_script_from_url("file:helpers/dummy/ve.py").VE
Ply = sp.io.import_script_from_url("file:helpers/dummy/ply.py").Ply
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
GaugeBribe = sp.io.import_script_from_url("file:helpers/dummy/gauge_bribe.py").GaugeBribe

############
# Constants
############

DECIMALS = 10 ** 18

DAY = 86400
WEEK = 7 * DAY
YEAR = 52 * WEEK
MAX_TIME = 4 * YEAR

VOTE_SHARE_MULTIPLIER = 10 ** 18

# Initial weekly ply inflation in number of tokens
INITIAL_INFLATION = 2_000_000 * DECIMALS

# Long term fixed trailing inflation rate after high inflation period is over
TRAIL_INFLATION = 10_000 * DECIMALS

# The precision multiplier for drop percentages
DROP_GRANULARITY = 1_000_000

# Inflation drop after the high initial rate for 4 weeks (period may change)
# This implies inflation drops to 35% of the initial value
INITIAL_DROP = 35 * DROP_GRANULARITY  # Percentage with granularity

# Inflation drop after every one year
YEARLY_DROP = 55 * DROP_GRANULARITY  # Percentage with granularity

########
# Types
########


class Types:

    # Bigmap key and value types

    TOKEN_AMM_VOTES_KEY = sp.TRecord(
        token_id=sp.TNat,
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("token_id", ("amm", "epoch")))

    TOTAL_AMM_VOTES_KEY = sp.TRecord(
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("amm", "epoch"))

    TOTAL_TOKEN_VOTES_KEY = sp.TRecord(
        token_id=sp.TNat,
        epoch=sp.TNat,
    ).layout(("token_id", "epoch"))

    AMM_TO_GAUGE_BRIBE = sp.TRecord(
        gauge=sp.TAddress,
        bribe=sp.TAddress,
    ).layout(("gauge", "bribe"))

    # Param types

    ADD_AMM_PARAMS = sp.TRecord(
        amm=sp.TAddress,
        gauge=sp.TAddress,
        bribe=sp.TAddress,
    ).layout(("amm", ("gauge", "bribe")))

    VOTE_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        vote_items=sp.TList(
            sp.TRecord(
                amm=sp.TAddress,
                votes=sp.TNat,
            )
        ),
    ).layout(("token_id", "vote_items"))

    CLAIM_BRIBE_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        epoch=sp.TNat,
        amm=sp.TAddress,
        bribe_id=sp.TNat,
    ).layout(("token_id", ("epoch", ("amm", "bribe_id"))))

    CLAIM_FEE_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        epoch=sp.TNat,
        amm=sp.TAddress,
    ).layout(("token_id", ("epoch", "amm")))

    # Enumeration for voting power readers
    CURRENT = sp.nat(0)
    WHOLE_WEEK = sp.nat(1)


#########
# Errors
#########


class Errors:
    EPOCH_ENDED = "EPOCH_ENDED"
    PREVIOUS_EPOCH_YET_TO_END = "PREVIOUS_EPOCH_YET_TO_END"
    INVALID_EPOCH = "INVALID_EPOCH"
    AMM_INVALID_OR_NOT_WHITELISTED = "AMM_INVALID_OR_NOT_WHITELISTED"
    SENDER_DOES_NOT_OWN_LOCK = "SENDER_DOES_NOT_OWN_LOCK"
    ZERO_VOTE_NOT_ALLOWED = "ZERO_VOTE_NOT_ALLOWED"
    NOT_ENOUGH_VOTING_POWER_AVAILABLE = "NOT_ENOUGH_VOTING_POWER_AVAILABLE"

    # Generic
    INVALID_VIEW = "INVALID_VIEW"
    NOT_AUTHORISED = "NOT_AUTHORISED"


###########
# Contract
###########


class Voter(sp.Contract):
    def __init__(
        self,
        epoch=sp.nat(0),
        epoch_end=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TTimestamp,
        ),
        amm_to_gauge_bribe=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=Types.AMM_TO_GAUGE_BRIBE,
        ),
        total_amm_votes=sp.big_map(
            l={},
            tkey=Types.TOTAL_AMM_VOTES_KEY,
            tvalue=sp.TNat,
        ),
        token_amm_votes=sp.big_map(
            l={},
            tkey=Types.TOKEN_AMM_VOTES_KEY,
            tvalue=sp.TNat,
        ),
        total_token_votes=sp.big_map(
            l={},
            tkey=Types.TOTAL_TOKEN_VOTES_KEY,
            tvalue=sp.TNat,
        ),
        total_epoch_votes=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TNat,
        ),
        emission=sp.record(
            base=INITIAL_INFLATION,
            real=sp.nat(0),
            genesis=sp.nat(0),
        ),
        core_factory=Addresses.DUMMY,
        fee_distributor=Addresses.DUMMY,
        ply_address=Addresses.TOKEN,
        ve_address=Addresses.CONTRACT,
    ):
        self.init(
            epoch=epoch,
            epoch_end=epoch_end,
            amm_to_gauge_bribe=amm_to_gauge_bribe,
            total_amm_votes=total_amm_votes,
            token_amm_votes=token_amm_votes,
            total_token_votes=total_token_votes,
            total_epoch_votes=total_epoch_votes,
            emission=emission,
            core_factory=core_factory,
            fee_distributor=fee_distributor,
            ply_address=ply_address,
            ve_address=ve_address,
        )

    @sp.entry_point
    def next_epoch(self):
        with sp.if_(self.data.epoch == 0):

            # Calculate timestamp rounded to nearest whole week, based on Unix epoch - 12 AM UTC, Thursday
            now_ = sp.as_nat(sp.now - sp.timestamp(0))
            ts_ = ((now_ + WEEK) // WEEK) * WEEK

            # Set genesis for emission
            self.data.emission.genesis = ts_

            self.data.epoch += 1
            self.data.epoch_end[self.data.epoch] = sp.timestamp(0).add_seconds(sp.to_int(ts_))
        with sp.else_():

            # Verify that previous epoch is over
            sp.verify(sp.now > self.data.epoch_end[self.data.epoch], Errors.PREVIOUS_EPOCH_YET_TO_END)

            now_ = sp.as_nat(sp.now - sp.timestamp(0))
            rounded_now = (now_ // WEEK) * WEEK

            # Fetch total supply of PLY
            ply_total_supply = sp.view(
                "get_total_supply",
                self.data.ply_address,
                sp.unit,
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            # Fetch PLY supply locked up in vote escrow
            ply_locked_supply = sp.view(
                "get_locked_supply",
                self.data.ve_address,
                sp.unit,
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            # Calculate decrease offset based on locked supply ratio
            emission_offset = (self.data.emission.base * ply_locked_supply) // ply_total_supply

            # Calculate real emission for the epoch that just ended
            real_emission = sp.as_nat(self.data.emission.base - emission_offset)
            self.data.emission.real = real_emission

            # Adjust base emission value based on inflation drop
            with sp.if_((rounded_now - self.data.emission.genesis) == (4 * WEEK)):
                self.data.emission.base = (self.data.emission.base * INITIAL_DROP) // (100 * DROP_GRANULARITY)
            with sp.if_(((rounded_now - self.data.emission.genesis) % YEAR) == 0):
                self.data.emission.base = (self.data.emission.base * YEARLY_DROP) // (100 * DROP_GRANULARITY)
                with sp.if_(self.data.emission.base < TRAIL_INFLATION):
                    self.data.emission.base = TRAIL_INFLATION

            # Update weekly epoch
            self.data.epoch += 1
            self.data.epoch_end[self.data.epoch] = self.data.epoch_end[sp.as_nat(self.data.epoch - 1)].add_seconds(WEEK)

    # NOTE: This is called only once during origination sequence
    @sp.entry_point
    def set_factory_and_fee_dist(self, params):
        sp.set_type(params, sp.TRecord(factory=sp.TAddress, fee_dist=sp.TAddress))

        with sp.if_(self.data.core_factory == Addresses.DUMMY):
            self.data.core_factory = params.factory
            self.data.fee_distributor = params.fee_dist

    # NOTE: This is tested in CoreFactory
    @sp.entry_point
    def add_amm(self, params):
        sp.set_type(params, Types.ADD_AMM_PARAMS)

        # Verify that the sender is the core factory
        sp.verify(sp.sender == self.data.core_factory, Errors.NOT_AUTHORISED)

        # Add to storage
        self.data.amm_to_gauge_bribe[params.amm] = sp.record(
            gauge=params.gauge,
            bribe=params.bribe,
        )

    # NOTE: This is tested in CoreFactory
    @sp.entry_point
    def remove_amm(self, amm):
        sp.set_type(amm, sp.TAddress)

        # Verify that the sender is the core factory
        sp.verify(sp.sender == self.data.core_factory, Errors.NOT_AUTHORISED)

        # Delete AMM from storage
        del self.data.amm_to_gauge_bribe[amm]

    @sp.entry_point
    def vote(self, params):
        sp.set_type(params, Types.VOTE_PARAMS)

        # Verify that current epoch is not yet over
        sp.verify(sp.now < self.data.epoch_end[self.data.epoch], Errors.EPOCH_ENDED)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        epoch_ = self.data.epoch

        # Get available voting power for the lock / token-id (rounded to previous whole week)
        max_token_voting_power = sp.view(
            "get_token_voting_power",
            self.data.ve_address,
            sp.record(token_id=params.token_id, ts=now_, time=Types.WHOLE_WEEK),
            sp.TNat,
        ).open_some(Errors.INVALID_VIEW)

        # Verify that the sender owns the specified token / lock
        is_owner = sp.view(
            "is_owner",
            self.data.ve_address,
            sp.record(address=sp.sender, token_id=params.token_id),
            sp.TBool,
        ).open_some(Errors.INVALID_VIEW)
        sp.verify(is_owner, Errors.SENDER_DOES_NOT_OWN_LOCK)

        # Calculate available voting power for token i.e max power - used up power
        used_power = self.data.total_token_votes.get(
            sp.record(token_id=params.token_id, epoch=self.data.epoch),
            sp.nat(0),
        )
        power_available = sp.local("power_used", sp.as_nat(max_token_voting_power - used_power))

        with sp.for_("vote_item", params.vote_items) as vote_item:

            # Verify that the amm being voted on exists in voter i.e whitelisted
            sp.verify(self.data.amm_to_gauge_bribe.contains(vote_item.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

            # Verify that vote is non-zero
            sp.verify(vote_item.votes != 0, Errors.ZERO_VOTE_NOT_ALLOWED)

            # Re-votes in the same epoch gets added up
            key_ = sp.record(token_id=params.token_id, epoch=epoch_, amm=vote_item.amm)
            with sp.if_(~self.data.token_amm_votes.contains(key_)):
                self.data.token_amm_votes[key_] = 0
            self.data.token_amm_votes[key_] += vote_item.votes

            # Update total epoch votes for amm
            key_ = sp.record(amm=vote_item.amm, epoch=epoch_)
            with sp.if_(~self.data.total_amm_votes.contains(key_)):
                self.data.total_amm_votes[key_] = 0
            self.data.total_amm_votes[key_] += vote_item.votes

            # Update total epoch votes for token
            key_ = sp.record(token_id=params.token_id, epoch=epoch_)
            with sp.if_(~self.data.total_token_votes.contains(key_)):
                self.data.total_token_votes[key_] = 0
            self.data.total_token_votes[key_] += vote_item.votes

            # Update total epoch votes as a whole
            with sp.if_(~self.data.total_epoch_votes.contains(epoch_)):
                self.data.total_epoch_votes[epoch_] = 0
            self.data.total_epoch_votes[epoch_] += vote_item.votes

            # Update power used & verify that available voting power of token has not been overshot
            power_available.value = sp.as_nat(
                power_available.value - vote_item.votes, Errors.NOT_ENOUGH_VOTING_POWER_AVAILABLE
            )

    @sp.entry_point
    def claim_bribe(self, params):
        sp.set_type(params, Types.CLAIM_BRIBE_PARAMS)

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Verify that the sender owns the specified token / lock
        is_owner = sp.view(
            "is_owner",
            self.data.ve_address,
            sp.record(address=sp.sender, token_id=params.token_id),
            sp.TBool,
        ).open_some(Errors.INVALID_VIEW)
        sp.verify(is_owner, Errors.SENDER_DOES_NOT_OWN_LOCK)

        # Calculate share weightage for the vePLY token
        token_votes_for_amm = self.data.token_amm_votes[
            sp.record(token_id=params.token_id, epoch=params.epoch, amm=params.amm)
        ]
        total_votes_for_amm = self.data.total_amm_votes[sp.record(epoch=params.epoch, amm=params.amm)]

        token_vote_share = (token_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_amm

        # call the 'claim' entrypoint in bribe contract
        param_type = sp.TRecord(
            token_id=sp.TNat,
            owner=sp.TAddress,
            epoch=sp.TNat,
            bribe_id=sp.TNat,
            weight_share=sp.TNat,
        ).layout(("token_id", ("owner", ("epoch", ("bribe_id", "weight_share")))))

        c = sp.contract(param_type, self.data.amm_to_gauge_bribe[params.amm].bribe, "claim").open_some()

        sp.transfer(
            sp.record(
                token_id=params.token_id,
                owner=sp.sender,
                epoch=params.epoch,
                bribe_id=params.bribe_id,
                weight_share=token_vote_share,
            ),
            sp.tez(0),
            c,
        )

    @sp.entry_point
    def claim_fee(self, params):
        sp.set_type(params, Types.CLAIM_FEE_PARAMS)

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Verify that the sender owns the specified token / lock
        is_owner = sp.view(
            "is_owner",
            self.data.ve_address,
            sp.record(address=sp.sender, token_id=params.token_id),
            sp.TBool,
        ).open_some(Errors.INVALID_VIEW)
        sp.verify(is_owner, Errors.SENDER_DOES_NOT_OWN_LOCK)

        # Calculate share weightage for the vePLY token
        token_votes_for_amm = self.data.token_amm_votes[
            sp.record(token_id=params.token_id, epoch=params.epoch, amm=params.amm)
        ]
        total_votes_for_amm = self.data.total_amm_votes[sp.record(epoch=params.epoch, amm=params.amm)]

        token_vote_share = (token_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_amm

        # call the 'claim' entrypoint in Fee Distributor to distribute the fee to the token holder
        param_type = sp.TRecord(
            token_id=sp.TNat,
            owner=sp.TAddress,
            amm=sp.TAddress,
            epoch=sp.TNat,
            weight_share=sp.TNat,
        ).layout(("token_id", ("owner", ("amm", ("epoch", "weight_share")))))

        c = sp.contract(param_type, self.data.fee_distributor, "claim").open_some()

        sp.transfer(
            sp.record(
                token_id=params.token_id,
                owner=sp.sender,
                amm=params.amm,
                epoch=params.epoch,
                weight_share=token_vote_share,
            ),
            sp.tez(0),
            c,
        )

    @sp.entry_point
    def pull_amm_fee(self, params):
        sp.set_type(params, sp.TRecord(epoch=sp.TNat, amm=sp.TAddress))

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # TODO: call the 'forward_fee' entrypoint of the amm, passing in fee_distributor & epoch

    @sp.entry_point
    def recharge_gauge(self, params):
        sp.set_type(params, sp.TRecord(epoch=sp.TNat, amm=sp.TAddress))

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Calculate the share weightage for the amm gauge
        total_votes_for_amm = self.data.total_amm_votes[sp.record(epoch=params.epoch, amm=params.amm)]
        total_votes_for_epoch = self.data.total_epoch_votes[params.epoch]
        amm_vote_share = (total_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_epoch

        # Calculate recharge amount based on share weightage
        recharge_amount = (self.data.emission.real * amm_vote_share) // VOTE_SHARE_MULTIPLIER

        # Mint PLY tokens for the concerned gauge contract
        c = sp.contract(
            sp.TRecord(address=sp.TAddress, value=sp.TNat),
            self.data.ply_address,
            "mint",
        ).open_some()
        sp.transfer(
            sp.record(address=self.data.amm_to_gauge_bribe[params.amm].gauge, value=recharge_amount),
            sp.tez(0),
            c,
        )

        # Call 'recharge' entrypoint in concerned gauge
        c_gauge = sp.contract(
            sp.TRecord(amount=sp.TNat, epoch=sp.TNat),
            self.data.amm_to_gauge_bribe[params.amm].gauge,
            "recharge",
        ).open_some()
        sp.transfer(
            sp.record(amount=recharge_amount, epoch=params.epoch),
            sp.tez(0),
            c_gauge,
        )

    @sp.onchain_view()
    def get_current_epoch(self):
        sp.result((self.data.epoch, self.data.epoch_end[self.data.epoch]))


if __name__ == "__main__":

    ####################
    # vote (valid test)
    ####################

    @sp.add_test(name="vote allows voting across multiple whitelisted AMMs")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with 3 whitelisted AMMs
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                    Addresses.AMM_2: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                    Addresses.AMM_3: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += voter

        # when ALICE votes for AMM_1 and AMM_2 using token-1
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list(
                    [sp.record(amm=Addresses.AMM_1, votes=20), sp.record(amm=Addresses.AMM_2, votes=30)]
                ),
            )
        ).run(sender=Addresses.ALICE, now=sp.timestamp(5))

        # Storage is updated correctly
        scenario.verify(voter.data.token_amm_votes[sp.record(token_id=1, amm=Addresses.AMM_1, epoch=1)] == 20)
        scenario.verify(voter.data.token_amm_votes[sp.record(token_id=1, amm=Addresses.AMM_2, epoch=1)] == 30)
        scenario.verify(voter.data.total_amm_votes[sp.record(amm=Addresses.AMM_1, epoch=1)] == 20)
        scenario.verify(voter.data.total_amm_votes[sp.record(amm=Addresses.AMM_2, epoch=1)] == 30)
        scenario.verify(voter.data.total_token_votes[sp.record(token_id=1, epoch=1)] == 50)

        # when BOB votes for AMM_2 and AMM_3 using token-2
        scenario += voter.vote(
            sp.record(
                token_id=2,
                vote_items=sp.list(
                    [sp.record(amm=Addresses.AMM_2, votes=30), sp.record(amm=Addresses.AMM_3, votes=40)]
                ),
            )
        ).run(sender=Addresses.BOB, now=sp.timestamp(6))

        # Storage is updated correctly
        scenario.verify(voter.data.token_amm_votes[sp.record(token_id=2, amm=Addresses.AMM_2, epoch=1)] == 30)
        scenario.verify(voter.data.token_amm_votes[sp.record(token_id=2, amm=Addresses.AMM_3, epoch=1)] == 40)
        scenario.verify(voter.data.total_amm_votes[sp.record(amm=Addresses.AMM_2, epoch=1)] == 60)
        scenario.verify(voter.data.total_amm_votes[sp.record(amm=Addresses.AMM_3, epoch=1)] == 40)
        scenario.verify(voter.data.total_token_votes[sp.record(token_id=2, epoch=1)] == 70)
        scenario.verify(voter.data.total_epoch_votes[1] == 120)

    @sp.add_test(name="vote allows voting multiple times for the same amm using the same token")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with an AMM
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += voter

        # when ALICE votes for AMM_1 twice
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_1, votes=20)]),
            )
        ).run(sender=Addresses.ALICE, now=sp.timestamp(5))
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_1, votes=30)]),
            )
        ).run(sender=Addresses.ALICE, now=sp.timestamp(6))

        # Storage is updated correctly
        scenario.verify(voter.data.token_amm_votes[sp.record(token_id=1, amm=Addresses.AMM_1, epoch=1)] == 50)
        scenario.verify(voter.data.total_amm_votes[sp.record(amm=Addresses.AMM_1, epoch=1)] == 50)
        scenario.verify(voter.data.total_token_votes[sp.record(token_id=1, epoch=1)] == 50)
        scenario.verify(voter.data.total_epoch_votes[1] == 50)

    ######################
    # vote (failure test)
    ######################

    @sp.add_test(name="vote fails if more than the available token voting power is used")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with an AMM
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                    Addresses.AMM_2: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += voter

        # ALICE votes for AMM_1
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_1, votes=50)]),
            )
        ).run(sender=Addresses.ALICE, now=sp.timestamp(5))

        # When ALICE votes for AMM_2 with more than the available votes, the transaction fails
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_2, votes=60)]),
            )
        ).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(6),
            valid=False,
            exception=Errors.NOT_ENOUGH_VOTING_POWER_AVAILABLE,
        )

    @sp.add_test(name="vote fails if zero vote is deposited for a certain amm")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with an AMM
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                    Addresses.AMM_2: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += voter

        # When ALICE puts zero vote for AMM_1, the txn fails
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_1, votes=0)]),
            )
        ).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(5),
            valid=False,
            exception=Errors.ZERO_VOTE_NOT_ALLOWED,
        )

    @sp.add_test(name="vote fails if epoch has already ended")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with an AMM
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                    Addresses.AMM_2: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += voter

        # When ALICE votes after the epoch has ended, txn fails
        scenario += voter.vote(
            sp.record(
                token_id=1,
                vote_items=sp.list([sp.record(amm=Addresses.AMM_1, votes=0)]),
            )
        ).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(11),
            valid=False,
            exception=Errors.EPOCH_ENDED,
        )

    ##########################
    # next_epoch (valid test)
    ##########################

    @sp.add_test(name="next_epoch correctly updates first epoch")
    def test():
        scenario = sp.test_scenario()

        voter = Voter()

        scenario += voter

        # When next_epoch is called for the first time
        scenario += voter.next_epoch().run(now=sp.timestamp(8 * DAY))

        # Storage is updated correctly
        scenario.verify(voter.data.epoch == 1)
        scenario.verify(voter.data.epoch_end[1] == sp.timestamp(2 * WEEK))
        scenario.verify(voter.data.emission.genesis == 2 * WEEK)

    @sp.add_test(name="next_epoch correctly updates epoch during first inflation drop")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(100 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(400 * DECIMALS))

        voter = Voter(
            epoch=5,
            epoch_end=sp.big_map(l={5: sp.timestamp(6 * WEEK)}),
            emission=sp.record(
                base=INITIAL_INFLATION,
                real=sp.nat(0),
                genesis=2 * WEEK,
            ),
            ve_address=ve.address,
            ply_address=ply.address,
        )

        scenario += ve
        scenario += ply
        scenario += voter

        # When next_epoch is called at the end of 4 weeks of inflation
        scenario += voter.next_epoch().run(now=sp.timestamp(6 * WEEK + 124))  # random offset for testing

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 6)
        scenario.verify(voter.data.epoch_end[6] == sp.timestamp(7 * WEEK))

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == 700_000 * DECIMALS)
        scenario.verify(voter.data.emission.real == 1_500_000 * DECIMALS)

        # When next epoch is called again at the end of 7 Weeks
        scenario += voter.next_epoch().run(now=sp.timestamp(7 * WEEK + 73))

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 7)
        scenario.verify(voter.data.epoch_end[7] == sp.timestamp(8 * WEEK))

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == 700_000 * DECIMALS)
        scenario.verify(voter.data.emission.real == 525_000 * DECIMALS)

    @sp.add_test(name="next_epoch correctly updates epoch during yearly inflation drop")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(100 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(400 * DECIMALS))

        voter = Voter(
            epoch=53,
            epoch_end=sp.big_map(l={53: sp.timestamp(54 * WEEK)}),
            emission=sp.record(
                base=700_000 * DECIMALS,
                real=sp.nat(0),
                genesis=2 * WEEK,
            ),
            ve_address=ve.address,
            ply_address=ply.address,
        )

        scenario += ve
        scenario += ply
        scenario += voter

        # When next epoch is called again at the end of 1st complete year
        scenario += voter.next_epoch().run(now=sp.timestamp(54 * WEEK + 24))

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 54)
        scenario.verify(voter.data.epoch_end[54] == sp.timestamp(55 * WEEK))

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == 385_000 * DECIMALS)
        scenario.verify(voter.data.emission.real == 525_000 * DECIMALS)

    @sp.add_test(name="next_epoch correctly sets trail inflation")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(100 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(400 * DECIMALS))

        voter = Voter(
            epoch=53,
            epoch_end=sp.big_map(l={53: sp.timestamp(54 * WEEK)}),
            emission=sp.record(
                base=15_000 * DECIMALS,
                real=sp.nat(0),
                genesis=2 * WEEK,
            ),
            ve_address=ve.address,
            ply_address=ply.address,
        )

        scenario += ve
        scenario += ply
        scenario += voter

        # When next epoch is called again at the end of 1st complete year
        scenario += voter.next_epoch().run(now=sp.timestamp(54 * WEEK + 24))

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 54)
        scenario.verify(voter.data.epoch_end[54] == sp.timestamp(55 * WEEK))

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == 10_000 * DECIMALS)
        scenario.verify(voter.data.emission.real == 11_250 * DECIMALS)

    ############################
    # next_epoch (failure test)
    ############################

    @sp.add_test(name="next_epoch fails if called before current epoch is over")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(
            epoch_end=sp.big_map(
                l={
                    1: sp.timestamp(5),
                }
            ),
            epoch=sp.nat(1),
        )

        scenario += voter

        # When next_epoch is called before the current epoch is over, the txn fails
        scenario += voter.next_epoch().run(
            now=sp.timestamp(4),
            valid=False,
            exception=Errors.PREVIOUS_EPOCH_YET_TO_END,
        )

    ###########################
    # claim_bribe (valid test)
    ###########################

    # NOTE: This will also be accepted for weight share calculation in claim_fee

    @sp.add_test(name="claim_bribe correctly calculates the vote weight share")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow for ownership checks
        ve = VE()

        # Initialize a dummy bribe contract and set it in the voter for AMM_1
        bribe = GaugeBribe()

        # Initialize with some votes for epoch 1
        voter = Voter(
            epoch=2,
            epoch_end=sp.big_map(l={2: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=bribe.address),
                }
            ),
            token_amm_votes=sp.big_map(
                l={
                    sp.record(token_id=1, epoch=1, amm=Addresses.AMM_1): 150,
                }
            ),
            total_amm_votes=sp.big_map(
                l={
                    sp.record(epoch=1, amm=Addresses.AMM_1): 250,
                }
            ),
            ve_address=ve.address,
        )

        scenario += ve
        scenario += bribe
        scenario += voter

        # When ALICE calls claim_bribe for epoch 1 votes
        scenario += voter.claim_bribe(
            sp.record(
                token_id=1,
                epoch=1,
                amm=Addresses.AMM_1,
                bribe_id=1,
            )
        ).run(sender=Addresses.ALICE)

        # Vote weight is calculated correctly and bribe contract is called with correct values
        scenario.verify(
            bribe.data.claim_val.open_some()
            == sp.record(
                token_id=1,
                epoch=1,
                owner=Addresses.ALICE,
                bribe_id=1,
                weight_share=int(0.6 * VOTE_SHARE_MULTIPLIER),
            )
        )

    #############################
    # claim_bribe (failure test)
    #############################

    # NOTE: This failure test is also accepted for claim_fee, recharge_gauge and pull_amm_fee

    @sp.add_test(name="claim_bribe fails if epoch is in the future or amm is not whitelisted")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
        )

        scenario += voter

        # When ALICE tries to claim bribe for future epoch 2, txn fails
        scenario += voter.claim_bribe(token_id=1, epoch=2, amm=Addresses.AMM_1, bribe_id=1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.INVALID_EPOCH,
        )

        # When ALICE tries to claim bribe for non-whitelisted AMM, txn fails
        scenario += voter.claim_bribe(token_id=1, epoch=0, amm=Addresses.AMM_2, bribe_id=1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.AMM_INVALID_OR_NOT_WHITELISTED,
        )

    ##############################
    # recharge_gauge (valid test)
    ##############################

    @sp.add_test(name="recharge_gauge correctly calculates the amm vote share and recharges the gauge")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12(Addresses.ADMIN)

        # Initialize a dummy gauge contract and set it in the voter for AMM_1
        gauge = GaugeBribe()

        # Initialize with some votes for epoch 1
        voter = Voter(
            epoch=2,
            epoch_end=sp.big_map(l={2: sp.timestamp(10)}),
            emission=sp.record(
                base=INITIAL_INFLATION,
                real=INITIAL_INFLATION,
                genesis=2 * WEEK,
            ),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=gauge.address, bribe=Addresses.CONTRACT),
                }
            ),
            total_amm_votes=sp.big_map(
                l={
                    sp.record(epoch=1, amm=Addresses.AMM_1): 250,
                }
            ),
            total_epoch_votes=sp.big_map(l={1: 500}),
            ply_address=ply_token.address,
        )

        scenario += gauge
        scenario += voter
        scenario += ply_token

        # Make voter contract a mint admin
        scenario += ply_token.addMintAdmin(voter.address).run(sender=Addresses.ADMIN)

        # When gauge is recharged for epoch 1
        scenario += voter.recharge_gauge(
            sp.record(
                epoch=1,
                amm=Addresses.AMM_1,
            )
        ).run(sender=Addresses.ALICE)

        # AMM's vote share is calculated correctly and gauge contract is called with correct amount value
        scenario.verify(
            gauge.data.recharge_val.open_some() == sp.record(amount=1_000_000 * DECIMALS, epoch=1)
        )  # 0.5 of the real emission

        # PLY tokens are minted correctly for gauge
        scenario.verify(ply_token.data.balances[gauge.address].balance == 1_000_000 * DECIMALS)

    sp.add_compilation_target("voter", Voter())
