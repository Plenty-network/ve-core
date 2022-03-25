import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
Voter = sp.io.import_script_from_url("file:helpers/dummy/voter.py").Voter
FA12 = sp.io.import_script_from_url("file:helpers/tokens/fa12.py").FA12
FA2 = sp.io.import_script_from_url("file:helpers/tokens/fa2.py")

############
# Constants
############

VOTE_SHARE_MULTIPLIER = 10 ** 18

########
# Types
########


class Types:

    # big-map key/value types

    EPOCH_BRIBES_KEY = sp.TRecord(
        epoch=sp.TNat,
        bribe_id=sp.TNat,
    ).layout(("epoch", "bribe_id"))

    # Pair type represents a (token type, token-id) pairing. Token id only relevant for FA2
    EPOCH_BRIBES_VALUE = sp.TRecord(
        token_address=sp.TAddress,
        type=sp.TPair(sp.TNat, sp.TNat),
        amount=sp.TNat,
    ).layout(("token_address", ("type", "amount")))

    CLAIM_LEDGER_KEY = sp.TRecord(
        token_id=sp.TNat,
        bribe_id=sp.TNat,
    ).layout(("token_id", "bribe_id"))

    # param types

    ADD_BRIBE_PARAMS = sp.TRecord(
        epoch=sp.TNat,
        token_address=sp.TAddress,
        type=sp.TPair(sp.TNat, sp.TNat),
        amount=sp.TNat,
    ).layout(("epoch", ("token_address", ("type", "amount"))))

    CLAIM_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        owner=sp.TAddress,
        epoch=sp.TNat,
        bribe_id=sp.TNat,
        weight_share=sp.TNat,
    ).layout(("token_id", ("owner", ("epoch", ("bribe_id", "weight_share")))))

    # Token-type enumeration
    TOKEN_FA12 = 0
    TOKEN_FA2 = 1


#########
# Errors
#########


class Errors:
    EPOCH_IN_THE_PAST = "EPOCH_IN_THE_PAST"
    INVALID_BRIBE_ID_OR_EPOCH = "INVALID_BRIBE_ID_OR_EPOCH"
    VOTER_HAS_ALREADY_CLAIMED_BRIBE = "VOTER_HAS_ALREADY_CLAIMED_BRIBE"

    # Generic
    INVALID_VIEW = "INVALID_VIEW"
    NOT_AUTHORISED = "NOT_AUTHORISED"


###########
# Contract
###########


class Bribe(sp.Contract):
    def __init__(
        self,
        uid=sp.nat(0),
        voter=Addresses.CONTRACT,
        epoch_bribes=sp.big_map(
            l={},
            tkey=Types.EPOCH_BRIBES_KEY,
            tvalue=Types.EPOCH_BRIBES_VALUE,
        ),
        claim_ledger=sp.big_map(
            l={},
            tkey=Types.CLAIM_LEDGER_KEY,
            tvalue=sp.TUnit,
        ),
    ):
        self.init(
            uid=uid,
            voter=voter,
            epoch_bribes=epoch_bribes,
            claim_ledger=claim_ledger,
        )

        self.init_type(
            sp.TRecord(
                uid=sp.TNat,
                voter=sp.TAddress,
                epoch_bribes=sp.TBigMap(Types.EPOCH_BRIBES_KEY, Types.EPOCH_BRIBES_VALUE),
                claim_ledger=sp.TBigMap(Types.CLAIM_LEDGER_KEY, sp.TUnit),
            )
        )

    @sp.entry_point
    def add_bribe(self, params):
        sp.set_type(params, Types.ADD_BRIBE_PARAMS)

        # Get current epoch from Voter
        epoch_ = sp.view(
            "get_current_epoch",
            self.data.voter,
            sp.unit,
            sp.TPair(sp.TNat, sp.TTimestamp),
        ).open_some(Errors.INVALID_VIEW)

        # Sanity checks
        sp.verify(
            (params.epoch > sp.fst(epoch_)) | ((params.epoch == sp.fst(epoch_)) & (sp.now < sp.snd(epoch_))),
            Errors.EPOCH_IN_THE_PAST,
        )

        # Insert bribe in storage
        self.data.uid += 1
        self.data.epoch_bribes[sp.record(epoch=params.epoch, bribe_id=self.data.uid)] = sp.record(
            token_address=params.token_address,
            type=params.type,
            amount=params.amount,
        )

        # Retrieve bribe amount from sender
        with sp.if_(sp.fst(params.type) == Types.TOKEN_FA12):
            TokenUtils.transfer_FA12(
                sp.record(
                    from_=sp.sender,
                    to_=sp.self_address,
                    value=params.amount,
                    token_address=params.token_address,
                )
            )
        with sp.else_():
            TokenUtils.transfer_FA2(
                sp.record(
                    from_=sp.sender,
                    to_=sp.self_address,
                    amount=params.amount,
                    token_address=params.token_address,
                    token_id=sp.snd(params.type),
                )
            )

    @sp.entry_point
    def claim(self, params):
        sp.set_type(params, Types.CLAIM_PARAMS)

        # Sanity checks
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)
        sp.verify(
            self.data.epoch_bribes.contains(sp.record(epoch=params.epoch, bribe_id=params.bribe_id)),
            Errors.INVALID_BRIBE_ID_OR_EPOCH,
        )
        sp.verify(
            ~self.data.claim_ledger.contains(sp.record(token_id=params.token_id, bribe_id=params.bribe_id)),
            Errors.VOTER_HAS_ALREADY_CLAIMED_BRIBE,
        )

        # Calculate bribe share for voter
        bribe_ = self.data.epoch_bribes[sp.record(epoch=params.epoch, bribe_id=params.bribe_id)]
        bribe_amount = bribe_.amount
        voter_bribe_share = (bribe_amount * params.weight_share) // VOTE_SHARE_MULTIPLIER

        # Transfer bribe to voter
        with sp.if_(sp.fst(bribe_.type) == Types.TOKEN_FA12):
            TokenUtils.transfer_FA12(
                sp.record(
                    from_=sp.self_address,
                    to_=params.owner,
                    value=voter_bribe_share,
                    token_address=bribe_.token_address,
                )
            )
        with sp.else_():
            TokenUtils.transfer_FA2(
                sp.record(
                    from_=sp.self_address,
                    to_=params.owner,
                    amount=voter_bribe_share,
                    token_address=bribe_.token_address,
                    token_id=sp.snd(bribe_.type),
                )
            )

        # Mark the lock token as claimed
        self.data.claim_ledger[sp.record(token_id=params.token_id, bribe_id=params.bribe_id)] = sp.unit


if __name__ == "__main__":

    #########################
    # add_bribe (valid test)
    #########################

    @sp.add_test(name="add_bribe correctly adds a bribe for ongoing and future epochs")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 tokens
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        voter = Voter(epoch=sp.nat(1), end=sp.timestamp(10))
        bribe = Bribe(voter=voter.address)

        scenario += token_1
        scenario += token_2
        scenario += voter
        scenario += bribe

        # Mint tokens for ALICE (bribe creator)
        scenario += token_1.mint(address=Addresses.ALICE, value=100).run(sender=Addresses.ADMIN)
        scenario += token_2.mint(
            address=Addresses.ALICE,
            amount=200,
            metadata=FA2.FA2.make_metadata(name="TOKEN", decimals=18, symbol="TKN"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # Approve tokens bribe contract
        scenario += token_1.approve(spender=bribe.address, value=100).run(sender=Addresses.ALICE)
        scenario += token_2.update_operators(
            [sp.variant("add_operator", sp.record(owner=Addresses.ALICE, operator=bribe.address, token_id=0))]
        ).run(sender=Addresses.ALICE)

        # When ALICE creates a bribe in current epoch
        scenario += bribe.add_bribe(
            epoch=1,
            token_address=token_1.address,
            type=(Types.TOKEN_FA12, 0),
            amount=100,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(5))

        # and future epoch
        scenario += bribe.add_bribe(
            epoch=3,
            token_address=token_2.address,
            type=(Types.TOKEN_FA2, 0),
            amount=150,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(6))

        # Storage is updated correctly
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=1, bribe_id=1)]
            == sp.record(token_address=token_1.address, type=(Types.TOKEN_FA12, 0), amount=100)
        )
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=3, bribe_id=2)]
            == sp.record(token_address=token_2.address, type=(Types.TOKEN_FA2, 0), amount=150)
        )

        # Tokens are correctly retrieved from ALICE
        scenario.verify(token_1.data.balances[bribe.address].balance == 100)
        scenario.verify(token_2.data.ledger[bribe.address].balance == 150)

    ###########################
    # add_bribe (failure test)
    ###########################

    @sp.add_test(name="add_bribe fails for past epochs")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(epoch=sp.nat(2), end=sp.timestamp(10))
        bribe = Bribe(voter=voter.address)

        scenario += voter
        scenario += bribe

        # When ALICE creates a bribe for a past epoch, txn fails
        scenario += bribe.add_bribe(
            epoch=1,
            token_address=Addresses.TOKEN,
            type=(Types.TOKEN_FA12, 0),
            amount=100,
        ).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(5),
            valid=False,
            exception=Errors.EPOCH_IN_THE_PAST,
        )

        # When ALICE creates a bribe for current epoch, but after it is over, txn fails again
        scenario += bribe.add_bribe(
            epoch=2,
            token_address=Addresses.TOKEN,
            type=(Types.TOKEN_FA12, 0),
            amount=100,
        ).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(12),
            valid=False,
            exception=Errors.EPOCH_IN_THE_PAST,
        )

    #####################
    # claim (valid test)
    #####################

    @sp.add_test(name="claim works correctly for both fa12 and fa2 tokens")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 tokens
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        bribe = Bribe(
            epoch_bribes=sp.big_map(
                l={
                    sp.record(epoch=1, bribe_id=1): sp.record(
                        token_address=token_1.address, type=(Types.TOKEN_FA12, 0), amount=100
                    ),
                    sp.record(epoch=3, bribe_id=2): sp.record(
                        token_address=token_2.address, type=(Types.TOKEN_FA2, 0), amount=150
                    ),
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += token_1
        scenario += token_2
        scenario += bribe

        # Mint tokens for bribe contract
        scenario += token_1.mint(address=bribe.address, value=100).run(sender=Addresses.ADMIN)
        scenario += token_2.mint(
            address=bribe.address,
            amount=150,
            metadata=FA2.FA2.make_metadata(name="TOKEN", decimals=18, symbol="TKN"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # When ALICE claims bribe 1 using her lock token
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=1,
                bribe_id=1,
                weight_share=int(0.35 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and BOB claims bribe 1 using his lock token
        scenario += bribe.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                epoch=1,
                bribe_id=1,
                weight_share=int(0.65 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and ALICE claims bribe 2 using her lock token
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=3,
                bribe_id=2,
                weight_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and BOB claims bribe 2 using his lock token
        scenario += bribe.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                epoch=3,
                bribe_id=2,
                weight_share=int(0.8 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=1, bribe_id=1)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=1, bribe_id=2)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=2, bribe_id=1)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=2, bribe_id=2)] == sp.unit)

        # ALICE & BOB receive their tokens correctly
        scenario.verify(token_1.data.balances[Addresses.ALICE].balance == 35)
        scenario.verify(token_1.data.balances[Addresses.BOB].balance == 65)
        scenario.verify(token_2.data.ledger[Addresses.ALICE].balance == 30)
        scenario.verify(token_2.data.ledger[Addresses.BOB].balance == 120)

    #######################
    # claim (failure test)
    #######################

    @sp.add_test(name="claim fails if lock owner has already claimed")
    def test():
        scenario = sp.test_scenario()

        bribe = Bribe(
            epoch_bribes=sp.big_map(
                l={
                    sp.record(epoch=1, bribe_id=1): sp.record(
                        token_address=Addresses.TOKEN, type=(Types.TOKEN_FA12, 0), amount=100
                    ),
                    sp.record(epoch=3, bribe_id=2): sp.record(
                        token_address=Addresses.TOKEN, type=(Types.TOKEN_FA2, 0), amount=150
                    ),
                }
            ),
            claim_ledger=sp.big_map(
                l={
                    sp.record(token_id=1, bribe_id=1): sp.unit,
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += bribe

        # When ALICE tries to claim a second time, txn fails
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=1,
                bribe_id=1,
                weight_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.VOTER_HAS_ALREADY_CLAIMED_BRIBE,
        )

    sp.add_compilation_target("bribe", Bribe())
