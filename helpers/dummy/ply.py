import smartpy as sp


class Ply(sp.Contract):
    def __init__(self, total_supply=sp.nat(0)):
        self.init(total_supply=total_supply)

    @sp.entry_point
    def mint(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, value=sp.TNat))

        pass

    @sp.onchain_view()
    def get_total_supply(self):
        sp.result(self.data.total_supply)
