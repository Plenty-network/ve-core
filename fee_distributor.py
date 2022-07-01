import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:helpers/tokens/fa12.py").FA12
FA2 = sp.io.import_script_from_url("file:helpers/tokens/fa2.py")
Pure = sp.io.import_script_from_url("file:helpers/dummy/pure.py").Pure

############
# Constants
############

VOTE_SHARE_MULTIPLIER = 10 ** 18

########
# Types
########


class Types:

    # Token types on Tezos
    TOKEN_VARIANT = sp.TVariant(
        fa12=sp.TAddress,
        fa2=sp.TPair(sp.TAddress, sp.TNat),
        tez=sp.TUnit,
    )

    # big-map keys/values

    AMM_EPOCH_FEE_KEY = sp.TRecord(
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("amm", "epoch"))

    AMM_EPOCH_FEE_VALUE = sp.TMap(TOKEN_VARIANT, sp.TNat)

    AMM_TO_TOKENS_VALUE = sp.TSet(TOKEN_VARIANT)

    CLAIM_LEDGER_KEY = sp.TRecord(
        token_id=sp.TNat,
        amm=sp.TAddress,
        epoch=sp.TNat,
    ).layout(("token_id", ("amm", "epoch")))

    # parameter types

    ADD_AMM_PARAMS = sp.TRecord(
        amm=sp.TAddress,
        tokens=sp.TSet(TOKEN_VARIANT),
    ).layout(("amm", "tokens"))

    ADD_FEES_PARAMS = sp.TRecord(
        epoch=sp.TNat,
        fees=sp.TMap(TOKEN_VARIANT, sp.TNat),
    ).layout(("epoch", "fees"))

    CLAIM_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        owner=sp.TAddress,
        amm=sp.TAddress,
        epoch_vote_shares=sp.TList(sp.TRecord(epoch=sp.TNat, share=sp.TNat)),
    ).layout(("token_id", ("owner", ("amm", "epoch_vote_shares"))))


#########
# Errors
#########


class Errors:
    AMM_INVALID_OR_NOT_WHITELISTED = "AMM_INVALID_OR_NOT_WHITELISTED"
    ALREADY_ADDED_FEES_FOR_EPOCH = "ALREADY_ADDED_FEES_FOR_EPOCH"
    VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH = "VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH"
    FEES_NOT_YET_ADDED = "FEES_NOT_YET_ADDED"
    INVALID_TOKEN = "INVALID_TOKEN"
    ENTRYPOINT_DOES_NOT_ACCEPT_TEZ = "ENTRYPOINT_DOES_NOT_ACCEPT_TEZ"
    CONTRACT_DOES_NOT_ACCEPT_TEZ = "CONTRACT_DOES_NOT_ACCEPT_TEZ"

    # Generic
    NOT_AUTHORISED = "NOT_AUTHORISED"


############
# Contracts
############


class FeeDistributor(sp.Contract):
    def __init__(
        self,
        voter=Addresses.CONTRACT,
        core_factory=Addresses.CONTRACT,
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
    ):
        self.init(
            voter=voter,
            core_factory=core_factory,
            amm_to_tokens=amm_to_tokens,
            amm_epoch_fee=amm_epoch_fee,
            claim_ledger=claim_ledger,
        )

        self.init_type(
            sp.TRecord(
                voter=sp.TAddress,
                core_factory=sp.TAddress,
                amm_to_tokens=sp.TBigMap(sp.TAddress, Types.AMM_TO_TOKENS_VALUE),
                amm_epoch_fee=sp.TBigMap(Types.AMM_EPOCH_FEE_KEY, Types.AMM_EPOCH_FEE_VALUE),
                claim_ledger=sp.TBigMap(Types.CLAIM_LEDGER_KEY, sp.TUnit),
            )
        )

    # NOTE: This is tested in CoreFactory
    @sp.entry_point
    def add_amm(self, params):
        sp.set_type(params, Types.ADD_AMM_PARAMS)

        # Verify that the sender is the core factory
        sp.verify(sp.sender == self.data.core_factory, Errors.NOT_AUTHORISED)

        # Add amm and tokens to storage
        self.data.amm_to_tokens[params.amm] = params.tokens

    # NOTE: This is tested in CoreFactory
    @sp.entry_point
    def remove_amm(self, amm):
        sp.set_type(amm, sp.TAddress)

        # Verify that the sender is the core factory
        sp.verify(sp.sender == self.data.core_factory, Errors.NOT_AUTHORISED)

        # Delete AMM from storage
        del self.data.amm_to_tokens[amm]

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

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)

        # Local variables to store fees for individual tokens across epochs
        token_fees = sp.local("token_fees", sp.map(l={}, tkey=Types.TOKEN_VARIANT, tvalue=sp.TNat))

        # Iterate through the epochs and vote shares
        with sp.for_("epoch_vote_share", params.epoch_vote_shares) as epoch_vote_share:
            sp.verify(
                self.data.amm_epoch_fee.contains(sp.record(amm=params.amm, epoch=epoch_vote_share.epoch)),
                Errors.FEES_NOT_YET_ADDED,
            )
            sp.verify(
                ~self.data.claim_ledger.contains(
                    sp.record(token_id=params.token_id, amm=params.amm, epoch=epoch_vote_share.epoch)
                ),
                Errors.VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH,
            )

            key_ = sp.record(amm=params.amm, epoch=epoch_vote_share.epoch)

            # Iterate through the two tokens and record cumulative fees
            amm_epoch_fee = sp.compute(self.data.amm_epoch_fee[key_])
            with sp.for_("token", amm_epoch_fee.keys()) as token:
                total_fees = amm_epoch_fee[token]
                fees_share = token_fees.value.get(token, 0)
                token_fees.value[token] = fees_share + (total_fees * epoch_vote_share.share)

                # Mark the voter (vePLY token id) as claimed
                self.data.claim_ledger[
                    sp.record(
                        token_id=params.token_id,
                        amm=params.amm,
                        epoch=epoch_vote_share.epoch,
                    )
                ] = sp.unit

        # Iterate through the two tokens and transfer the share to token / lock owner
        with sp.for_("token", token_fees.value.keys()) as token:
            voter_fees_share = token_fees.value[token] // VOTE_SHARE_MULTIPLIER

            with token.match_cases() as arg:
                with arg.match("fa12") as address:
                    TokenUtils.transfer_FA12(
                        sp.record(
                            from_=sp.self_address,
                            to_=params.owner,
                            value=voter_fees_share,
                            token_address=address,
                        )
                    )
                with arg.match("fa2") as fa2_args:
                    TokenUtils.transfer_FA2(
                        sp.record(
                            from_=sp.self_address,
                            to_=params.owner,
                            amount=voter_fees_share,
                            token_address=sp.fst(fa2_args),
                            token_id=sp.snd(fa2_args),
                        )
                    )
                with arg.match("tez") as _:
                    with sp.if_(voter_fees_share > 0):
                        sp.send(params.owner, sp.utils.nat_to_mutez(voter_fees_share))

    # Reject tez sent to the contract address
    @sp.entry_point
    def default(self):
        sp.failwith(Errors.CONTRACT_DOES_NOT_ACCEPT_TEZ)


if __name__ == "__main__":

    ########################
    # add_fees (valid test)
    ########################

    @sp.add_test(name="add_fees correctly adds fees for an epoch with fa12 and fa2 tokens")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.variant("fa12", Addresses.TOKEN_1)
        TOKEN_2 = sp.variant("fa2", (Addresses.TOKEN_2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
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

    @sp.add_test(name="add_fees correctly adds fees for an epoch with fa12 token and tez")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.variant("fa12", Addresses.TOKEN_1)
        TEZ = sp.variant("tez", sp.unit)

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TEZ]),
                }
            ),
        )

        scenario += fee_dist

        # When fees is added for epoch 3 (random) through AMM
        scenario += fee_dist.add_fees(
            epoch=3,
            fees={TOKEN_1: 100, TEZ: 10},
        ).run(sender=Addresses.AMM)

        # Storage is updated correctly
        scenario.verify_equal(
            fee_dist.data.amm_epoch_fee[sp.record(amm=Addresses.AMM, epoch=3)],
            {TOKEN_1: 100, TEZ: 10},
        )

    ##########################
    # add_fees (failure test)
    ##########################

    @sp.add_test(name="add_fees fails if amm is invalid or not whitelisted")
    def test():
        scenario = sp.test_scenario()

        TOKEN_1 = sp.variant("fa12", Addresses.TOKEN_1)
        TOKEN_2 = sp.variant("fa2", (Addresses.TOKEN_2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
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

        TOKEN_1 = sp.variant("fa12", Addresses.TOKEN_1)
        TOKEN_2 = sp.variant("fa2", (Addresses.TOKEN_2, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
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

    @sp.add_test(name="claim works correctly for fa12 and fa2 tokens and one epoch")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 token pair for the AMM
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        TOKEN_1 = sp.variant("fa12", token_1.address)
        TOKEN_2 = sp.variant("fa2", (token_2.address, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
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
                epoch_vote_shares=[sp.record(epoch=3, share=int(0.4 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(sender=Addresses.CONTRACT)
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch_vote_shares=[sp.record(epoch=3, share=int(0.6 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=3)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=3)] == sp.unit)

        # ALICE and BOB get their tokens
        scenario.verify(token_1.data.balances[Addresses.ALICE].balance == 40)
        scenario.verify(token_1.data.balances[Addresses.BOB].balance == 60)
        scenario.verify(token_2.data.ledger[Addresses.ALICE].balance == 80)
        scenario.verify(token_2.data.ledger[Addresses.BOB].balance == 120)

    @sp.add_test(name="claim works correctly for fa12 and fa2 tokens and multiple epochs")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 token pair for the AMM
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        TOKEN_1 = sp.variant("fa12", token_1.address)
        TOKEN_2 = sp.variant("fa2", (token_2.address, 0))

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=1): {
                        TOKEN_1: 100,
                        TOKEN_2: 200,
                    },
                    sp.record(amm=Addresses.AMM, epoch=2): {
                        TOKEN_1: 300,
                        TOKEN_2: 400,
                    },
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 500,
                        TOKEN_2: 600,
                    },
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += token_1
        scenario += token_2
        scenario += fee_dist

        # Mint tokens for fee_dist
        scenario += token_1.mint(address=fee_dist.address, value=1000).run(sender=Addresses.ADMIN)
        scenario += token_2.mint(
            address=fee_dist.address,
            amount=1500,
            metadata=FA2.FA2.make_metadata(name="TOKEN", decimals=18, symbol="TKN"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # When ALICE (40% share) and BOB (60% share) claim fee for epochs 1, 2, 3
        scenario += fee_dist.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                amm=Addresses.AMM,
                epoch_vote_shares=[
                    sp.record(epoch=1, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=2, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=3, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                ],
            )
        ).run(sender=Addresses.CONTRACT)
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch_vote_shares=[
                    sp.record(epoch=1, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=2, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=3, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                ],
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=1)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=2)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=3)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=1)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=2)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=3)] == sp.unit)

        # ALICE and BOB get their tokens
        scenario.verify(token_1.data.balances[Addresses.ALICE].balance == 360)
        scenario.verify(token_1.data.balances[Addresses.BOB].balance == 540)
        scenario.verify(token_2.data.ledger[Addresses.ALICE].balance == 480)
        scenario.verify(token_2.data.ledger[Addresses.BOB].balance == 720)

    @sp.add_test(name="claim works correctly for fa12 token and tez and one epoch")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2
        token_1 = FA12(admin=Addresses.ADMIN)

        TOKEN_1 = sp.variant("fa12", token_1.address)
        TEZ = sp.variant("tez", sp.unit)

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TEZ]),
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 100,
                        TEZ: 200,
                    }
                }
            ),
            voter=Addresses.CONTRACT,
        )

        # Set tez balance for fee_dist
        fee_dist.set_initial_balance(sp.tez(1))

        # Initialize dummy claimers
        alice_dummy = Pure()
        bob_dummy = Pure()

        scenario += token_1
        scenario += fee_dist
        scenario += alice_dummy
        scenario += bob_dummy

        # Mint fa1.2 tokens for fee_dist
        scenario += token_1.mint(address=fee_dist.address, value=100).run(sender=Addresses.ADMIN)

        # When ALICE (40% share) and BOB (60% share) claim fee for epoch 3
        scenario += fee_dist.claim(
            sp.record(
                token_id=1,
                owner=alice_dummy.address,
                amm=Addresses.AMM,
                epoch_vote_shares=[sp.record(epoch=3, share=int(0.4 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(sender=Addresses.CONTRACT)
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=bob_dummy.address,
                amm=Addresses.AMM,
                epoch_vote_shares=[sp.record(epoch=3, share=int(0.6 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=3)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=3)] == sp.unit)

        # ALICE and BOB get their tokens
        scenario.verify(token_1.data.balances[alice_dummy.address].balance == 40)
        scenario.verify(token_1.data.balances[bob_dummy.address].balance == 60)
        scenario.verify(alice_dummy.balance == sp.mutez(80))
        scenario.verify(bob_dummy.balance == sp.mutez(120))

    @sp.add_test(name="claim works correctly for fa12 token and tez and multiple epochs")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2
        token_1 = FA12(admin=Addresses.ADMIN)

        TOKEN_1 = sp.variant("fa12", token_1.address)
        TEZ = sp.variant("tez", sp.unit)

        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TEZ]),
                }
            ),
            amm_epoch_fee=sp.big_map(
                l={
                    sp.record(amm=Addresses.AMM, epoch=1): {
                        TOKEN_1: 100,
                        TEZ: 200,
                    },
                    sp.record(amm=Addresses.AMM, epoch=2): {
                        TOKEN_1: 300,
                        TEZ: 400,
                    },
                    sp.record(amm=Addresses.AMM, epoch=3): {
                        TOKEN_1: 500,
                        TEZ: 600,
                    },
                }
            ),
            voter=Addresses.CONTRACT,
        )

        # Set tez balance for fee_dist
        fee_dist.set_initial_balance(sp.tez(1))

        # Initialize dummy claimers
        alice_dummy = Pure()
        bob_dummy = Pure()

        scenario += token_1
        scenario += fee_dist
        scenario += alice_dummy
        scenario += bob_dummy

        # Mint fa1.2 tokens for fee_dist
        scenario += token_1.mint(address=fee_dist.address, value=1000).run(sender=Addresses.ADMIN)

        # When ALICE (40% share) and BOB (60% share) claim fee for epoch 3
        scenario += fee_dist.claim(
            sp.record(
                token_id=1,
                owner=alice_dummy.address,
                amm=Addresses.AMM,
                epoch_vote_shares=[
                    sp.record(epoch=1, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=2, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=3, share=int(0.4 * VOTE_SHARE_MULTIPLIER)),
                ],
            )
        ).run(sender=Addresses.CONTRACT)
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=bob_dummy.address,
                amm=Addresses.AMM,
                epoch_vote_shares=[
                    sp.record(epoch=1, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=2, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                    sp.record(epoch=3, share=int(0.6 * VOTE_SHARE_MULTIPLIER)),
                ],
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=1)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=2)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=1, amm=Addresses.AMM, epoch=3)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=1)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=2)] == sp.unit)
        scenario.verify(fee_dist.data.claim_ledger[sp.record(token_id=2, amm=Addresses.AMM, epoch=3)] == sp.unit)

        # # ALICE and BOB get their tokens
        scenario.verify(token_1.data.balances[alice_dummy.address].balance == 360)
        scenario.verify(token_1.data.balances[bob_dummy.address].balance == 540)
        scenario.verify(alice_dummy.balance == sp.mutez(480))
        scenario.verify(bob_dummy.balance == sp.mutez(720))

    #######################
    # claim (failure test)
    #######################

    @sp.add_test(name="claim fails if a lock owner has already claimed fees or fees is not added for epoch")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 token pair for the AMM
        TOKEN_1 = sp.variant("fa12", Addresses.TOKEN_1)
        TOKEN_2 = sp.variant("fa2", (Addresses.TOKEN_2, 0))

        # Initialize with BOB's token marked as claimed
        fee_dist = FeeDistributor(
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: sp.set([TOKEN_1, TOKEN_2]),
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

        scenario += fee_dist

        # When BOB tries to claim twice, txn fails
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch_vote_shares=[sp.record(epoch=3, share=int(0.4 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.VOTER_ALREADY_CLAIMED_FEES_FOR_EPOCH,
        )

        # When BOB tries to claim for epoch that has not been added yet, txn fails
        scenario += fee_dist.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                amm=Addresses.AMM,
                epoch_vote_shares=[sp.record(epoch=4, share=int(0.4 * VOTE_SHARE_MULTIPLIER))],
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.FEES_NOT_YET_ADDED,
        )

    sp.add_compilation_target("fee_distributor", FeeDistributor())
