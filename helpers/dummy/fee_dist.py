import smartpy as sp


class FeeDist(sp.Contract):
    def __init__(self):
        self.init(claim_val=sp.none)

    @sp.entry_point
    def claim(self, params):
        sp.set_type(
            params,
            sp.TRecord(
                token_id=sp.TNat,
                owner=sp.TAddress,
                amm=sp.TAddress,
                epoch_vote_shares=sp.TList(sp.TRecord(epoch=sp.TNat, share=sp.TNat)),
            ).layout(("token_id", ("owner", ("amm", "epoch_vote_shares")))),
        )

        self.data.claim_val = sp.some(params)
