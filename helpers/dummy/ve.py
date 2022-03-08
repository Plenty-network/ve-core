# Dummy contract to mimic on-chain reads of VoteEscrow

import smartpy as sp


class VE(sp.Contract):
    def __init__(
        self,
        powers=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TNat,
        ),
    ):
        self.init(powers=powers)

    @sp.onchain_view()
    def get_token_voting_power(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, ts=sp.TNat))

        sp.result(self.data.powers[params.token_id])

    @sp.onchain_view()
    def is_owner(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, token_id=sp.TNat))

        sp.result(sp.bool(True))
