import smartpy as sp


def transfer_FA12(params):
    sp.set_type(
        params,
        sp.TRecord(
            token_address=sp.TAddress,
            from_=sp.TAddress,
            to_=sp.TAddress,
            value=sp.TNat,
        ),
    )

    c = sp.contract(
        sp.TRecord(from_=sp.TAddress, to_=sp.TAddress, value=sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
        params.token_address,
        "transfer",
    ).open_some()

    sp.transfer(
        sp.record(from_=params.from_, to_=params.to_, value=params.value),
        sp.tez(0),
        c,
    )
