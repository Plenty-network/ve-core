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
        locked_supply=sp.nat(0),
    ):
        self.init(
            powers=powers,
            locked_supply=locked_supply,
        )

    @sp.onchain_view()
    def get_token_voting_power(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, ts=sp.TNat))

        sp.result(self.data.powers[params.token_id])

    @sp.onchain_view()
    def is_owner(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, token_id=sp.TNat))

        sp.result(sp.bool(True))

    @sp.onchain_view()
    def get_locked_supply(self):
        sp.result(self.data.locked_supply)
