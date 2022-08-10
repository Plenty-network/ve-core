import smartpy as sp

Errors = sp.io.import_script_from_url("file:utils/errors.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
VE = sp.io.import_script_from_url("file:helpers/dummy/ve.py").VE
Constants = sp.io.import_script_from_url("file:utils/constants.py")
Ply = sp.io.import_script_from_url("file:helpers/dummy/ply.py").Ply
Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
FeeDist = sp.io.import_script_from_url("file:helpers/dummy/fee_dist.py").FeeDist
GaugeBribe = sp.io.import_script_from_url("file:helpers/dummy/gauge_bribe.py").GaugeBribe


############
# Constants
############


DAY = Constants.DAY
WEEK = Constants.WEEK
YEAR = Constants.YEAR
MAX_TIME = Constants.MAX_TIME
DECIMALS = Constants.DECIMALS
PRECISION = Constants.PRECISION
YEARLY_DROP = Constants.YEARLY_DROP
INITIAL_DROP = Constants.INITIAL_DROP
TRAIL_EMISSION = Constants.TRAIL_EMISSION
EMISSION_FACTOR = Constants.EMISSION_FACTOR
INITIAL_EMISSION = Constants.INITIAL_EMISSION
DROP_GRANULARITY = Constants.DROP_GRANULARITY
VOTE_SHARE_MULTIPLIER = Constants.VOTE_SHARE_MULTIPLIER


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
        amm=sp.TAddress,
        epoch=sp.TNat,
        bribe_id=sp.TNat,
    ).layout(("token_id", ("amm", ("epoch", "bribe_id"))))

    CLAIM_FEE_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        amm=sp.TAddress,
        epochs=sp.TList(sp.TNat),
    ).layout(("token_id", ("amm", "epochs")))

    # Enumeration for voting power readers
    CURRENT = sp.nat(0)
    WHOLE_WEEK = sp.nat(1)


###########
# Contract
###########


class Voter(sp.Contract):
    def __init__(
        self,
        core_factory=Addresses.DUMMY,
        fee_distributor=Addresses.DUMMY,
        ply_address=Addresses.TOKEN,
        ve_address=Addresses.CONTRACT,
        epoch=sp.nat(0),
        epoch_end=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TTimestamp,
        ),
        emission=sp.record(
            base=INITIAL_EMISSION,
            real=sp.nat(0),
            genesis=sp.nat(0),
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
    ):
        self.init(
            core_factory=core_factory,
            fee_distributor=fee_distributor,
            ply_address=ply_address,
            ve_address=ve_address,
            epoch=epoch,
            epoch_end=epoch_end,
            emission=emission,
            amm_to_gauge_bribe=amm_to_gauge_bribe,
            total_amm_votes=total_amm_votes,
            token_amm_votes=token_amm_votes,
            total_token_votes=total_token_votes,
            total_epoch_votes=total_epoch_votes,
        )

        self.init_type(
            sp.TRecord(
                core_factory=sp.TAddress,
                fee_distributor=sp.TAddress,
                ply_address=sp.TAddress,
                ve_address=sp.TAddress,
                epoch=sp.TNat,
                epoch_end=sp.TBigMap(sp.TNat, sp.TTimestamp),
                emission=sp.TRecord(base=sp.TNat, real=sp.TNat, genesis=sp.TNat),
                amm_to_gauge_bribe=sp.TBigMap(sp.TAddress, Types.AMM_TO_GAUGE_BRIBE),
                total_amm_votes=sp.TBigMap(Types.TOTAL_AMM_VOTES_KEY, sp.TNat),
                token_amm_votes=sp.TBigMap(Types.TOKEN_AMM_VOTES_KEY, sp.TNat),
                total_token_votes=sp.TBigMap(Types.TOTAL_TOKEN_VOTES_KEY, sp.TNat),
                total_epoch_votes=sp.TBigMap(sp.TNat, sp.TNat),
            )
        )

    @sp.entry_point
    def next_epoch(self):
        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        with sp.if_(self.data.epoch == 0):

            # Calculate timestamp rounded to nearest whole week, based on Unix epoch - 12 AM UTC, Thursday
            now_ = sp.as_nat(sp.now - sp.timestamp(0))
            ts_ = sp.compute(((now_ + WEEK) // WEEK) * WEEK)

            # Set genesis for emission
            self.data.emission.genesis = ts_

            self.data.epoch += 1
            self.data.epoch_end[self.data.epoch] = sp.timestamp(0).add_seconds(sp.to_int(ts_))
        with sp.else_():

            # Verify that previous epoch is over
            sp.verify(sp.now > self.data.epoch_end[self.data.epoch], Errors.PREVIOUS_EPOCH_YET_TO_END)

            now_ = sp.as_nat(sp.now - sp.timestamp(0))
            rounded_now = sp.compute((now_ // WEEK) * WEEK)

            # Fetch total supply of PLY
            ply_total_supply = sp.compute(
                sp.view(
                    "get_total_supply",
                    self.data.ply_address,
                    sp.unit,
                    sp.TNat,
                ).open_some(Errors.INVALID_VIEW)
            )

            # Fetch PLY supply locked up in vote escrow
            ply_locked_supply = sp.compute(
                sp.view(
                    "get_locked_supply",
                    self.data.ve_address,
                    sp.unit,
                    sp.TNat,
                ).open_some(Errors.INVALID_VIEW)
            )

            # Store as local variable to keep on stack
            current_emission = sp.compute(self.data.emission)

            # Calculate decrease offset based on locked supply ratio
            emission_offset = ((current_emission.base * ply_locked_supply) // ply_total_supply) // EMISSION_FACTOR

            # Calculate real emission for the epoch that just ended
            real_emission = sp.as_nat(current_emission.base - emission_offset)
            self.data.emission.real = real_emission

            # Calculate growth due to the emission
            growth = (real_emission * PRECISION) // ply_total_supply
            lockers_inflation = sp.compute((growth * ply_locked_supply) // PRECISION)

            # Mint required number of PLY tokens (lockers inflation) for VoteEscrow
            c = sp.contract(
                sp.TRecord(address=sp.TAddress, value=sp.TNat),
                self.data.ply_address,
                "mint",
            ).open_some()
            sp.transfer(
                sp.record(address=self.data.ve_address, value=lockers_inflation),
                sp.tez(0),
                c,
            )

            # Inflate lockers proportionally
            c = sp.contract(
                sp.TRecord(epoch=sp.TNat, value=sp.TNat).layout(("epoch", "value")),
                self.data.ve_address,
                "add_inflation",
            ).open_some()
            sp.transfer(
                sp.record(epoch=self.data.epoch, value=lockers_inflation),
                sp.tez(0),
                c,
            )

            # Adjust base emission value based on emission drop
            with sp.if_((rounded_now - current_emission.genesis) == (4 * WEEK)):
                self.data.emission.base = (current_emission.base * INITIAL_DROP) // (100 * DROP_GRANULARITY)
            with sp.if_(((rounded_now - current_emission.genesis) % YEAR) == 0):
                self.data.emission.base = (current_emission.base * YEARLY_DROP) // (100 * DROP_GRANULARITY)
                with sp.if_(self.data.emission.base < TRAIL_EMISSION):
                    self.data.emission.base = TRAIL_EMISSION

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

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Verify that current epoch is not yet over
        sp.verify(sp.now <= self.data.epoch_end[self.data.epoch], Errors.EPOCH_ENDED)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Store as local variable to keep on stack
        epoch_ = sp.compute(self.data.epoch)

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
            votes_ = self.data.token_amm_votes.get(key_, 0)
            self.data.token_amm_votes[key_] = votes_ + vote_item.votes

            # Update total epoch votes for amm
            key_ = sp.record(amm=vote_item.amm, epoch=epoch_)
            votes_ = self.data.total_amm_votes.get(key_, 0)
            self.data.total_amm_votes[key_] = votes_ + vote_item.votes

            # Update total epoch votes for token
            key_ = sp.record(token_id=params.token_id, epoch=epoch_)
            votes_ = self.data.total_token_votes.get(key_, 0)
            self.data.total_token_votes[key_] = votes_ + vote_item.votes

            # Update total epoch votes as a whole
            votes_ = self.data.total_epoch_votes.get(epoch_, 0)
            self.data.total_epoch_votes[epoch_] = votes_ + vote_item.votes

            # Update power used & verify that available voting power of token has not been overshot
            power_available.value = sp.as_nat(
                power_available.value - vote_item.votes, Errors.NOT_ENOUGH_VOTING_POWER_AVAILABLE
            )

    @sp.entry_point
    def claim_bribe(self, params):
        sp.set_type(params, Types.CLAIM_BRIBE_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

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

        # Calculate vote share for the vePLY token
        token_votes_for_amm = self.data.token_amm_votes.get(
            sp.record(token_id=params.token_id, epoch=params.epoch, amm=params.amm),
            0,
        )

        total_votes_for_amm = sp.compute(
            self.data.total_amm_votes.get(
                sp.record(epoch=params.epoch, amm=params.amm),
                0,
            )
        )

        with sp.if_(total_votes_for_amm > 0):
            token_vote_share = (token_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_amm

            # call the 'claim' entrypoint in bribe contract
            param_type = sp.TRecord(
                token_id=sp.TNat,
                owner=sp.TAddress,
                epoch=sp.TNat,
                bribe_id=sp.TNat,
                vote_share=sp.TNat,
            ).layout(("token_id", ("owner", ("epoch", ("bribe_id", "vote_share")))))

            c = sp.contract(param_type, self.data.amm_to_gauge_bribe[params.amm].bribe, "claim").open_some()

            sp.transfer(
                sp.record(
                    token_id=params.token_id,
                    owner=sp.sender,
                    epoch=params.epoch,
                    bribe_id=params.bribe_id,
                    vote_share=token_vote_share,
                ),
                sp.tez(0),
                c,
            )
        with sp.else_():
            # Retutn the bribe to the provider is no votes received by the AMM
            c = sp.contract(
                sp.TRecord(epoch=sp.TNat, bribe_id=sp.TNat),
                self.data.amm_to_gauge_bribe[params.amm].bribe,
                "return_bribe",
            ).open_some()
            sp.transfer(
                sp.record(
                    epoch=params.epoch,
                    bribe_id=params.bribe_id,
                ),
                sp.tez(0),
                c,
            )

    @sp.entry_point
    def claim_fee(self, params):
        sp.set_type(params, Types.CLAIM_FEE_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Verify that the sender owns the specified token / lock
        is_owner = sp.view(
            "is_owner",
            self.data.ve_address,
            sp.record(address=sp.sender, token_id=params.token_id),
            sp.TBool,
        ).open_some(Errors.INVALID_VIEW)
        sp.verify(is_owner, Errors.SENDER_DOES_NOT_OWN_LOCK)

        # Local variable to store through the vote share across the epochs
        epoch_vote_shares = sp.local("epoch_vote_shares", sp.list(l=[], t=sp.TRecord(epoch=sp.TNat, share=sp.TNat)))

        # Iterate through requested epochs
        with sp.for_("epochs", params.epochs) as epoch:
            sp.verify(self.data.epoch > epoch, Errors.INVALID_EPOCH)

            # Calculate vote share for the vePLY token
            token_votes_for_amm = self.data.token_amm_votes[
                sp.record(token_id=params.token_id, epoch=epoch, amm=params.amm)
            ]
            total_votes_for_amm = self.data.total_amm_votes[sp.record(epoch=epoch, amm=params.amm)]

            token_vote_share = (token_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_amm

            epoch_vote_shares.value.push(sp.record(epoch=epoch, share=token_vote_share))

        # call the 'claim' entrypoint in Fee Distributor to distribute the fee to the token holder
        param_type = sp.TRecord(
            token_id=sp.TNat,
            owner=sp.TAddress,
            amm=sp.TAddress,
            epoch_vote_shares=sp.TList(sp.TRecord(epoch=sp.TNat, share=sp.TNat)),
        ).layout(("token_id", ("owner", ("amm", "epoch_vote_shares"))))

        c = sp.contract(param_type, self.data.fee_distributor, "claim").open_some()

        sp.transfer(
            sp.record(
                token_id=params.token_id,
                owner=sp.sender,
                amm=params.amm,
                epoch_vote_shares=epoch_vote_shares.value,
            ),
            sp.tez(0),
            c,
        )

    @sp.entry_point
    def pull_amm_fee(self, params):
        sp.set_type(params, sp.TRecord(amm=sp.TAddress, epoch=sp.TNat).layout(("amm", "epoch")))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Call the 'forwardFee' entrypoint of the amm, passing in fee_distributor & epoch
        c = sp.contract(
            sp.TRecord(feeDistributor=sp.TAddress, epoch=sp.TNat),
            params.amm,
            "forwardFee",
        ).open_some()
        sp.transfer(
            sp.record(feeDistributor=self.data.fee_distributor, epoch=params.epoch),
            sp.tez(0),
            c,
        )

    @sp.entry_point
    def recharge_gauge(self, params):
        sp.set_type(params, sp.TRecord(amm=sp.TAddress, epoch=sp.TNat).layout(("amm", "epoch")))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(self.data.epoch > params.epoch, Errors.INVALID_EPOCH)
        sp.verify(self.data.amm_to_gauge_bribe.contains(params.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

        # Calculate the vote share for the amm gauge
        total_votes_for_amm = self.data.total_amm_votes[sp.record(epoch=params.epoch, amm=params.amm)]
        total_votes_for_epoch = self.data.total_epoch_votes[params.epoch]
        amm_vote_share = (total_votes_for_amm * VOTE_SHARE_MULTIPLIER) // total_votes_for_epoch

        # Calculate recharge amount based on share
        recharge_amount = sp.compute((self.data.emission.real * amm_vote_share) // VOTE_SHARE_MULTIPLIER)

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

    @sp.onchain_view()
    def get_epoch_end(self, param):
        sp.set_type(param, sp.TNat)
        sp.result(sp.as_nat(self.data.epoch_end[param] - sp.timestamp(0)))

    @sp.onchain_view()
    def get_token_amm_votes(self, params):
        sp.set_type(params, Types.TOKEN_AMM_VOTES_KEY)
        sp.result(self.data.token_amm_votes.get(params, 0))

    @sp.onchain_view()
    def get_total_amm_votes(self, params):
        sp.set_type(params, Types.TOTAL_AMM_VOTES_KEY)
        sp.result(self.data.total_amm_votes.get(params, 0))

    @sp.onchain_view()
    def get_total_token_votes(self, params):
        sp.set_type(params, Types.TOTAL_TOKEN_VOTES_KEY)
        sp.result(self.data.total_token_votes.get(params, 0))

    @sp.onchain_view()
    def get_total_epoch_votes(self, param):
        sp.set_type(param, sp.TNat)
        sp.result(self.data.total_epoch_votes.get(param, 0))


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

    @sp.add_test(name="next_epoch correctly updates epoch during first emission drop")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(1_000_000 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(4_000_000 * DECIMALS))

        voter = Voter(
            epoch=5,
            epoch_end=sp.big_map(l={5: sp.timestamp(6 * WEEK)}),
            emission=sp.record(
                base=INITIAL_EMISSION,
                real=sp.nat(0),
                genesis=2 * WEEK,
            ),
            ve_address=ve.address,
            ply_address=ply.address,
        )

        scenario += ve
        scenario += ply
        scenario += voter

        # When next_epoch is called at the end of 4 weeks of emission
        scenario += voter.next_epoch().run(now=sp.timestamp(6 * WEEK + 124))  # random offset for testing

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 6)
        scenario.verify(voter.data.epoch_end[6] == sp.timestamp(7 * WEEK))

        # Predicted values
        emission_offset = ((INITIAL_EMISSION * 1_000_000 * DECIMALS) // (4_000_000 * DECIMALS)) // EMISSION_FACTOR
        real_emission = INITIAL_EMISSION - emission_offset
        base_emission = (INITIAL_EMISSION * INITIAL_DROP) // (100 * DROP_GRANULARITY)

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == base_emission)
        scenario.verify(voter.data.emission.real == real_emission)

        # Predicted locker inflation
        growth = (real_emission * PRECISION) // (4_000_000 * DECIMALS)
        locker_inflation = (1_000_000 * DECIMALS * growth) // PRECISION

        # Correct inflation is record
        scenario.verify(ve.data.inflation == locker_inflation)

        # When next epoch is called again at the end of 7 Weeks
        scenario += voter.next_epoch().run(now=sp.timestamp(7 * WEEK + 73))

        # Epoch is updated correctly
        scenario.verify(voter.data.epoch == 7)
        scenario.verify(voter.data.epoch_end[7] == sp.timestamp(8 * WEEK))

        # Predicted values
        emission_offset = ((base_emission * 1_000_000 * DECIMALS) // (4_000_000 * DECIMALS)) // EMISSION_FACTOR
        real_emission = base_emission - emission_offset

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == base_emission)
        scenario.verify(voter.data.emission.real == real_emission)

        # Predicted locker inflation
        growth = (real_emission * PRECISION) // (4_000_000 * DECIMALS)
        locker_inflation = (1_000_000 * DECIMALS * growth) // PRECISION

        # Correct inflation is record
        scenario.verify(ve.data.inflation == locker_inflation)

    @sp.add_test(name="next_epoch correctly updates epoch during yearly emission drop")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(1_000_000 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(4_000_000 * DECIMALS))

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

        # Predicted values
        emission_offset = ((700_000 * DECIMALS * 1_000_000 * DECIMALS) // (4_000_000 * DECIMALS)) // EMISSION_FACTOR
        real_emission = (700_000 * DECIMALS) - emission_offset
        base_emission = (700_000 * DECIMALS * YEARLY_DROP) // (100 * DROP_GRANULARITY)

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == base_emission)
        scenario.verify(voter.data.emission.real == real_emission)

        # Predicted locker inflation
        growth = (real_emission * PRECISION) // (4_000_000 * DECIMALS)
        locker_inflation = (1_000_000 * DECIMALS * growth) // PRECISION

        # Correct inflation is record
        scenario.verify(ve.data.inflation == locker_inflation)

    @sp.add_test(name="next_epoch correctly sets trail emission")
    def test():
        scenario = sp.test_scenario()

        # Initialize vote escrow with locked supply of 100 tokens
        ve = VE(locked_supply=sp.nat(1_000_000 * DECIMALS))

        # Initialize Ply token with total supply 400
        ply = Ply(total_supply=sp.nat(4_000_000 * DECIMALS))

        base_emission = TRAIL_EMISSION + 5_000 * DECIMALS

        voter = Voter(
            epoch=53,
            epoch_end=sp.big_map(l={53: sp.timestamp(54 * WEEK)}),
            emission=sp.record(
                base=base_emission,
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

        emission_offset = ((base_emission * 1_000_000 * DECIMALS) // (4_000_000 * DECIMALS)) // EMISSION_FACTOR
        real_emission = (base_emission) - emission_offset
        base_emission = (base_emission * YEARLY_DROP) // (100 * DROP_GRANULARITY)

        # Emission values are updated correctly
        scenario.verify(voter.data.emission.base == TRAIL_EMISSION)
        scenario.verify(voter.data.emission.real == real_emission)

        # Predicted locker inflation
        growth = (real_emission * PRECISION) // (4_000_000 * DECIMALS)
        locker_inflation = (1_000_000 * DECIMALS * growth) // PRECISION

        # Correct inflation is record
        scenario.verify(ve.data.inflation == locker_inflation)

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

    ##########################
    # claim_fee (valid test)
    ##########################

    @sp.add_test(name="claim_fee correctly calculates the vote share for one epoch")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow for ownership checks
        ve = VE()

        # Initialize a dummy fee distributor contract
        fee_dist = FeeDist()

        # Initialize with some votes for epoch 1
        voter = Voter(
            epoch=2,
            epoch_end=sp.big_map(l={2: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
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
            fee_distributor=fee_dist.address,
            ve_address=ve.address,
        )

        scenario += ve
        scenario += fee_dist
        scenario += voter

        # When ALICE calls claim_fee for epoch 1 votes
        scenario += voter.claim_fee(
            sp.record(
                token_id=1,
                epochs=[1],
                amm=Addresses.AMM_1,
            )
        ).run(sender=Addresses.ALICE)

        # Vote share is calculated correctly and FeeDistributor contract is called with correct values
        scenario.verify_equal(
            fee_dist.data.claim_val.open_some(),
            sp.record(
                token_id=1,
                amm=Addresses.AMM_1,
                owner=Addresses.ALICE,
                epoch_vote_shares=[sp.record(epoch=1, share=int(0.6 * VOTE_SHARE_MULTIPLIER))],
            ),
        )

    @sp.add_test(name="claim_fee correctly calculates the vote share for multiple epochs")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow for ownership checks
        ve = VE()

        # Initialize a dummy fee distributor contract
        fee_dist = FeeDist()

        # Initialize with some votes for epoch 1
        voter = Voter(
            epoch=4,
            epoch_end=sp.big_map(l={4: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
            token_amm_votes=sp.big_map(
                l={
                    sp.record(token_id=1, epoch=1, amm=Addresses.AMM_1): 150,
                    sp.record(token_id=1, epoch=2, amm=Addresses.AMM_1): 250,
                    sp.record(token_id=1, epoch=3, amm=Addresses.AMM_1): 350,
                }
            ),
            total_amm_votes=sp.big_map(
                l={
                    sp.record(epoch=1, amm=Addresses.AMM_1): 250,
                    sp.record(epoch=2, amm=Addresses.AMM_1): 500,
                    sp.record(epoch=3, amm=Addresses.AMM_1): 700,
                }
            ),
            fee_distributor=fee_dist.address,
            ve_address=ve.address,
        )

        scenario += ve
        scenario += fee_dist
        scenario += voter

        # When ALICE calls claim_fee for votes of epochs 1, 2, 3
        scenario += voter.claim_fee(
            sp.record(
                token_id=1,
                epochs=[1, 2, 3],
                amm=Addresses.AMM_1,
            )
        ).run(sender=Addresses.ALICE)

        # Vote share is calculated correctly and FeeDistributor contract is called with correct values
        scenario.verify_equal(
            fee_dist.data.claim_val.open_some(),
            sp.record(
                token_id=1,
                amm=Addresses.AMM_1,
                owner=Addresses.ALICE,
                epoch_vote_shares=[
                    sp.record(epoch=3, share=int(0.5 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=2, share=int(0.5 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=1, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                ],
            ),
        )

    ############################
    # claim_fee (failure test)
    ############################

    @sp.add_test(name="claim_fee fails if epoch is in the future or amm is not whitelisted")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow for ownership checks
        ve = VE()

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

        # When ALICE tries to call claim_fee for future epoch 2, txn fails
        scenario += voter.claim_fee(sp.record(token_id=1, epochs=[1, 2], amm=Addresses.AMM_1)).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.INVALID_EPOCH,
        )

        # When ALICE tries to call claim_fee for non-whitelisted AMM, txn fails
        scenario += voter.claim_fee(sp.record(token_id=1, epochs=[1], amm=Addresses.AMM_2)).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.AMM_INVALID_OR_NOT_WHITELISTED,
        )

    ###########################
    # claim_bribe (valid test)
    ###########################

    @sp.add_test(name="claim_bribe correctly calculates the vote share")
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

        # Vote share is calculated correctly and bribe contract is called with correct values
        scenario.verify(
            bribe.data.claim_val.open_some()
            == sp.record(
                token_id=1,
                epoch=1,
                owner=Addresses.ALICE,
                bribe_id=1,
                vote_share=int(0.6 * VOTE_SHARE_MULTIPLIER),
            )
        )

    @sp.add_test(name="claim_bribe calls return_bribe when total votes for the amm is zero")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow for ownership checks
        ve = VE()

        # Initialize a dummy bribe contract and set it in the voter for AMM_1
        bribe = GaugeBribe()

        # Initialize with no votes for epoch 1
        voter = Voter(
            epoch=2,
            epoch_end=sp.big_map(l={2: sp.timestamp(10)}),
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM_1: sp.record(gauge=Addresses.CONTRACT, bribe=bribe.address),
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

        # return_bribe is executed in the bribe contract
        scenario.verify(bribe.data.return_val.open_some() == sp.record(epoch=1, bribe_id=1))

    #############################
    # claim_bribe (failure test)
    #############################

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
                base=INITIAL_EMISSION,
                real=INITIAL_EMISSION,
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

    ################################
    # recharge_gauge (failure test)
    ################################

    @sp.add_test(name="recharge_gauge fails if epoch is in the future or amm is not whitelisted")
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

        # When ALICE tries to call recharge_gauge for future epoch 2, txn fails
        scenario += voter.recharge_gauge(epoch=2, amm=Addresses.AMM_1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.INVALID_EPOCH,
        )

        # When ALICE tries to call recharge_gauge for non-whitelisted AMM, txn fails
        scenario += voter.recharge_gauge(epoch=0, amm=Addresses.AMM_2).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.AMM_INVALID_OR_NOT_WHITELISTED,
        )

    ##############################
    # pull_amm_fee (failure test)
    ##############################

    @sp.add_test(name="pull_amm_fee fails if epoch is in the future or amm is not whitelisted")
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

        # When ALICE tries to call pull_amm_fee for future epoch 2, txn fails
        scenario += voter.pull_amm_fee(epoch=2, amm=Addresses.AMM_1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.INVALID_EPOCH,
        )

        # When ALICE tries to call pull_amm_fee for non-whitelisted AMM, txn fails
        scenario += voter.pull_amm_fee(epoch=0, amm=Addresses.AMM_2).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.AMM_INVALID_OR_NOT_WHITELISTED,
        )

    ####################
    # onchain_view test
    ####################

    @sp.add_test(name="onchain views work correctly")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(
            epoch=sp.nat(2),
            epoch_end=sp.big_map(
                l={
                    2: sp.timestamp(5),
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
            total_token_votes=sp.big_map(l={sp.record(epoch=1, token_id=1): 300}),
            total_epoch_votes=sp.big_map(
                l={
                    1: 500,
                }
            ),
        )

        scenario += voter

        # All views return correct values
        scenario.verify(voter.get_current_epoch() == (2, sp.timestamp(5)))
        scenario.verify(voter.get_token_amm_votes(sp.record(token_id=1, epoch=1, amm=Addresses.AMM_1)) == 150)
        scenario.verify(voter.get_total_amm_votes(sp.record(epoch=1, amm=Addresses.AMM_1)) == 250)
        scenario.verify(voter.get_total_token_votes(sp.record(epoch=1, token_id=1)) == 300)
        scenario.verify(voter.get_total_epoch_votes(1) == 500)

    sp.add_compilation_target("voter", Voter())
