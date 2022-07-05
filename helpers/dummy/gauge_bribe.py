import smartpy as sp

# Dummy contract to test calls to Bribe and Gauge contracts from within the Voter contract


class GaugeBribe(sp.Contract):
    def __init__(self):
        self.init(claim_val=sp.none, return_val=sp.none, recharge_val=sp.none)

    @sp.entry_point
    def claim(self, params):
        sp.set_type(
            params,
            sp.TRecord(
                token_id=sp.TNat,
                owner=sp.TAddress,
                epoch=sp.TNat,
                bribe_id=sp.TNat,
                vote_share=sp.TNat,
            ).layout(("token_id", ("owner", ("epoch", ("bribe_id", "vote_share"))))),
        )

        self.data.claim_val = sp.some(params)

    @sp.entry_point
    def return_bribe(self, params):
        sp.set_type(params, sp.TRecord(epoch=sp.TNat, bribe_id=sp.TNat))

        self.data.return_val = sp.some(params)

    @sp.entry_point
    def recharge(self, params):
        sp.set_type(params, sp.TRecord(amount=sp.TNat, epoch=sp.TNat))

        self.data.recharge_val = sp.some(params)
