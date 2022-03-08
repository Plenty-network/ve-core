import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
VE = sp.io.import_script_from_url("file:helpers/dummy/ve.py").VE
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12

############
# Constants
############

DAY = 86400
WEEK = 7 * DAY
YEAR = 52 * WEEK
MAX_TIME = 4 * YEAR

########
# Types
########


class Types:
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

    DISTRIBUTOR = sp.TRecord(
        gauge=sp.TAddress,
        bribe=sp.TAddress,
    ).layout(("gauge", "bribe"))

    VOTE_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        vote_items=sp.TList(
            sp.TRecord(
                amm=sp.TAddress,
                votes=sp.TNat,
            ).layout(("amm", "votes"))
        ),
    ).layout(("token_id", "vote_items"))


#########
# Errors
#########


class Errors:
    EPOCH_ENDED = "EPOCH_ENDED"
    PREVIOUS_EPOCH_YET_TO_END = "PREVIOUS_EPOCH_YET_TO_END"
    AMM_INVALID_OR_NOT_WHITELISTED = "AMM_INVALID_OR_NOT_WHITELISTED"
    SENDER_DOES_NOT_OWN_LOCK = "SENDER_DOES_NOT_OWN_LOCK"
    ZERO_VOTE_NOT_ALLOWED = "ZERO_VOTE_NOT_ALLOWED"
    NOT_ENOUGH_VOTING_POWER_AVAILABLE = "NOT_ENOUGH_VOTING_POWER_AVAILABLE"

    # Generic
    INVALID_VIEW = "INVALID_VIEW"


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
        distributors=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=Types.DISTRIBUTOR,
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
        ve_address=Addresses.CONTRACT,
    ):
        self.init(
            epoch=epoch,
            epoch_end=epoch_end,
            distributors=distributors,
            total_amm_votes=total_amm_votes,
            token_amm_votes=token_amm_votes,
            total_token_votes=total_token_votes,
            ve_address=ve_address,
        )

    @sp.entry_point
    def next_epoch(self):
        with sp.if_(self.data.epoch == 0):

            # Calculate timestamp rounded to nearest whole week, based on Unix epoch - 12 AM UTC, Thursday
            now_ = sp.as_nat(sp.now - sp.timestamp(0))
            ts_ = ((now_ + WEEK) // WEEK) * WEEK

            self.data.epoch += 1
            self.data.epoch_end[self.data.epoch] = sp.timestamp(0).add_seconds(sp.to_int(ts_))
        with sp.else_():

            # Verify that previous epoch is over
            sp.verify(sp.now > self.data.epoch_end[self.data.epoch], Errors.PREVIOUS_EPOCH_YET_TO_END)

            self.data.epoch += 1
            self.data.epoch_end[self.data.epoch] = self.data.epoch_end[sp.as_nat(self.data.epoch - 1)].add_seconds(WEEK)

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
            sp.record(token_id=params.token_id, ts=now_),
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
            sp.verify(self.data.distributors.contains(vote_item.amm), Errors.AMM_INVALID_OR_NOT_WHITELISTED)

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

            # Update power used & verify that available voting power of token has not been overshot
            power_available.value = sp.as_nat(
                power_available.value - vote_item.votes, Errors.NOT_ENOUGH_VOTING_POWER_AVAILABLE
            )


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
            distributors=sp.big_map(
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

    @sp.add_test(name="vote allows voting multiple times for the same amm using the same token")
    def test():
        scenario = sp.test_scenario()

        # Initialize dummy vote escrow with two tokens of voting powers 100 & 150
        ve = VE(powers=sp.big_map(l={1: sp.nat(100), 2: sp.nat(150)}))

        # Initialize voter with an AMM
        voter = Voter(
            epoch=1,
            epoch_end=sp.big_map(l={1: sp.timestamp(10)}),
            distributors=sp.big_map(
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
            distributors=sp.big_map(
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

    sp.add_compilation_target("voter", Voter())
