import smartpy as sp

Errors = sp.io.import_script_from_url("file:utils/errors.py")
FA2 = sp.io.import_script_from_url("file:helpers/tokens/fa2.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
Constants = sp.io.import_script_from_url("file:utils/constants.py")
Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
Pure = sp.io.import_script_from_url("file:helpers/dummy/pure.py").Pure
FA12 = sp.io.import_script_from_url("file:helpers/tokens/fa12.py").FA12
Voter = sp.io.import_script_from_url("file:helpers/dummy/voter.py").Voter


############
# Constants
############

VOTE_SHARE_MULTIPLIER = Constants.VOTE_SHARE_MULTIPLIER

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

    # big-map key/value types

    EPOCH_BRIBES_KEY = sp.TRecord(
        epoch=sp.TNat,
        bribe_id=sp.TNat,
    ).layout(("epoch", "bribe_id"))

    EPOCH_BRIBES_VALUE = sp.TRecord(
        provider=sp.TAddress,
        bribe=sp.TRecord(
            type=TOKEN_VARIANT,
            value=sp.TNat,
        ).layout(("type", "value")),
    ).layout(("provider", "bribe"))

    CLAIM_LEDGER_KEY = sp.TRecord(
        token_id=sp.TNat,
        bribe_id=sp.TNat,
    ).layout(("token_id", "bribe_id"))

    # param types

    ADD_BRIBE_PARAMS = sp.TRecord(
        epoch=sp.TNat,
        type=TOKEN_VARIANT,
        value=sp.TNat,
    ).layout(("epoch", ("type", "value")))

    CLAIM_PARAMS = sp.TRecord(
        token_id=sp.TNat,
        owner=sp.TAddress,
        epoch=sp.TNat,
        bribe_id=sp.TNat,
        vote_share=sp.TNat,
    ).layout(("token_id", ("owner", ("epoch", ("bribe_id", "vote_share")))))


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
        epoch_ = sp.compute(
            sp.view(
                "get_current_epoch",
                self.data.voter,
                sp.unit,
                sp.TPair(sp.TNat, sp.TTimestamp),
            ).open_some(Errors.INVALID_VIEW)
        )

        # Sanity checks
        sp.verify(
            (params.epoch > sp.fst(epoch_)) | ((params.epoch == sp.fst(epoch_)) & (sp.now < sp.snd(epoch_))),
            Errors.EPOCH_IN_THE_PAST,
        )

        # Insert bribe in storage
        self.data.uid += 1
        self.data.epoch_bribes[sp.record(epoch=params.epoch, bribe_id=self.data.uid)] = sp.record(
            provider=sp.sender,
            bribe=sp.record(
                type=params.type,
                value=params.value,
            ),
        )

        # Retrieve bribe amount from sender
        with params.type.match_cases() as arg:
            with arg.match("fa12") as address:
                TokenUtils.transfer_FA12(
                    sp.record(
                        from_=sp.sender,
                        to_=sp.self_address,
                        value=params.value,
                        token_address=address,
                    )
                )
            with arg.match("fa2") as fa2_args:
                TokenUtils.transfer_FA2(
                    sp.record(
                        from_=sp.sender,
                        to_=sp.self_address,
                        amount=params.value,
                        token_address=sp.fst(fa2_args),
                        token_id=sp.snd(fa2_args),
                    )
                )
            with arg.match("tez") as _:
                # verify if correct amount has been sent over
                sp.verify(sp.amount == sp.utils.nat_to_mutez(params.value), Errors.INCORRECT_TEZ_VALUE_SENT)

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
        epoch_bribe = sp.compute(self.data.epoch_bribes[sp.record(epoch=params.epoch, bribe_id=params.bribe_id)])
        voter_bribe_share = (epoch_bribe.bribe.value * params.vote_share) // VOTE_SHARE_MULTIPLIER

        # Transfer bribe to voter
        with epoch_bribe.bribe.type.match_cases() as arg:
            with arg.match("fa12") as address:
                TokenUtils.transfer_FA12(
                    sp.record(
                        from_=sp.self_address,
                        to_=params.owner,
                        value=voter_bribe_share,
                        token_address=address,
                    )
                )
            with arg.match("fa2") as fa2_args:
                TokenUtils.transfer_FA2(
                    sp.record(
                        from_=sp.self_address,
                        to_=params.owner,
                        amount=voter_bribe_share,
                        token_address=sp.fst(fa2_args),
                        token_id=sp.snd(fa2_args),
                    )
                )
            with arg.match("tez") as _:
                sp.send(params.owner, sp.utils.nat_to_mutez(voter_bribe_share))

        # Mark the lock token as claimed
        self.data.claim_ledger[sp.record(token_id=params.token_id, bribe_id=params.bribe_id)] = sp.unit

    @sp.entry_point
    def return_bribe(self, params):
        sp.set_type(params, sp.TRecord(epoch=sp.TNat, bribe_id=sp.TNat))

        # Sanity checks
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)
        sp.verify(
            self.data.epoch_bribes.contains(params),
            Errors.INVALID_BRIBE_ID_OR_EPOCH,
        )
        epoch_bribe = sp.compute(self.data.epoch_bribes[params])

        # Return bribe to provider
        with epoch_bribe.bribe.type.match_cases() as arg:
            with arg.match("fa12") as address:
                TokenUtils.transfer_FA12(
                    sp.record(
                        from_=sp.self_address,
                        to_=epoch_bribe.provider,
                        value=epoch_bribe.bribe.value,
                        token_address=address,
                    )
                )
            with arg.match("fa2") as fa2_args:
                TokenUtils.transfer_FA2(
                    sp.record(
                        from_=sp.self_address,
                        to_=epoch_bribe.provider,
                        amount=epoch_bribe.bribe.value,
                        token_address=sp.fst(fa2_args),
                        token_id=sp.snd(fa2_args),
                    )
                )
            with arg.match("tez") as _:
                sp.send(epoch_bribe.provider, sp.utils.nat_to_mutez(epoch_bribe.bribe.value))

        self.data.epoch_bribes[params].bribe.value = sp.nat(0)

    # Reject tez sent to the contract address
    @sp.entry_point
    def default(self):
        sp.failwith(Errors.CONTRACT_DOES_NOT_ACCEPT_TEZ)


if __name__ == "__main__":

    #########################
    # add_bribe (valid test)
    #########################

    @sp.add_test(name="add_bribe correctly adds a bribe for ongoing and future epochs in all token variants")
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
            type=sp.variant("fa12", token_1.address),
            value=100,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(5))

        # and future epoch
        scenario += bribe.add_bribe(
            epoch=3,
            type=sp.variant("fa2", (token_2.address, 0)),
            value=150,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(6))

        # and another one with tez
        scenario += bribe.add_bribe(
            epoch=4,
            type=sp.variant("tez", sp.unit),
            value=200,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(6), amount=sp.mutez(200))

        # Storage is updated correctly
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=1, bribe_id=1)].provider == Addresses.ALICE,
        )
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=1, bribe_id=1)].bribe
            == sp.record(type=sp.variant("fa12", token_1.address), value=100)
        )
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=3, bribe_id=2)].bribe
            == sp.record(type=sp.variant("fa2", (token_2.address, 0)), value=150)
        )
        scenario.verify(
            bribe.data.epoch_bribes[sp.record(epoch=4, bribe_id=3)].bribe
            == sp.record(type=sp.variant("tez", sp.unit), value=200)
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
        scenario += bribe.add_bribe(epoch=1, type=sp.variant("fa12", Addresses.TOKEN), value=100,).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(5),
            valid=False,
            exception=Errors.EPOCH_IN_THE_PAST,
        )

        # When ALICE creates a bribe for current epoch, but after it is over, txn fails again
        scenario += bribe.add_bribe(epoch=2, type=sp.variant("fa12", Addresses.TOKEN), value=100,).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(12),
            valid=False,
            exception=Errors.EPOCH_IN_THE_PAST,
        )

    #####################
    # claim (valid test)
    #####################

    @sp.add_test(name="claim works correctly for all token variants")
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
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("fa12", token_1.address),
                            value=100,
                        ),
                    ),
                    sp.record(epoch=3, bribe_id=2): sp.record(
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("fa2", (token_2.address, 0)),
                            value=150,
                        ),
                    ),
                    sp.record(epoch=4, bribe_id=3): sp.record(
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("tez", sp.unit),
                            value=150,
                        ),
                    ),
                }
            ),
            voter=Addresses.CONTRACT,
        )

        # Create claim dummies for tez claim
        alice_dummy = Pure()
        bob_dummy = Pure()

        # Set tez balance for bribe contract
        bribe.set_initial_balance(sp.tez(1))

        scenario += token_1
        scenario += token_2
        scenario += bribe
        scenario += alice_dummy
        scenario += bob_dummy

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
                vote_share=int(0.35 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and BOB claims bribe 1 using his lock token
        scenario += bribe.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                epoch=1,
                bribe_id=1,
                vote_share=int(0.65 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and ALICE claims bribe 2 using her lock token
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=3,
                bribe_id=2,
                vote_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and BOB claims bribe 2 using his lock token
        scenario += bribe.claim(
            sp.record(
                token_id=2,
                owner=Addresses.BOB,
                epoch=3,
                bribe_id=2,
                vote_share=int(0.8 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and ALICE (dummy) claims bribe 3 using her lock token
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=alice_dummy.address,
                epoch=4,
                bribe_id=3,
                vote_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # and BOB (dummy) claims bribe 3 using his lock token
        scenario += bribe.claim(
            sp.record(
                token_id=2,
                owner=bob_dummy.address,
                epoch=4,
                bribe_id=3,
                vote_share=int(0.8 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=1, bribe_id=1)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=1, bribe_id=2)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=1, bribe_id=3)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=2, bribe_id=1)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=2, bribe_id=2)] == sp.unit)
        scenario.verify(bribe.data.claim_ledger[sp.record(token_id=2, bribe_id=3)] == sp.unit)

        # ALICE & BOB receive their tokens correctly
        scenario.verify(token_1.data.balances[Addresses.ALICE].balance == 35)
        scenario.verify(token_1.data.balances[Addresses.BOB].balance == 65)
        scenario.verify(token_2.data.ledger[Addresses.ALICE].balance == 30)
        scenario.verify(token_2.data.ledger[Addresses.BOB].balance == 120)
        scenario.verify(alice_dummy.balance == sp.mutez(30))
        scenario.verify(bob_dummy.balance == sp.mutez(120))

    #######################
    # claim (failure test)
    #######################

    @sp.add_test(name="claim fails if incorrect id is provided or if lock owner has already claimed")
    def test():
        scenario = sp.test_scenario()

        bribe = Bribe(
            epoch_bribes=sp.big_map(
                l={
                    sp.record(epoch=1, bribe_id=1): sp.record(
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("fa12", Addresses.TOKEN_1),
                            value=100,
                        ),
                    ),
                    sp.record(epoch=3, bribe_id=2): sp.record(
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("fa2", (Addresses.TOKEN_2, 0)),
                            value=150,
                        ),
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

        # When ALICE tries to claim an invalid epoch, txn fails
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=4,
                bribe_id=2,
                vote_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.INVALID_BRIBE_ID_OR_EPOCH,
        )

        # When ALICE tries to claim a second time, txn fails
        scenario += bribe.claim(
            sp.record(
                token_id=1,
                owner=Addresses.ALICE,
                epoch=1,
                bribe_id=1,
                vote_share=int(0.2 * VOTE_SHARE_MULTIPLIER),
            )
        ).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.VOTER_HAS_ALREADY_CLAIMED_BRIBE,
        )

    ############################
    # return_bribe (valid test)
    ############################

    @sp.add_test(name="return_bribe returns bribe amount back to the provider")
    def test():
        scenario = sp.test_scenario()

        # Initialize FA1.2 and FA2 tokens
        token_1 = FA12(admin=Addresses.ADMIN)
        token_2 = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        # Create claim dummies for tez claim
        alice_dummy = Pure()

        bribe = Bribe(
            epoch_bribes=sp.big_map(
                l={
                    sp.record(epoch=1, bribe_id=1): sp.record(
                        provider=alice_dummy.address,
                        bribe=sp.record(
                            type=sp.variant("fa12", token_1.address),
                            value=100,
                        ),
                    ),
                    sp.record(epoch=3, bribe_id=2): sp.record(
                        provider=alice_dummy.address,
                        bribe=sp.record(
                            type=sp.variant("fa2", (token_2.address, 0)),
                            value=150,
                        ),
                    ),
                    sp.record(epoch=4, bribe_id=3): sp.record(
                        provider=alice_dummy.address,
                        bribe=sp.record(
                            type=sp.variant("tez", sp.unit),
                            value=150,
                        ),
                    ),
                }
            ),
            voter=Addresses.CONTRACT,
        )

        # Set tez balance for bribe contract
        bribe.set_initial_balance(sp.tez(1))

        scenario += token_1
        scenario += token_2
        scenario += bribe
        scenario += alice_dummy

        # Mint tokens for bribe contract
        scenario += token_1.mint(address=bribe.address, value=100).run(sender=Addresses.ADMIN)
        scenario += token_2.mint(
            address=bribe.address,
            amount=150,
            metadata=FA2.FA2.make_metadata(name="TOKEN", decimals=18, symbol="TKN"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # Call return_bribe for epoch 1
        scenario += bribe.return_bribe(epoch=1, bribe_id=1).run(
            sender=Addresses.CONTRACT,
        )

        # Call return_bribe for epoch 3
        scenario += bribe.return_bribe(epoch=3, bribe_id=2).run(
            sender=Addresses.CONTRACT,
        )

        # Call return_bribe for epoch 4
        scenario += bribe.return_bribe(epoch=4, bribe_id=3).run(
            sender=Addresses.CONTRACT,
        )

        # alice_dummy receives correct amounts
        scenario.verify(token_1.data.balances[alice_dummy.address].balance == 100)
        scenario.verify(token_2.data.ledger[alice_dummy.address].balance == 150)
        scenario.verify(alice_dummy.balance == sp.mutez(150))

    ##############################
    # return_bribe (failure test)
    ##############################

    @sp.add_test(name="return_bribe fails if not called by voter or if invalid id is provided")
    def test():
        scenario = sp.test_scenario()

        bribe = Bribe(
            epoch_bribes=sp.big_map(
                l={
                    sp.record(epoch=1, bribe_id=1): sp.record(
                        provider=Addresses.ALICE,
                        bribe=sp.record(
                            type=sp.variant("fa12", Addresses.TOKEN_1),
                            value=100,
                        ),
                    ),
                }
            ),
            voter=Addresses.CONTRACT,
        )

        scenario += bribe

        # When return_bribe is called by ALICE, txn fails
        scenario += bribe.return_bribe(epoch=1, bribe_id=1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

        # When return_bribe is called for epoch 2, txn fails
        scenario += bribe.return_bribe(epoch=2, bribe_id=1).run(
            sender=Addresses.CONTRACT,
            valid=False,
            exception=Errors.INVALID_BRIBE_ID_OR_EPOCH,
        )

    sp.add_compilation_target("bribe", Bribe())
