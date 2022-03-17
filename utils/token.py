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


def transfer_FA2(params):
    sp.set_type(
        params,
        sp.TRecord(
            token_address=sp.TAddress,
            token_id=sp.TNat,
            from_=sp.TAddress,
            to_=sp.TAddress,
            amount=sp.TNat,
        ),
    )

    param_type = sp.TList(
        sp.TRecord(
            from_=sp.TAddress,
            txs=sp.TList(
                sp.TRecord(to_=sp.TAddress, token_id=sp.TNat, amount=sp.TNat,).layout(
                    ("to_", ("token_id", "amount")),
                ),
            ),
        ).layout(("from_", "txs"))
    )

    c = sp.contract(
        param_type,
        params.token_address,
        "transfer",
    ).open_some()

    sp.transfer(
        [
            sp.record(
                from_=params.from_, txs=[sp.record(to_=params.to_, token_id=params.token_id, amount=params.amount)]
            )
        ],
        sp.tez(0),
        c,
    )
