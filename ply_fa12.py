import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")

############
# Constants
############

MAX_SUPPLY = 100_000_000 * (10 ** 18)

# TODO: Update icon url
TOKEN_METADATA = {
    "decimals": "18",
    "name": "Plenty PLY",
    "symbol": "PLY",
    "icon": "ipfs://dummy",
}

# TODO: Update url
CONTRACT_METADATA = {
    "": "ipfs://dummy",
}


class FA12_Error:
    def make(s):
        return "FA1.2_" + s

    NotAdmin = make("NotAdmin")
    InsufficientBalance = make("InsufficientBalance")
    UnsafeAllowanceChange = make("UnsafeAllowanceChange")
    NotAllowed = make("NotAllowed")
    MintingDisabled = make("MintingDisabled")
    MaxSupplyMinted = make("MaxSupplyMinted")


class FA12_common:
    def normalize_metadata(self, metadata):
        meta = {}
        for key in metadata:
            meta[key] = sp.utils.bytes_of_string(metadata[key])

        return meta


class FA12_core(sp.Contract, FA12_common):
    def __init__(self, **extra_storage):
        self.init(
            balances=sp.big_map(
                tvalue=sp.TRecord(approvals=sp.TMap(sp.TAddress, sp.TNat), balance=sp.TNat),
            ),
            totalSupply=0,
            mintingDisabled=False,
            **extra_storage,
        )

    @sp.entry_point
    def transfer(self, params):
        sp.set_type(
            params,
            sp.TRecord(from_=sp.TAddress, to_=sp.TAddress, value=sp.TNat).layout(
                ("from_ as from", ("to_ as to", "value"))
            ),
        )
        sp.verify(
            (params.from_ == sp.sender) | (self.data.balances[params.from_].approvals[sp.sender] >= params.value),
            FA12_Error.NotAllowed,
        )

        self.addAddressIfNecessary(params.from_)
        self.addAddressIfNecessary(params.to_)
        sp.verify(self.data.balances[params.from_].balance >= params.value, FA12_Error.InsufficientBalance)
        self.data.balances[params.from_].balance = sp.as_nat(self.data.balances[params.from_].balance - params.value)
        self.data.balances[params.to_].balance += params.value

        with sp.if_(params.from_ != sp.sender):
            self.data.balances[params.from_].approvals[sp.sender] = sp.as_nat(
                self.data.balances[params.from_].approvals[sp.sender] - params.value
            )

    @sp.entry_point
    def approve(self, params):
        sp.set_type(params, sp.TRecord(spender=sp.TAddress, value=sp.TNat).layout(("spender", "value")))
        self.addAddressIfNecessary(sp.sender)
        alreadyApproved = self.data.balances[sp.sender].approvals.get(params.spender, 0)
        sp.verify((alreadyApproved == 0) | (params.value == 0), FA12_Error.UnsafeAllowanceChange)
        self.data.balances[sp.sender].approvals[params.spender] = params.value

    def addAddressIfNecessary(self, address):
        with sp.if_(~self.data.balances.contains(address)):
            self.data.balances[address] = sp.record(balance=0, approvals={})

    @sp.utils.view(sp.TNat)
    def getBalance(self, params):
        sp.set_type(params, sp.TAddress)
        with sp.if_(self.data.balances.contains(params)):
            sp.result(self.data.balances[params].balance)
        with sp.else_():
            sp.result(sp.nat(0))

    @sp.utils.view(sp.TNat)
    def getAllowance(self, params):
        sp.set_type(params, sp.TRecord(owner=sp.TAddress, spender=sp.TAddress))
        with sp.if_(self.data.balances.contains(params.owner)):
            sp.result(self.data.balances[params.owner].approvals.get(params.spender, 0))
        with sp.else_():
            sp.result(sp.nat(0))

    @sp.utils.view(sp.TNat)
    def getTotalSupply(self, params):
        sp.set_type(params, sp.TUnit)
        sp.result(self.data.totalSupply)

    # CHANGED: added new onchain view to assist in voter
    @sp.onchain_view()
    def get_total_supply(self):
        sp.result(self.data.totalSupply)


class FA12_mint(FA12_core):
    @sp.entry_point
    def mint(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, value=sp.TNat))
        sp.verify(self.is_administrator(sp.sender), FA12_Error.NotAdmin)
        sp.verify(~self.data.mintingDisabled, FA12_Error.MintingDisabled)
        self.addAddressIfNecessary(params.address)

        mint_val = sp.local("mint_val", params.value)
        with sp.if_((self.data.totalSupply + params.value) > MAX_SUPPLY):
            mint_val.value = sp.as_nat(MAX_SUPPLY - self.data.totalSupply)
            sp.verify(mint_value.value != 0, FA12_Error.MaxSupplyMinted)

        self.data.balances[params.address].balance += mint_val.value
        self.data.totalSupply += mint_val.value

    @sp.entry_point
    def disableMint(self):
        sp.verify(self.is_administrator(sp.sender), FA12_Error.NotAdmin)
        self.data.mintingDisabled = True


class FA12_administrator(FA12_core):
    def is_administrator(self, sender):
        return sender == self.data.administrator


class FA12_token_metadata(FA12_core):
    def set_token_metadata(self, metadata):
        self.update_initial_storage(
            token_metadata=sp.big_map(
                {0: sp.record(token_id=0, token_info=self.normalize_metadata(metadata))},
                tkey=sp.TNat,
                tvalue=sp.TRecord(token_id=sp.TNat, token_info=sp.TMap(sp.TString, sp.TBytes)),
            )
        )


class FA12_contract_metadata(FA12_core):
    def set_contract_metadata(self, metadata):
        self.update_initial_storage(metadata=sp.big_map(self.normalize_metadata(metadata)))


class FA12(
    FA12_mint,
    FA12_administrator,
    FA12_token_metadata,
    FA12_contract_metadata,
    FA12_core,
):
    def __init__(
        self,
        admin=Addresses.ADMIN,
        token_metadata=TOKEN_METADATA,
        contract_metadata=CONTRACT_METADATA,
    ):
        FA12_core.__init__(self, administrator=admin)

        self.set_token_metadata(token_metadata)
        self.set_contract_metadata(contract_metadata)


class Viewer(sp.Contract):
    def __init__(self, t):
        self.init(last=sp.none)
        self.init_type(sp.TRecord(last=sp.TOption(t)))

    @sp.entry_point
    def target(self, params):
        self.data.last = sp.some(params)


if __name__ == "__main__":

    @sp.add_test(name="Default Smartpy test suite")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("FA1.2 template - Fungible assets")

        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h1("Accounts")
        scenario.show([admin, alice, bob])

        scenario.h1("Contract")
        c1 = FA12(admin.address)

        scenario.h1("Entry points")
        scenario += c1
        scenario.h2("Admin mints a few coins")
        scenario += c1.mint(address=alice.address, value=12).run(sender=admin)
        scenario += c1.mint(address=alice.address, value=3).run(sender=admin)
        scenario += c1.mint(address=alice.address, value=3).run(sender=admin)
        scenario.h2("Alice transfers to Bob")
        scenario += c1.transfer(from_=alice.address, to_=bob.address, value=4).run(sender=alice)
        scenario.verify(c1.data.balances[alice.address].balance == 14)
        scenario.h2("Bob tries to transfer from Alice but he doesn't have her approval")
        scenario += c1.transfer(from_=alice.address, to_=bob.address, value=4).run(sender=bob, valid=False)
        scenario.h2("Alice approves Bob and Bob transfers")
        scenario += c1.approve(spender=bob.address, value=5).run(sender=alice)
        scenario += c1.transfer(from_=alice.address, to_=bob.address, value=4).run(sender=bob)
        scenario.h2("Bob tries to over-transfer from Alice")
        scenario += c1.transfer(from_=alice.address, to_=bob.address, value=4).run(sender=bob, valid=False)
        scenario.verify(c1.data.balances[alice.address].balance == 10)
        scenario += c1.transfer(from_=alice.address, to_=bob.address, value=1).run(sender=alice)

        scenario.verify(c1.data.totalSupply == 18)
        scenario.verify(c1.data.balances[alice.address].balance == 9)
        scenario.verify(c1.data.balances[bob.address].balance == 9)

        scenario.h1("Views")
        scenario.h2("Balance")
        view_balance = Viewer(sp.TNat)
        scenario += view_balance
        scenario += c1.getBalance(
            (alice.address, view_balance.typed.target),
        )
        scenario.verify_equal(view_balance.data.last, sp.some(9))

        scenario.h2("Total Supply")
        view_totalSupply = Viewer(sp.TNat)
        scenario += view_totalSupply
        scenario += c1.getTotalSupply(
            (sp.unit, view_totalSupply.typed.target),
        )
        scenario.verify_equal(view_totalSupply.data.last, sp.some(18))

        scenario.h2("Allowance")
        view_allowance = Viewer(sp.TNat)
        scenario += view_allowance
        scenario += c1.getAllowance(
            (sp.record(owner=alice.address, spender=bob.address), view_allowance.typed.target),
        )
        scenario.verify_equal(view_allowance.data.last, sp.some(1))

    sp.add_compilation_target("ply_fa12", FA12())
