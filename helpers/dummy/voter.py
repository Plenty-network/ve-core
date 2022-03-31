import smartpy as sp


class Voter(sp.Contract):
    def __init__(self, epoch=sp.nat(0), end=sp.timestamp(0)):
        self.init(epoch=epoch, end=end)

    @sp.onchain_view()
    def get_current_epoch(self):
        sp.result((self.data.epoch, self.data.end))

    @sp.onchain_view()
    def get_epoch_end(self, param):
        sp.set_type(param, sp.TNat)
        sp.result(sp.as_nat(self.data.end - sp.timestamp(0)))
