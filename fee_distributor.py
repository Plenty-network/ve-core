import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
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

    # big-map keys/values

    AMM_EPOCH_FEE_KEY = sp.TRecord(
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("amm", "epoch"))

    # Pair type represents a (token type, token-id) pairing. Token id only relevant for FA2
    AMM_EPOCH_FEE_VALUE = sp.TMap(
        sp.TRecord(
            token_address=sp.TAddress,
            type=sp.TPair(sp.TNat, sp.TNat),
        ).layout(("token_address", "type")),
        sp.TNat,
    )

    AMM_TO_TOKENS_VALUE = sp.TSet(
        sp.TRecord(
            token_address=sp.TAddress,
            type=sp.TPair(sp.TNat, sp.TNat),
        ).layout(("token_address", "type"))
    )

    CLAIM_LEDGER_KEY = sp.TRecord(
        token_id=sp.TNat,
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("token_id", ("amm", "epoch")))

    # parameter types

    ADD_FEES_PARAMS = sp.TRecord(
        epoch=sp.TNat,
        fees=sp.TMap(
            sp.TRecord(
                token_address=sp.TAddress,
                type=sp.TPair(sp.TNat, sp.TNat),
            ).layout(("token_address", "type")),
            sp.TNat,
        ),
    ).layout(("epoch", "fees"))

    CLAIM_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        owner=sp.TAddress,
        amm=sp.TAddress,
        epoch=sp.TNat,
        weight_share=sp.TNat,
    ).layout(("token_id", ("owner", ("amm", ("epoch", "weight_share")))))

    # Token types enumeration

    TOKEN_FA12 = 0
    TOKEN_FA2 = 1


#########
# Errors
#########


class Errors:
    AMM_INVALID_OR_NOT_WHITELISTED = "AMM_INVALID_OR_NOT_WHITELISTED"
    ALREADY_ADDED_FEES_FOR_EPOCH = "ALREADY_ADDED_FEES_FOR_EPOCH"
    VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH = "VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH"
    FEES_NOT_YET_ADDED = "FEES_NOT_YET_ADDED"
    INVALID_TOKEN = "INVALID_TOKEN"

    # Generic
    NOT_AUTHORISED = "NOT_AUTHORISED"


############
# Contracts
############


class FeeDistributor(sp.Contract):
    def __init__(
        self,
        amm_to_tokens=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=Types.AMM_TO_TOKENS_VALUE,
        ),
        amm_epoch_fee=sp.big_map(
            l={},
            tkey=Types.AMM_EPOCH_FEE_KEY,
            tvalue=Types.AMM_EPOCH_FEE_VALUE,
        ),
        claim_ledger=sp.big_map(
            l={},
            tkey=Types.CLAIM_LEDGER_KEY,
            tvalue=sp.TUnit,
        ),
        voter=Addresses.CONTRACT,
    ):
        self.init(
            amm_to_tokens=amm_to_tokens,
            amm_epoch_fee=amm_epoch_fee,
            claim_ledger=claim_ledger,
            voter=voter,
        )

    @sp.entry_point
    def add_fees(self, params):
        sp.set_type(params, Types.ADD_FEES_PARAMS)

        # Sanity checks
        sp.verify(self.data.amm_to_tokens.contains(sp.sender), Errors.AMM_INVALID_OR_NOT_WHITELISTED)
        sp.verify(
            ~self.data.amm_epoch_fee.contains(sp.record(amm=sp.sender, epoch=params.epoch)),
            Errors.ALREADY_ADDED_FEES_FOR_EPOCH,
        )

        # Update fees value for the epoch
        key_ = sp.record(amm=sp.sender, epoch=params.epoch)
        self.data.amm_epoch_fee[key_] = {}
        with sp.for_("token", params.fees.keys()) as token:
            sp.verify(self.data.amm_to_tokens[sp.sender].contains(token), Errors.INVALID_TOKEN)
            self.data.amm_epoch_fee[key_][token] = params.fees[token]

    @sp.entry_point
    def claim(self, params):
        sp.set_type(params, Types.CLAIM_PARAMS)

        # Sanity checks
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)
        sp.verify(
            self.data.amm_epoch_fee.contains(sp.record(amm=params.amm, epoch=params.epoch)),
            Errors.FEES_NOT_YET_ADDED,
        )
        sp.verify(
            ~self.data.claim_ledger.contains(sp.record(token_id=params.token_id, amm=params.amm, epoch=params.epoch)),
            Errors.VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH,
        )

        # Iterate through the two tokens and transfer the share to token / lock owner
        key_ = sp.record(amm=params.amm, epoch=params.epoch)
        with sp.for_("token", self.data.amm_epoch_fee[key_].keys()) as token:
            total_fees = self.data.amm_epoch_fee[key_][token]
            voter_fees_share = (total_fees * params.weight_share) // VOTE_SHARE_MULTIPLIER

            with sp.if_(sp.fst(token.type) == Types.TOKEN_FA12):
                TokenUtils.transfer_FA12(
                    sp.record(
                        from_=sp.self_address,
                        to_=params.owner,
                        value=voter_fees_share,
                        token_address=token.token_address,
                    )
                )
            with sp.else_():
                TokenUtils.transfer_FA2(
                    sp.record(
                        from_=sp.self_address,
                        to_=params.owner,
                        amount=voter_fees_share,
                        token_address=token.token_address,
                        token_id=sp.snd(token.type),
                    )
                )

        # Mark the voter (vePLY token id) as claimed
        self.data.claim_ledger[sp.record(token_id=params.token_id, amm=params.amm, epoch=params.epoch)] = sp.unit


if __name__ == "__main__":

    ########################
    # add_fees (valid test)
    ########################

    @sp.add_test(name="add_fees correctly adds fees for an epoch")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.record(token_address=Addresses.TOKEN_1, type=(Types.TOKEN_FA12, 0))
        TOKEN_2 = sp.record(token_address=Addresses.TOKEN_2, type=(Types.TOKEN_FA2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: {TOKEN_1, TOKEN_2},
                }
            ),
        )

        scenario += fee_dist

        # When fees is added for epoch 3 (random) through AMM
        scenario += fee_dist.add_fees(
            epoch=3,
            fees={TOKEN_1: 100, TOKEN_2: 200},
        ).run(sender=Addresses.AMM)

        # Storage is updated correctly
        scenario.verify_equal(
            fee_dist.data.amm_epoch_fee[sp.record(amm=Addresses.AMM, epoch=3)],
            {TOKEN_1: 100, TOKEN_2: 200},
        )

    ##########################
    # add_fees (failure test)
    ##########################

    @sp.add_test(name="add_fees fails if amm is invalid or not whitelisted")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.record(token_address=Addresses.TOKEN_1, type=(Types.TOKEN_FA12, 0))
        TOKEN_2 = sp.record(token_address=Addresses.TOKEN_2, type=(Types.TOKEN_FA2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: {TOKEN_1, TOKEN_2},
                }
            ),
        )

        scenario += fee_dist

        # When fees is added for epoch 3 (random) through AMM_1 (not-whitelisted), the txn fails
        scenario += fee_dist.add_fees(epoch=3, fees={TOKEN_1: 100, TOKEN_2: 200}).run(
            sender=Addresses.AMM_1,
            valid=False,
            exception=Errors.AMM_INVALID_OR_NOT_WHITELISTED,
        )

    @sp.add_test(name="add_fees fails if fees is already added for an amm in an epoch")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.record(token_address=Addresses.TOKEN_1, type=(Types.TOKEN_FA12, 0))
        TOKEN_2 = sp.record(token_address=Addresses.TOKEN_2, type=(Types.TOKEN_FA2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: {TOKEN_1, TOKEN_2},
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 100,
                        TOKEN_2: 200,
                    }
                }
            ),
        )

        scenario += fee_dist

        # When fees is added again for AMM in epoch 3, txn fails
        scenario += fee_dist.add_fees(epoch=3, fees={TOKEN_1: 100, TOKEN_2: 200}).run(
            sender=Addresses.AMM,
            valid=False,
            exception=Errors.ALREADY_ADDED_FEES_FOR_EPOCH,
        )

    #####################
    # claim (valid test)
    #####################

    @sp.add_test(name="claim works correctly for both fa12 and fa2 tokens")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 token pair for the AMM
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        TOKEN_1 = sp.record(token_address=token_1.address, type=(Types.TOKEN_FA12, 0))
        TOKEN_2 = sp.record(token_address=token_2.address, type=(Types.TOKEN_FA2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: {TOKEN_1, TOKEN_2},
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 100,
                        TOKEN_2: 200,
                    }
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += token_1
        scenario += token_2
        scenario += fee_dist

        # Mint tokens for fee_dist
        scenario += token_1.mint(address=fee_dist.address, value=100).run(sender=Addresses.ADMIN)
        scenario += token_2.mint(
            address=fee_dist.address,
            amount=200,
            metadata=FA2.FA2.make_metadata(name="TOKEN", decimals=18, symbol="TKN"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # When ALICE (40% share) and BOB (60% share) claim fee for epoch 3
        scenario += fee_dist.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                amm=Addresses.AMM,
                epoch=3,
                weight_share=int(0.4 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch=3,
                weight_share=int(0.6 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated clearly
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=3)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=3)] == sp.unit)

        # ALICE and BOB get their tokens
        scenario.verify(token_1.data.balances[Addresses.ALICE].balance == 40)
        scenario.verify(token_1.data.balances[Addresses.BOB].balance == 60)
        scenario.verify(token_2.data.ledger[Addresses.ALICE].balance == 80)
        scenario.verify(token_2.data.ledger[Addresses.BOB].balance == 120)

    #######################
    # claim (failure test)
    #######################

    @sp.add_test(name="claim fails if a lock owner has already claimed fees")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 token pair for the AMM
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        TOKEN_1 = sp.record(token_address=token_1.address, type=(Types.TOKEN_FA12, 0))
        TOKEN_2 = sp.record(token_address=token_2.address, type=(Types.TOKEN_FA2, 0))

        # Initialize with BOB's token marked as claimed
        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: {
                        TOKEN_1: (Types.TOKEN_FA12, 0),
                        TOKEN_2: (Types.TOKEN_FA2, 0),
                    },
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 100,
                        TOKEN_2: 200,
                    }
                }
            ),
            claim_ledger=sp.big_map(
                l={
                    sp.record(token_id=2, amm=Addresses.AMM, epoch=3): sp.unit,
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += token_1
        scenario += token_2
        scenario += fee_dist

        # When BOB tries to claim twice, txn fails
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch=3,
                weight_share=int(0.4 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH,
        )

    sp.add_compilation_target("fee_distributor", FeeDistributor())
