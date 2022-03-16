import smartpy as sp


class Ply(sp.Contract):
    def __init__(self, total_supply=sp.nat(0)):
        self.init(total_supply=total_supply)

    @sp.onchain_view()
    def get_total_supply(self):
        sp.result(self.data.total_supply)
