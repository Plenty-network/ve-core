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

    with sp.if_(params.value > 0):
        c = sp.contract(
            sp.TRecord(from_=sp.TAddress, to_=sp.TAddress, value=sp.TNat).layout(
                ("from_ as from", ("to_ as to", "value"))
            ),
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

    with sp.if_(params.amount > 0):
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


# VE attachment for Gauge LP boosting
def update_token_attachments(params):
    sp.set_type(
        params,
        sp.TRecord(
            owner=sp.TAddress,
            attachments=sp.TList(
                sp.TVariant(
                    add_attachment=sp.TNat,
                    remove_attachment=sp.TNat,
                )
            ),
            ve_address=sp.TAddress,
        ),
    )

    c = sp.contract(
        sp.TRecord(
            attachments=sp.TList(
                sp.TVariant(
                    add_attachment=sp.TNat,
                    remove_attachment=sp.TNat,
                )
            ),
            owner=sp.TAddress,
        ),
        params.ve_address,
        "update_attachments",
    ).open_some()

    sp.transfer(
        sp.record(attachments=params.attachments, owner=params.owner),
        sp.tez(0),
        c,
    )
