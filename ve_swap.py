# This contract is a supplementary contract provided to assist in the swapping of existing PLENTY and WRAP tokens
# to PLY token at a fixed exchange rate. 50% of the PLY which is to be received by the user, will be locked for
# 3 months as a transferrable vePLY NFT, which can be used to vote on PLY emissions across gauges.

import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
FA2 = sp.io.import_script_from_url("file:helpers/tokens/fa2.py")
VoteEscrow = sp.io.import_script_from_url("file:vote_escrow.py").VoteEscrow

############
# Constants
############

DAY = 86400
WEEK = 7 * DAY

PRECISION = 10 ** 18

# Enumeration
class Token:
    PLENTY = sp.nat(0)
    WRAP = sp.nat(1)


###########
# Contract
###########


class VESwap(sp.Contract):
    def __init__(
        self,
        admin=Addresses.ADMIN,
        ply_address=Addresses.TOKEN,
        plenty_address=Addresses.TOKEN,
        wrap_address=Addresses.TOKEN,
        ve_address=Addresses.CONTRACT,
        plenty_exchange_val=sp.nat(0),
        wrap_exchange_val=sp.nat(0),
        ve_lock_period=sp.nat(12 * WEEK),
    ):
        self.init(
            admin=admin,
            ply_address=ply_address,
            plenty_address=plenty_address,
            wrap_address=wrap_address,
            ve_address=ve_address,
            plenty_exchange_val=plenty_exchange_val,
            wrap_exchange_val=wrap_exchange_val,
            ve_lock_period=ve_lock_period,
        )

        self.init_type(
            sp.TRecord(
                admin=sp.TAddress,
                ply_address=sp.TAddress,
                plenty_address=sp.TAddress,
                wrap_address=sp.TAddress,
                ve_address=sp.TAddress,
                plenty_exchange_val=sp.TNat,
                wrap_exchange_val=sp.TNat,
                ve_lock_period=sp.TNat,
            )
        )

    @sp.entry_point
    def approve_ply_ve(self, value):
        sp.set_type(value, sp.TNat)

        sp.verify(sp.sender == self.data.admin)

        c_ply = sp.contract(
            sp.TRecord(spender=sp.TAddress, value=sp.TNat),
            self.data.ply_address,
            "approve",
        ).open_some()
        sp.transfer(
            sp.record(spender=self.data.ve_address, value=value),
            sp.tez(0),
            c_ply,
        )

    @sp.entry_point
    def exchange(self, params):
        sp.set_type(params, sp.TRecord(token=sp.TNat, value=sp.TNat))

        # Calculate total PLY after exchange
        ply_converted = sp.local("ply_converted", sp.nat(0))
        with sp.if_(params.token == Token.PLENTY):
            ply_converted.value = (self.data.plenty_exchange_val * params.value) // PRECISION
        with sp.else_():
            ply_converted.value = (self.data.wrap_exchange_val * params.value) // PRECISION

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # 50% of the converted value
        ply_half = ply_converted.value // 2

        # Mint ply_half for the user
        c_ply = sp.contract(
            sp.TRecord(address=sp.TAddress, value=sp.TNat),
            self.data.ply_address,
            "mint",
        ).open_some()
        sp.transfer(sp.record(address=sp.sender, value=ply_half), sp.tez(0), c_ply)

        # Mint ply_half for the self
        c_ply = sp.contract(
            sp.TRecord(address=sp.TAddress, value=sp.TNat),
            self.data.ply_address,
            "mint",
        ).open_some()
        sp.transfer(sp.record(address=sp.self_address, value=ply_half), sp.tez(0), c_ply)

        # Give self's ply_half to user as vePLY
        c_ve = sp.contract(
            sp.TRecord(
                user_address=sp.TAddress,
                base_value=sp.TNat,
                end=sp.TNat,
            ).layout(("user_address", ("base_value", "end"))),
            self.data.ve_address,
            "create_lock",
        ).open_some()
        sp.transfer(
            sp.record(
                user_address=sp.sender,
                base_value=ply_half,
                # 6 days for week adjustment
                end=now_ + self.data.ve_lock_period + (6 * DAY),
            ),
            sp.tez(0),
            c_ve,
        )

        # Retrieve PLENTY or WRAP tokens
        with sp.if_(params.token == Token.PLENTY):
            TokenUtils.transfer_FA12(
                sp.record(
                    from_=sp.sender,
                    to_=sp.self_address,
                    value=params.value,
                    token_address=self.data.plenty_address,
                )
            )
        with sp.else_():
            TokenUtils.transfer_FA2(
                sp.record(
                    from_=sp.sender,
                    to_=sp.self_address,
                    amount=params.value,
                    token_address=self.data.wrap_address,
                    token_id=0,
                )
            )


if __name__ == "__main__":

    ###########
    # exchange
    ###########

    @sp.add_test(name="exchange correctly swaps PLENTY")
    def test():
        scenario = sp.test_scenario()

        ply = FA12(Addresses.ADMIN)
        plenty = FA12(Addresses.ADMIN)
        ve = VoteEscrow(base_token=ply.address)

        ve_swap = VESwap(
            plenty_exchange_val=5 * PRECISION,
            ply_address=ply.address,
            ve_address=ve.address,
            plenty_address=plenty.address,
        )

        scenario += ply
        scenario += ve
        scenario += plenty
        scenario += ve_swap

        # Make ve_swap a mint admin in PLY
        scenario += ply.addMintAdmin(ve_swap.address).run(sender=Addresses.ADMIN)

        # Mint PLENTY for ALICE
        scenario += plenty.mint(address=Addresses.ALICE, value=100).run(sender=Addresses.ADMIN)

        # Approve PLY spending by ve for ve_swap
        scenario += ply.approve(spender=ve.address, value=1000).run(sender=ve_swap.address)

        # Approve PLENTY spending by ve_swap for ALICE
        scenario += plenty.approve(spender=ve_swap.address, value=100).run(sender=Addresses.ALICE)

        # When ALICE exchanges her 100 PLENTY tokens for PLY
        scenario += ve_swap.exchange(token=Token.PLENTY, value=100).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(0),
        )

        # She gets 250 PLY tokens (50% of (5 * 100))
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 250)

        # She gets a vePLY NFT with a base_value of 250 PLY tokens
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 1)
        scenario.verify(ve.data.locks[1].base_value == 250)

    @sp.add_test(name="exchange correctly swaps WRAP")
    def test():
        scenario = sp.test_scenario()

        ply = FA12(Addresses.ADMIN)
        wrap = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )
        ve = VoteEscrow(base_token=ply.address)

        ve_swap = VESwap(
            wrap_exchange_val=5 * PRECISION,
            ply_address=ply.address,
            ve_address=ve.address,
            wrap_address=wrap.address,
        )

        scenario += ply
        scenario += ve
        scenario += wrap
        scenario += ve_swap

        # Make ve_swap a mint admin in PLY
        scenario += ply.addMintAdmin(ve_swap.address).run(sender=Addresses.ADMIN)

        # Mint WRAP for ALICE
        scenario += wrap.mint(
            address=Addresses.ALICE,
            amount=100,
            metadata=FA2.FA2.make_metadata(name="WRAP", decimals=8, symbol="WRAP"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # Approve PLY spending by ve for ve_swap
        scenario += ply.approve(spender=ve.address, value=1000).run(sender=ve_swap.address)

        # Make ve_swap an operator of WRAP for ALICE
        scenario += wrap.update_operators(
            [sp.variant("add_operator", sp.record(owner=Addresses.ALICE, operator=ve_swap.address, token_id=0))]
        ).run(sender=Addresses.ALICE)

        # When ALICE exchanges her 100 WRAP tokens for PLY
        scenario += ve_swap.exchange(token=Token.WRAP, value=100).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(0),
        )

        # She gets 250 PLY tokens (50% of (5 * 100))
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 250)

        # She gets a vePLY NFT with a base_value of 250 PLY tokens
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 1)
        scenario.verify(ve.data.locks[1].base_value == 250)

    sp.add_compilation_target("ve_swap", VESwap())
