import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
Voter = sp.io.import_script_from_url("file:voter.py").Voter
Bribe = sp.io.import_script_from_url("file:bribe.py").Bribe
Gauge = sp.io.import_script_from_url("file:gauge.py").Gauge
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


#########
# Errors
#########


class Errors:
    AMM_ALREADY_ADDED = "AMM_ALREADY_ADDED"
    AMM_INVALID = "AMM_INVALID"

    # Generic
    NOT_AUTHORISED = "NOT_AUTHORISED"


###########
# Contract
###########


class CoreFactory(sp.Contract):
    def __init__(
        self,
        admin=Addresses.ADMIN,
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
            admin=admin,
            voter=voter,
            ply_address=ply_address,
            ve_address=ve_address,
            fee_distributor=fee_distributor,
            amm_registered=amm_registered,
        )

        self.init_type(
            sp.TRecord(
                admin=sp.TAddress,
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

        sp.verify(sp.sender == self.data.admin, Errors.NOT_AUTHORISED)

        self.data.fee_distributor = address

    @sp.entry_point
    def add_amm(self, params):
        sp.set_type(params, Types.ADD_AMM_PARAMS)

        # Sanity checks
        sp.verify(sp.sender == self.data.admin, Errors.NOT_AUTHORISED)
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

        # Sanity checks
        sp.verify(sp.sender == self.data.admin, Errors.NOT_AUTHORISED)
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

    sp.add_compilation_target("core_factory", CoreFactory())
