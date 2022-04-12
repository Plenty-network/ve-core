# This contract is a supplementary contract provided to assist in the swapping of existing PLENTY and WRAP tokens
# to PLY token at a fixed exchange rate.
# 50% of the PLY is given immediately
# Remaining released over 2 years (25% each year)
# Retrieval once in 24 hours

import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
FA2 = sp.io.import_script_from_url("file:helpers/tokens/fa2.py")

############
# Constants
############

DAY = 86400

PRECISION = 10 ** 18

# Enumeration
class Token:
    PLENTY = sp.nat(0)
    WRAP = sp.nat(1)


#########
# Errors
#########


class Errors:
    SWAP_YET_TO_BEGIN = "SWAP_YET_TO_BEGIN"
    NOTHING_TO_CLAIM = "NOTHING_TO_CLAIM"
    CLAIMING_BEFORE_24_HOURS = "CLAIMING_BEFORE_24_HOURS"


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
        genesis=sp.timestamp(0),
        end=sp.timestamp(10),
        ledger=sp.big_map(
            l={},
            tkey=sp.TAddress,
            tvalue=sp.TRecord(
                balance=sp.TNat,
                release_rate=sp.TNat,
                vested=sp.TNat,
                last_claim=sp.TTimestamp,
            ).layout(("balance", ("release_rate", ("vested", "last_claim")))),
        ),
        plenty_exchange_val=sp.nat(0),
        wrap_exchange_val=sp.nat(0),
    ):
        self.init(
            admin=admin,
            ply_address=ply_address,
            plenty_address=plenty_address,
            wrap_address=wrap_address,
            genesis=genesis,
            end=end,
            ledger=ledger,
            plenty_exchange_val=plenty_exchange_val,
            wrap_exchange_val=wrap_exchange_val,
        )

        self.init_type(
            sp.TRecord(
                admin=sp.TAddress,
                ply_address=sp.TAddress,
                plenty_address=sp.TAddress,
                wrap_address=sp.TAddress,
                genesis=sp.TTimestamp,
                end=sp.TTimestamp,
                ledger=sp.TBigMap(
                    sp.TAddress,
                    sp.TRecord(
                        balance=sp.TNat,
                        release_rate=sp.TNat,
                        vested=sp.TNat,
                        last_claim=sp.TTimestamp,
                    ).layout(("balance", ("release_rate", ("vested", "last_claim")))),
                ),
                plenty_exchange_val=sp.TNat,
                wrap_exchange_val=sp.TNat,
            )
        )

    @sp.private_lambda(with_storage="read-write", wrap_call=True)
    def update_ledger(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, value=sp.TNat))

        with sp.if_(~self.data.ledger.contains(params.address)):
            self.data.ledger[params.address] = sp.record(
                balance=sp.nat(0),
                release_rate=sp.nat(0),
                vested=sp.nat(0),
                last_claim=sp.timestamp(0),
            )

        ledger_record = self.data.ledger[params.address]

        # Rate for newly added amount
        rate_ = params.value // sp.as_nat(self.data.end - self.data.genesis)

        # Vested from new amount
        vested_ = sp.min(params.value, rate_ * sp.as_nat(sp.now - self.data.genesis))

        # Vested from existing balance
        vested__ = sp.min(
            ledger_record.balance, ledger_record.release_rate * sp.as_nat(sp.now - ledger_record.last_claim)
        )

        # Update vested amount & remaining unvested balance
        ledger_record.vested += vested_ + vested__
        ledger_record.balance = sp.as_nat(ledger_record.balance - vested__) + sp.as_nat(params.value - vested_)

        # Update release rate based on remaining amount
        with sp.if_(ledger_record.balance != 0):
            ledger_record.release_rate = ledger_record.balance // sp.as_nat(self.data.end - sp.now)

        # Update last claimed
        ledger_record.last_claim = sp.now

    @sp.entry_point
    def exchange(self, params):
        sp.set_type(params, sp.TRecord(token=sp.TNat, value=sp.TNat))

        # Verify that timing is correct
        sp.verify(sp.now > self.data.genesis, Errors.SWAP_YET_TO_BEGIN)

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

        self.update_ledger(sp.record(address=sp.sender, value=ply_half))

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

    @sp.entry_point
    def claim(self):

        # Sanity checks
        sp.verify(sp.now > self.data.genesis, Errors.SWAP_YET_TO_BEGIN)
        sp.verify(self.data.ledger.contains(sp.sender), Errors.NOTHING_TO_CLAIM)
        sp.verify((sp.now - self.data.ledger[sp.sender].last_claim) > DAY, Errors.CLAIMING_BEFORE_24_HOURS)

        self.update_ledger(sp.record(address=sp.sender, value=sp.nat(0)))

        # Verify that non-zero amount is supposed to be claimed
        sp.verify(self.data.ledger[sp.sender].vested != 0, Errors.NOTHING_TO_CLAIM)

        # Mint vested tokens for claimer
        c_ply = sp.contract(
            sp.TRecord(address=sp.TAddress, value=sp.TNat),
            self.data.ply_address,
            "mint",
        ).open_some()
        sp.transfer(
            sp.record(address=sp.sender, value=self.data.ledger[sp.sender].vested),
            sp.tez(0),
            c_ply,
        )

        # Reset vested amount
        self.data.ledger[sp.sender].vested = sp.nat(0)


if __name__ == "__main__":

    ###########
    # exchange
    ###########

    @sp.add_test(name="exchange works correctly for both PLENTY and WRAP")
    def test():
        scenario = sp.test_scenario()

        ply = FA12(Addresses.ADMIN)
        plenty = FA12(Addresses.ADMIN)
        wrap = FA2.FA2(
            FA2.FA2_config(),
            sp.utils.metadata_of_url("https://example.com"),
            Addresses.ADMIN,
        )

        ve_swap = VESwap(
            plenty_exchange_val=5 * PRECISION,
            wrap_exchange_val=2 * PRECISION,
            ply_address=ply.address,
            plenty_address=plenty.address,
            wrap_address=wrap.address,
        )

        scenario += ply
        scenario += plenty
        scenario += wrap
        scenario += ve_swap

        # Make ve_swap a mint admin in PLY
        scenario += ply.addMintAdmin(ve_swap.address).run(sender=Addresses.ADMIN)

        # Mint PLENTY for ALICE
        scenario += plenty.mint(address=Addresses.ALICE, value=100).run(sender=Addresses.ADMIN)

        # Mint WRAP for ALICE
        scenario += wrap.mint(
            address=Addresses.ALICE,
            amount=100,
            metadata=FA2.FA2.make_metadata(name="WRAP", decimals=8, symbol="WRAP"),
            token_id=0,
        ).run(sender=Addresses.ADMIN)

        # Approve PLENTY spending by ve_swap for ALICE
        scenario += plenty.approve(spender=ve_swap.address, value=100).run(sender=Addresses.ALICE)

        # Make ve_swap an operator of WRAP for ALICE
        scenario += wrap.update_operators(
            [sp.variant("add_operator", sp.record(owner=Addresses.ALICE, operator=ve_swap.address, token_id=0))]
        ).run(sender=Addresses.ALICE)

        # When ALICE exchanges her 100 PLENTY tokens for PLY
        scenario += ve_swap.exchange(token=Token.PLENTY, value=100).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2),
        )

        # She gets 250 PLY tokens (50% of (5 * 100))
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 250)

        # Her ledger is updated correctly with already vested token amount
        scenario.verify(
            ve_swap.data.ledger[Addresses.ALICE]
            == sp.record(
                balance=200,
                release_rate=25,
                vested=50,
                last_claim=sp.timestamp(2),
            )
        )

        # When ALICE exchanges her 100 WRAP tokens for PLY
        scenario += ve_swap.exchange(token=Token.WRAP, value=100).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(4),
        )

        # She gets 100 PLY tokens (50% of (2 * 100)) + 250 earlier
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 350)

        # Her ledger is updated correctly with already vested token amount
        scenario.verify(
            ve_swap.data.ledger[Addresses.ALICE]
            == sp.record(
                balance=210,
                release_rate=(210 // 6),
                vested=140,
                last_claim=sp.timestamp(4),
            )
        )

        # ve_swap has correct amount of PLENTY and WRAP retrieved
        scenario.verify(plenty.data.balances[ve_swap.address].balance == 100)
        scenario.verify(wrap.data.ledger[ve_swap.address].balance == 100)

    ########
    # claim
    ########

    @sp.add_test(name="claim works correctly")
    def test():
        scenario = sp.test_scenario()

        ply = FA12(Addresses.ADMIN)

        ve_swap = VESwap(
            ply_address=ply.address,
            ledger=sp.big_map(
                l={
                    Addresses.ALICE: sp.record(
                        balance=1000000,
                        release_rate=2,
                        vested=5000,
                        last_claim=sp.timestamp(0),
                    )
                }
            ),
            end=sp.timestamp(10 * DAY),
        )

        scenario += ply
        scenario += ve_swap

        # Make ve_swap a mint admin in PLY
        scenario += ply.addMintAdmin(ve_swap.address).run(sender=Addresses.ADMIN)

        # When ALICE claims her vested tokens
        scenario += ve_swap.claim().run(sender=Addresses.ALICE, now=sp.timestamp(100000))

        # She gets correct amount of PLY
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 205000)

        # Ledger is updated correctly
        scenario.verify(
            ve_swap.data.ledger[Addresses.ALICE]
            == sp.record(
                balance=800000,
                release_rate=(800000 // (10 * DAY - 100000)),
                vested=0,
                last_claim=sp.timestamp(100000),
            )
        )

        # When ALICE claims her vested tokens after vesting period ends
        scenario += ve_swap.claim().run(sender=Addresses.ALICE, now=sp.timestamp(11 * DAY))

        # She gets all her tokens
        scenario.verify(ply.data.balances[Addresses.ALICE].balance == 1005000)

        # Ledger is updated correctly
        scenario.verify(
            ve_swap.data.ledger[Addresses.ALICE]
            == sp.record(
                balance=0,
                release_rate=(800000 // (10 * DAY - 100000)),
                vested=0,
                last_claim=sp.timestamp(11 * DAY),
            )
        )

    sp.add_compilation_target("ve_swap", VESwap())
