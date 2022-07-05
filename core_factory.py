import smartpy as sp

Voter = sp.io.import_script_from_url("file:voter.py").Voter
Bribe = sp.io.import_script_from_url("file:bribe.py").Bribe
Gauge = sp.io.import_script_from_url("file:gauge.py").Gauge
Errors = sp.io.import_script_from_url("file:utils/errors.py")
Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
FeeDistributor = sp.io.import_script_from_url("file:fee_distributor.py").FeeDistributor

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

    ADD_AMM_PARAMS = sp.TRecord(
        amm=sp.TAddress,
        lp_token_address=sp.TAddress,
        tokens=sp.TSet(TOKEN_VARIANT),
    ).layout(("amm", ("lp_token_address", "tokens")))


###########
# Contract
###########


class CoreFactory(sp.Contract):
    def __init__(
        self,
        add_admin=Addresses.ADMIN,
        remove_admin=Addresses.ADMIN,
        proposed_add_admin=sp.none,
        proposed_remove_admin=sp.none,
        voter=Addresses.CONTRACT,
        ply_address=Addresses.TOKEN,
        ve_address=Addresses.CONTRACT,
        fee_distributor=Addresses.CONTRACT,
        amm_registered=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TUnit,
        ),
    ):
        self.init(
            add_admin=add_admin,
            remove_admin=remove_admin,
            proposed_add_admin=proposed_add_admin,
            proposed_remove_admin=proposed_remove_admin,
            voter=voter,
            ply_address=ply_address,
            ve_address=ve_address,
            fee_distributor=fee_distributor,
            amm_registered=amm_registered,
        )

        self.init_type(
            sp.TRecord(
                add_admin=sp.TAddress,
                remove_admin=sp.TAddress,
                proposed_add_admin=sp.TOption(sp.TAddress),
                proposed_remove_admin=sp.TOption(sp.TAddress),
                voter=sp.TAddress,
                ply_address=sp.TAddress,
                ve_address=sp.TAddress,
                fee_distributor=sp.TAddress,
                amm_registered=sp.TBigMap(sp.TAddress, sp.TUnit),
            )
        )

        self.gauge = Gauge()
        self.bribe = Bribe()

    @sp.entry_point
    def set_fee_distributor(self, address):
        sp.set_type(address, sp.TAddress)
        with sp.if_(self.data.fee_distributor == Addresses.CONTRACT):
            self.data.fee_distributor = address

    @sp.entry_point
    def add_amm(self, params):
        sp.set_type(params, Types.ADD_AMM_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(sp.sender == self.data.add_admin, Errors.NOT_AUTHORISED)
        sp.verify(~self.data.amm_registered.contains(params.amm), Errors.AMM_ALREADY_ADDED)

        # Mark AMM as added
        self.data.amm_registered[params.amm] = sp.unit

        # Deploy gauge for AMM
        gauge_ = sp.create_contract(contract=self.gauge, storage=self.get_gauge_storage(params.lp_token_address))

        # Deploy bribe for AMM
        bribe_ = sp.create_contract(contract=self.bribe, storage=self.get_bribe_storage())

        # Set bribe and gauge for the AMM in Voter
        c_voter = sp.contract(
            sp.TRecord(
                amm=sp.TAddress,
                gauge=sp.TAddress,
                bribe=sp.TAddress,
            ).layout(("amm", ("gauge", "bribe"))),
            self.data.voter,
            "add_amm",
        ).open_some()
        sp.transfer(sp.record(amm=params.amm, gauge=gauge_, bribe=bribe_), sp.tez(0), c_voter)

        # Set AMM and associated tokens in FeeDistributor
        c_fee = sp.contract(
            sp.TRecord(
                amm=sp.TAddress,
                tokens=sp.TSet(Types.TOKEN_VARIANT),
            ).layout(("amm", "tokens")),
            self.data.fee_distributor,
            "add_amm",
        ).open_some()
        sp.transfer(sp.record(amm=params.amm, tokens=params.tokens), sp.tez(0), c_fee)

    @sp.entry_point
    def remove_amm(self, amm):
        sp.set_type(amm, sp.TAddress)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(sp.sender == self.data.remove_admin, Errors.NOT_AUTHORISED)
        sp.verify(self.data.amm_registered.contains(amm), Errors.AMM_INVALID)

        # Delete the AMM
        del self.data.amm_registered[amm]

        # Remove AMM from Voter
        c_voter = sp.contract(
            sp.TAddress,
            self.data.voter,
            "remove_amm",
        ).open_some()
        sp.transfer(amm, sp.tez(0), c_voter)

        # Remove AMM from FeeDistributor
        c_fee = sp.contract(
            sp.TAddress,
            self.data.fee_distributor,
            "remove_amm",
        ).open_some()
        sp.transfer(amm, sp.tez(0), c_fee)

    ##################
    # Utility Lambdas
    ##################

    def get_gauge_storage(self, lp_token_address):
        sp.set_type(lp_token_address, sp.TAddress)

        sp.result(
            sp.record(
                lp_token_address=lp_token_address,
                ply_address=self.data.ply_address,
                ve_address=self.data.ve_address,
                voter=self.data.voter,
                reward_rate=sp.nat(0),
                reward_per_token=sp.nat(0),
                last_update_time=sp.nat(0),
                period_finish=sp.nat(0),
                recharge_ledger=sp.big_map(l={}),
                user_reward_per_token_debt=sp.big_map(l={}),
                balances=sp.big_map(l={}),
                derived_balances=sp.big_map(l={}),
                attached_tokens=sp.big_map(l={}),
                rewards=sp.big_map(l={}),
                total_supply=sp.nat(0),
                derived_supply=sp.nat(0),
            )
        )

    def get_bribe_storage(self):
        sp.result(
            sp.record(
                uid=sp.nat(0),
                epoch_bribes=sp.big_map(l={}),
                claim_ledger=sp.big_map(l={}),
                voter=self.data.voter,
            )
        )

    @sp.entry_point
    def propose_add_admin(self, address):
        sp.set_type(address, sp.TAddress)

        # Verify that sender is add admin
        sp.verify(sp.sender == self.data.add_admin, Errors.NOT_AUTHORISED)

        self.data.proposed_add_admin = sp.some(address)

    @sp.entry_point
    def propose_remove_admin(self, address):
        sp.set_type(address, sp.TAddress)

        # Verify that sender is remove admin
        sp.verify(sp.sender == self.data.remove_admin, Errors.NOT_AUTHORISED)

        self.data.proposed_remove_admin = sp.some(address)

    @sp.entry_point
    def accept_add_admin(self):
        # Sanity checks
        sp.verify(self.data.proposed_add_admin.is_some(), Errors.NO_ADMIN_PROPOSED)
        sp.verify(sp.sender == self.data.proposed_add_admin.open_some(), Errors.NOT_AUTHORISED)

        # Update storage
        self.data.add_admin = sp.sender
        self.data.proposed_add_admin = sp.none

    @sp.entry_point
    def accept_remove_admin(self):
        # Sanity checks
        sp.verify(self.data.proposed_remove_admin.is_some(), Errors.NO_ADMIN_PROPOSED)
        sp.verify(sp.sender == self.data.proposed_remove_admin.open_some(), Errors.NOT_AUTHORISED)

        # Update storage
        self.data.remove_admin = sp.sender
        self.data.proposed_remove_admin = sp.none

    # Reject tez sent to the contract address
    @sp.entry_point
    def default(self):
        sp.failwith(Errors.CONTRACT_DOES_NOT_ACCEPT_TEZ)


if __name__ == "__main__":

    #######################
    # add_amm (valid test)
    #######################

    @sp.add_test(name="add_amm correctly deploys required contracts and updates the storage")
    def test():
        scenario = sp.test_scenario()

        voter = Voter()
        factory = CoreFactory(voter=voter.address)
        fee_dist = FeeDistributor(core_factory=factory.address)

        scenario += factory
        scenario += voter
        scenario += fee_dist

        # Set factory in voter and fee dist in factory
        scenario += voter.set_factory_and_fee_dist(factory=factory.address, fee_dist=fee_dist.address)
        scenario += factory.set_fee_distributor(fee_dist.address).run(sender=Addresses.ADMIN)

        TOKENS = sp.set(
            [
                sp.variant("fa12", Addresses.TOKEN_1),
                sp.variant("fa2", (Addresses.TOKEN_2, 0)),
            ]
        )

        # When ADMIN adds a new AMM
        scenario += factory.add_amm(
            amm=Addresses.AMM,
            lp_token_address=Addresses.LP_TOKEN,
            tokens=TOKENS,
        ).run(sender=Addresses.ADMIN)

        # Storage is updated correctly in required contracts
        scenario.verify(voter.data.amm_to_gauge_bribe.contains(Addresses.AMM))
        scenario.verify_equal(fee_dist.data.amm_to_tokens[Addresses.AMM], TOKENS)
        scenario.verify(factory.data.amm_registered[Addresses.AMM] == sp.unit)

    #########################
    # add_amm (failure test)
    #########################

    @sp.add_test(name="add_amm fails if not called by add_admin or if amm is already added")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            amm_registered=sp.big_map(
                l={
                    Addresses.AMM: sp.unit,
                },
            )
        )

        scenario += factory

        TOKENS = sp.set(
            [
                sp.variant("fa12", Addresses.TOKEN_1),
                sp.variant("fa2", (Addresses.TOKEN_2, 0)),
            ]
        )

        # When ALICE tries to call add_amm, txn fails
        scenario += factory.add_amm(
            amm=Addresses.AMM,
            lp_token_address=Addresses.LP_TOKEN,
            tokens=TOKENS,
        ).run(sender=Addresses.ALICE, valid=False, exception=Errors.NOT_AUTHORISED)

        # When ADMIN adds a new AMM
        scenario += factory.add_amm(
            amm=Addresses.AMM,
            lp_token_address=Addresses.LP_TOKEN,
            tokens=TOKENS,
        ).run(sender=Addresses.ADMIN, valid=False, exception=Errors.AMM_ALREADY_ADDED)

    ##########################
    # remove_amm (valid test)
    ##########################

    @sp.add_test(name="remove_amm correctly removes an already existing AMM")
    def test():
        scenario = sp.test_scenario()

        TOKENS = sp.set(
            [
                sp.variant("fa12", Addresses.TOKEN_1),
                sp.variant("fa2", (Addresses.TOKEN_2, 0)),
            ]
        )

        voter = Voter(
            amm_to_gauge_bribe=sp.big_map(
                l={
                    Addresses.AMM: sp.record(gauge=Addresses.CONTRACT, bribe=Addresses.CONTRACT),
                }
            ),
        )
        factory = CoreFactory(
            amm_registered=sp.big_map(
                l={
                    Addresses.AMM: sp.unit,
                }
            ),
            voter=voter.address,
        )
        fee_dist = FeeDistributor(
            core_factory=factory.address,
            amm_to_tokens=sp.big_map(
                l={
                    Addresses.AMM: TOKENS,
                }
            ),
        )

        scenario += factory
        scenario += voter
        scenario += fee_dist

        # Set factory in voter and fee dist in factory
        scenario += voter.set_factory_and_fee_dist(factory=factory.address, fee_dist=fee_dist.address)
        scenario += factory.set_fee_distributor(fee_dist.address).run(sender=Addresses.ADMIN)

        # When ADMIN removes AMM
        scenario += factory.remove_amm(Addresses.AMM).run(sender=Addresses.ADMIN)

        # Storage is updated correctly in required contracts
        scenario.verify(~voter.data.amm_to_gauge_bribe.contains(Addresses.AMM))
        scenario.verify(~fee_dist.data.amm_to_tokens.contains(Addresses.AMM))
        scenario.verify(~factory.data.amm_registered.contains(Addresses.AMM))

    ############################
    # remove_amm (failure test)
    ############################

    @sp.add_test(name="remove_amm fails if not called by remove_admin or if amm is not valid")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            amm_registered=sp.big_map(
                l={
                    Addresses.AMM: sp.unit,
                }
            ),
        )

        scenario += factory

        # When ALICE tries to remove AMM, txn fails
        scenario += factory.remove_amm(Addresses.AMM).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

        # When ADMIN removes AMM_1 (not valid), txn fails
        scenario += factory.remove_amm(Addresses.AMM_1).run(
            sender=Addresses.ADMIN,
            valid=False,
            exception=Errors.AMM_INVALID,
        )

    #################################
    # propose_add_admin (valid test)
    #################################

    @sp.add_test(name="propose_add_admin sets a new proposed add-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            add_admin=Addresses.ALICE,
        )

        scenario += factory

        # When ALICE proposed BOB as new add-admin
        scenario += factory.propose_add_admin(Addresses.BOB).run(sender=Addresses.ALICE)

        # Storage is updated correctly
        scenario.verify(factory.data.proposed_add_admin.open_some() == Addresses.BOB)

    ###################################
    # propose_add_admin (failure test)
    ###################################

    @sp.add_test(name="propose_add_admin fails if not called by add-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            add_admin=Addresses.ALICE,
        )

        scenario += factory

        # When ALICE proposed BOB as new add-admin, txn fails
        scenario += factory.propose_add_admin(Addresses.BOB).run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

    ####################################
    # propose_remove_admin (valid test)
    ####################################

    @sp.add_test(name="propose_remove_admin sets a new proposed remove-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            remove_admin=Addresses.ALICE,
        )

        scenario += factory

        # When ALICE proposed BOB as new remove-admin
        scenario += factory.propose_remove_admin(Addresses.BOB).run(sender=Addresses.ALICE)

        # Storage is updated correctly
        scenario.verify(factory.data.proposed_remove_admin.open_some() == Addresses.BOB)

    ######################################
    # propose_remove_admin (failure test)
    ######################################

    @sp.add_test(name="propose_remove_admin fails if not called by remove-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(
            remove_admin=Addresses.ALICE,
        )

        scenario += factory

        # When ALICE proposed BOB as new remove-admin, txn fails
        scenario += factory.propose_remove_admin(Addresses.BOB).run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

    ################################
    # accept_add_admin (valid test)
    ################################

    @sp.add_test(name="accept_add_admin allows proposed add-admin to take over the role")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(proposed_add_admin=sp.some(Addresses.ALICE))

        scenario += factory

        # When ALICE accepts add-admin role
        scenario += factory.accept_add_admin().run(
            sender=Addresses.ALICE,
        )

        # Storage is updated correctly
        scenario.verify(factory.data.add_admin == Addresses.ALICE)

    ##################################
    # accept_add_admin (failure test)
    ##################################

    @sp.add_test(name="accept_add_admin if not called by proposed add-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(proposed_add_admin=sp.some(Addresses.ALICE))

        scenario += factory

        # When BOB (not proposed admin) calls accept_add_admin, txn fails
        scenario += factory.accept_add_admin().run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

    @sp.add_test(name="accept_add_admin if no add-admin is proposed")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory()

        scenario += factory

        # When BOB calls accept_add_admin, txn fails
        scenario += factory.accept_add_admin().run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NO_ADMIN_PROPOSED,
        )

    ###################################
    # accept_remove_admin (valid test)
    ###################################

    @sp.add_test(name="accept_remove_admin allows proposed remove-admin to take over the role")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(proposed_remove_admin=sp.some(Addresses.ALICE))

        scenario += factory

        # When ALICE proposed BOB as new remove-admin
        scenario += factory.accept_remove_admin().run(
            sender=Addresses.ALICE,
        )

        scenario.verify(factory.data.remove_admin == Addresses.ALICE)

    #####################################
    # accept_remove_admin (failure test)
    #####################################

    @sp.add_test(name="accept_remove_admin if not called by proposed remove-admin")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory(proposed_remove_admin=sp.some(Addresses.ALICE))

        scenario += factory

        # When BOB (not proposed admin) calls accept_remove_admin, txn fails
        scenario += factory.accept_remove_admin().run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

    @sp.add_test(name="accept_remove_admin if no remove-admin is proposed")
    def test():
        scenario = sp.test_scenario()

        factory = CoreFactory()

        scenario += factory

        # When BOB calls accept_remove_admin, txn fails
        scenario += factory.accept_add_admin().run(
            sender=Addresses.BOB,
            valid=False,
            exception=Errors.NO_ADMIN_PROPOSED,
        )

    sp.add_compilation_target("core_factory", CoreFactory())
