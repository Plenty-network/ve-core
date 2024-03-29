import smartpy as sp

Errors = sp.io.import_script_from_url("file:utils/errors.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
Constants = sp.io.import_script_from_url("file:utils/constants.py")
Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
Voter = sp.io.import_script_from_url("file:helpers/dummy/voter.py").Voter
Utils = sp.io.import_script_from_url("file:utils/misc.py")
SVG = sp.io.import_script_from_url("file:utils/svg.py")

############
# Constants
############

DAY = Constants.DAY
WEEK = Constants.WEEK
YEAR = Constants.YEAR
MAX_TIME = Constants.MAX_TIME
DECIMALS = Constants.DECIMALS
SLOPE_MULTIPLIER = Constants.SLOPE_MULTIPLIER

########
# Types
########


class Types:
    LOCK = sp.TRecord(
        base_value=sp.TNat,
        end=sp.TNat,
    ).layout(("base_value", "end"))

    POINT = sp.TRecord(
        slope=sp.TNat,
        bias=sp.TNat,
        ts=sp.TNat,
    ).layout(("slope", ("bias", "ts")))

    TRANSFER_PARAMS = sp.TList(
        sp.TRecord(
            from_=sp.TAddress,
            txs=sp.TList(
                sp.TRecord(to_=sp.TAddress, token_id=sp.TNat, amount=sp.TNat,).layout(
                    ("to_", ("token_id", "amount")),
                ),
            ),
        ).layout(("from_", "txs"))
    )

    OPERATOR_PARAMS = sp.TRecord(
        owner=sp.TAddress,
        operator=sp.TAddress,
        token_id=sp.TNat,
    ).layout(("owner", ("operator", "token_id")))

    BALANCE_OF_PARAMS = sp.TRecord(
        requests=sp.TList(sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id"))),
        callback=sp.TContract(
            sp.TList(
                sp.TRecord(
                    request=sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id")),
                    balance=sp.TNat,
                ).layout(("request", "balance"))
            )
        ),
    ).layout(("requests", "callback"))

    CREATE_LOCK_PARAMS = sp.TRecord(
        user_address=sp.TAddress,
        base_value=sp.TNat,
        end=sp.TNat,
    ).layout(("user_address", ("base_value", "end")))

    CLAIM_LEDGER_KEY = sp.TRecord(
        token_id=sp.TNat,
        epoch=sp.TNat,
    ).layout(("token_id", "epoch"))

    # Enumeration for voting power readers
    CURRENT = sp.nat(0)
    WHOLE_WEEK = sp.nat(1)


# TZIP-12 specified errors for FA2 standard
class FA2_Errors:
    FA2_TOKEN_UNDEFINED = "FA2_TOKEN_UNDEFINED"
    FA2_NOT_OPERATOR = "FA2_NOT_OPERATOR"
    FA2_INSUFFICIENT_BALANCE = "FA2_INSUFFICIENT_BALANCE"
    FA2_NOT_OWNER = "FA2_NOT_OWNER"
    FA2_INVALID_AMOUNT = "FA2_INVALID_AMOUNT"


###########
# Contract
###########


class VoteEscrow(sp.Contract):
    def __init__(
        self,
        # FA2 standard storage items
        ledger=sp.big_map(
            l={},
            tkey=sp.TPair(sp.TAddress, sp.TNat),
            tvalue=sp.TNat,
        ),
        operators=sp.big_map(
            l={},
            tkey=sp.TRecord(
                token_id=sp.TNat,
                owner=sp.TAddress,
                operator=sp.TAddress,
            ),
            tvalue=sp.TUnit,
        ),
        # Vote-escrow storage items
        locks=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=Types.LOCK,
        ),
        attached=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TAddress,
        ),
        token_checkpoints=sp.big_map(
            l={},
            tkey=sp.TPair(sp.TNat, sp.TNat),
            tvalue=Types.POINT,
        ),
        num_token_checkpoints=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TNat,
        ),
        gc_index=sp.nat(0),
        global_checkpoints=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=Types.POINT,
        ),
        slope_changes=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TNat,
        ),
        epoch_inflation=sp.big_map(
            l={},
            tkey=sp.TNat,
            tvalue=sp.TNat,
        ),
        claim_ledger=sp.big_map(
            l={},
            tkey=Types.CLAIM_LEDGER_KEY,
            tvalue=sp.TUnit,
        ),
        voter=Addresses.CONTRACT,
        base_token=Addresses.TOKEN,
        locked_supply=sp.nat(0),
    ):

        METADATA = {
            "name": "PLY Vote Escrow",
            "version": "1.0.0",
            "description": "This contract allows locking up PLY as a veNFT",
            "interfaces": ["TZIP-012", "TZIP-016", "TZIP-021"],
            "views": [self.token_metadata],
        }

        # Smartpy's helper to create the metadata json
        self.init_metadata("metadata", METADATA)

        self.init(
            ledger=ledger,
            operators=operators,
            metadata=sp.utils.metadata_of_url("ipfs://QmXnSs9njQtEEauevAyhw5vKqEinFmieqXBwHxPKvXMKDA"),
            locks=locks,
            attached=attached,
            uid=sp.nat(0),
            token_checkpoints=token_checkpoints,
            num_token_checkpoints=num_token_checkpoints,
            gc_index=gc_index,
            global_checkpoints=global_checkpoints,
            slope_changes=slope_changes,
            epoch_inflation=epoch_inflation,
            claim_ledger=claim_ledger,
            voter=voter,
            base_token=base_token,
            locked_supply=locked_supply,
        )

        self.init_type(
            sp.TRecord(
                # FA2 specific
                ledger=sp.TBigMap(sp.TPair(sp.TAddress, sp.TNat), sp.TNat),
                operators=sp.TBigMap(
                    sp.TRecord(
                        token_id=sp.TNat,
                        owner=sp.TAddress,
                        operator=sp.TAddress,
                    ),
                    sp.TUnit,
                ),
                metadata=sp.TBigMap(sp.TString, sp.TBytes),
                # VE specific
                locks=sp.TBigMap(sp.TNat, Types.LOCK),
                attached=sp.TBigMap(sp.TNat, sp.TAddress),
                uid=sp.TNat,
                token_checkpoints=sp.TBigMap(sp.TPair(sp.TNat, sp.TNat), Types.POINT),
                num_token_checkpoints=sp.TBigMap(sp.TNat, sp.TNat),
                gc_index=sp.TNat,
                global_checkpoints=sp.TBigMap(sp.TNat, Types.POINT),
                slope_changes=sp.TBigMap(sp.TNat, sp.TNat),
                epoch_inflation=sp.TBigMap(sp.TNat, sp.TNat),
                claim_ledger=sp.TBigMap(Types.CLAIM_LEDGER_KEY, sp.TUnit),
                voter=sp.TAddress,
                base_token=sp.TAddress,
                locked_supply=sp.TNat,
            )
        )

    # Default tzip-12 specified transfer for NFTs
    @sp.entry_point
    def transfer(self, params):
        sp.set_type(params, Types.TRANSFER_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        with sp.for_("transfer", params) as transfer:
            current_from = transfer.from_
            with sp.for_("tx", transfer.txs) as tx:

                # Verify sender
                sp.verify(
                    (sp.sender == current_from)
                    | self.data.operators.contains(
                        sp.record(owner=current_from, operator=sp.sender, token_id=tx.token_id)
                    ),
                    FA2_Errors.FA2_NOT_OPERATOR,
                )

                # Verify that lock is not attached
                sp.verify(~self.data.attached.contains(tx.token_id), Errors.LOCK_IS_ATTACHED)

                # Verify that the token id belongs to a lock
                sp.verify(self.data.locks.contains(tx.token_id), FA2_Errors.FA2_TOKEN_UNDEFINED)

                # Each token is unique, so transfer amount would always be 1
                with sp.if_(tx.amount >= 1):
                    # Verify that the address has sufficient balance for transfer
                    sp.verify(
                        self.data.ledger[(current_from, tx.token_id)] >= tx.amount,
                        FA2_Errors.FA2_INSUFFICIENT_BALANCE,
                    )

                    # Make transfer
                    self.data.ledger[(current_from, tx.token_id)] = sp.as_nat(
                        self.data.ledger[(current_from, tx.token_id)] - tx.amount
                    )

                    balance = self.data.ledger.get((tx.to_, tx.token_id), 0)
                    self.data.ledger[(tx.to_, tx.token_id)] = balance + tx.amount
                with sp.else_():
                    pass

    # Default tzip-12 specified balance_of
    @sp.entry_point
    def balance_of(self, params):
        sp.set_type(params, Types.BALANCE_OF_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Response object
        response = sp.local("response", [])

        with sp.for_("request", params.requests) as request:
            sp.verify(self.data.locks.contains(request.token_id), FA2_Errors.FA2_TOKEN_UNDEFINED)

            balance = self.data.ledger.get((request.owner, request.token_id), 0)

            response.value.push(sp.record(request=request, balance=balance))

        sp.transfer(response.value, sp.tez(0), params.callback)

    # Default FA2 specified update_operators
    @sp.entry_point
    def update_operators(self, params):
        sp.set_type(
            params,
            sp.TList(
                sp.TVariant(
                    add_operator=Types.OPERATOR_PARAMS,
                    remove_operator=Types.OPERATOR_PARAMS,
                )
            ),
        )

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        with sp.for_("update", params) as update:
            with update.match_cases() as arg:
                with arg.match("add_operator") as upd:
                    sp.verify(
                        upd.owner == sp.sender,
                        FA2_Errors.FA2_NOT_OWNER,
                    )
                    self.data.operators[upd] = sp.unit
                with arg.match("remove_operator") as upd:
                    sp.verify(
                        upd.owner == sp.sender,
                        FA2_Errors.FA2_NOT_OWNER,
                    )
                    del self.data.operators[upd]

    @sp.entry_point
    def update_attachments(self, params):
        sp.set_type(
            params,
            sp.TRecord(
                attachments=sp.TList(
                    sp.TVariant(
                        add_attachment=sp.TNat,
                        remove_attachment=sp.TNat,
                    )
                ),
                owner=sp.TAddress,
            ),
        )

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        with sp.for_("attachment", params.attachments) as attachment:
            with attachment.match_cases() as arg:
                with arg.match("add_attachment") as token_id:
                    # Sanity checks
                    sp.verify(~self.data.attached.contains(token_id), Errors.LOCK_IS_ATTACHED)
                    sp.verify(self.data.ledger.get((params.owner, token_id), 0) == 1, Errors.NOT_AUTHORISED)
                    sp.verify(
                        (sp.sender == params.owner)
                        | self.data.operators.contains(
                            sp.record(owner=params.owner, operator=sp.sender, token_id=token_id)
                        ),
                        Errors.NOT_AUTHORISED,
                    )

                    # Attach token/lock
                    self.data.attached[token_id] = sp.sender
                with arg.match("remove_attachment") as token_id:
                    # Sanity checks
                    sp.verify(self.data.ledger.get((params.owner, token_id), 0) == 1, Errors.NOT_AUTHORISED)
                    sp.verify(sp.sender == self.data.attached[token_id], Errors.NOT_AUTHORISED)
                    sp.verify(
                        (sp.sender == params.owner)
                        | self.data.operators.contains(
                            sp.record(owner=params.owner, operator=sp.sender, token_id=token_id)
                        ),
                        Errors.NOT_AUTHORISED,
                    )
                    with sp.if_(self.data.attached.contains(token_id)):
                        # Detach token/lock
                        del self.data.attached[token_id]

    @sp.private_lambda(with_storage="read-write", wrap_call=True)
    def record_global_checkpoint(self, params):
        sp.set_type(
            params,
            sp.TRecord(old_cp=Types.POINT, new_cp=Types.POINT, prev_end=sp.TNat, new_end=sp.TNat),
        )

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        with sp.if_(self.data.gc_index == 0):
            # First entry check
            self.data.slope_changes[params.new_end] = params.new_cp.slope
            self.data.global_checkpoints[self.data.gc_index + 1] = sp.record(
                bias=params.new_cp.bias,
                slope=params.new_cp.slope,
                ts=now_,
            )
            self.data.gc_index += 1
        with sp.else_():
            global_checkpoint = sp.compute(self.data.global_checkpoints[self.data.gc_index])

            # Calculate current global bias and slope
            c_bias = sp.local("c_bias", global_checkpoint.bias)
            c_slope = sp.local("c_slope", global_checkpoint.slope)

            n_ts = sp.local("n_ts", ((global_checkpoint.ts + WEEK) // WEEK) * WEEK)
            c_ts = sp.local("c_ts", global_checkpoint.ts)

            with sp.if_(n_ts.value < now_):
                with sp.while_((n_ts.value < now_) & (c_bias.value != 0)):
                    d_ts = sp.as_nat(n_ts.value - c_ts.value)
                    c_bias.value = sp.as_nat(c_bias.value - (d_ts * c_slope.value) // SLOPE_MULTIPLIER)

                    # Update slope
                    c_slope.value = sp.as_nat(c_slope.value - self.data.slope_changes.get(n_ts.value, 0))

                    # Update n_ts
                    c_ts.value = n_ts.value
                    n_ts.value = n_ts.value + WEEK

            with sp.if_(c_bias.value != 0):
                d_ts = sp.as_nat(now_ - c_ts.value)
                c_bias.value = sp.as_nat(c_bias.value - (d_ts * c_slope.value) // SLOPE_MULTIPLIER)

            # Adjust out old checkpoint off the global bias/slope & slope_changes
            with sp.if_(params.old_cp.slope != 0):
                bias_ = sp.as_nat(
                    params.old_cp.bias - (params.old_cp.slope * sp.as_nat(now_ - params.old_cp.ts)) // SLOPE_MULTIPLIER
                )
                c_bias.value = sp.as_nat(c_bias.value - bias_)
                c_slope.value = sp.as_nat(c_slope.value - params.old_cp.slope)

            with sp.if_(params.prev_end != 0):
                self.data.slope_changes[params.prev_end] = sp.as_nat(
                    self.data.slope_changes[params.prev_end] - params.old_cp.slope
                )

            # Add new checkpoint to global bias/slope & slope_changes
            c_bias.value += params.new_cp.bias
            c_slope.value += params.new_cp.slope

            change = self.data.slope_changes.get(params.new_end, 0)
            self.data.slope_changes[params.new_end] = change + params.new_cp.slope

            # Insert new global checkpoint
            self.data.global_checkpoints[self.data.gc_index + 1] = sp.record(
                bias=c_bias.value,
                slope=c_slope.value,
                ts=now_,
            )
            self.data.gc_index += 1

    @sp.entry_point
    def create_lock(self, params):
        sp.set_type(params, Types.CREATE_LOCK_PARAMS)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        # Find a timestamp rounded off to nearest week
        ts = sp.compute((params.end // WEEK) * WEEK)

        # Lock period in seconds
        d_ts = sp.compute(sp.as_nat(ts - now_, Errors.INVALID_LOCK_TIME))

        # Verify that calculated timestamp falls in the correct range
        sp.verify((d_ts >= WEEK) & (d_ts <= MAX_TIME), Errors.INVALID_LOCK_TIME)

        # Calculate slope & bias for linearly decreasing voting power
        bias = sp.compute((params.base_value * d_ts) // MAX_TIME)
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Update uid and mint associated NFT for params.user_address
        self.data.uid += 1

        # Store as local variable to keep on stack
        uid = sp.compute(self.data.uid)

        # Update balance in the FA2 ledger
        self.data.ledger[(params.user_address, uid)] = sp.nat(1)

        # Register a lock
        self.data.locks[uid] = sp.record(
            base_value=params.base_value,
            end=ts,
        )

        # Record token checkpoint
        self.data.num_token_checkpoints[uid] = 1
        self.data.token_checkpoints[(uid, 1)] = sp.record(
            slope=slope,
            bias=bias,
            ts=now_,
        )

        # Record global checkpoint for lock creation
        old_cp = sp.record(bias=0, slope=0, ts=0)
        new_cp = self.data.token_checkpoints[(uid, 1)]
        self.record_global_checkpoint(
            sp.record(
                old_cp=old_cp,
                new_cp=new_cp,
                prev_end=0,
                new_end=self.data.locks[uid].end,
            )
        )

        # Retrieve base token to self address
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.sender,
                to_=sp.self_address,
                value=params.base_value,
                token_address=self.data.base_token,
            )
        )

        # Increase locked supply
        self.data.locked_supply += params.base_value

    @sp.entry_point
    def withdraw(self, token_id):
        sp.set_type(token_id, sp.TNat)

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Verify that the lock with supplied token-id exists
        sp.verify(self.data.locks.contains(token_id), Errors.LOCK_DOES_NOT_EXIST)

        # Store as local variable to keep on stack
        lock = sp.compute(self.data.locks[token_id])

        # Sanity checks
        sp.verify(self.data.ledger.get((sp.sender, token_id), 0) == 1, Errors.NOT_AUTHORISED)
        sp.verify(now_ > lock.end, Errors.LOCK_YET_TO_EXPIRE)
        sp.verify(~self.data.attached.contains(token_id), Errors.LOCK_IS_ATTACHED)

        # Transfer underlying PLY
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.self_address,
                to_=sp.sender,
                value=lock.base_value,
                token_address=self.data.base_token,
            )
        )

        # Decrease locked supply
        self.data.locked_supply = sp.as_nat(self.data.locked_supply - lock.base_value)

        # Remove associated token
        self.data.ledger[(sp.sender, token_id)] = 0

        # Delete the lock
        del self.data.locks[token_id]

    @sp.entry_point
    def increase_lock_value(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, value=sp.TNat).layout(("token_id", "value")))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        # Verify that lock with token-id exists
        sp.verify(self.data.locks.contains(params.token_id), Errors.LOCK_DOES_NOT_EXIST)

        # Store as local variable to keep on stack
        lock = sp.compute(self.data.locks[params.token_id])

        # Sanity checks
        sp.verify(
            (sp.sender == sp.self_address) | (self.data.ledger.get((sp.sender, params.token_id), 0) == 1),
            Errors.NOT_AUTHORISED,
        )
        sp.verify((sp.sender == sp.self_address) | (lock.end > now_), Errors.LOCK_HAS_EXPIRED)
        sp.verify(params.value > 0, Errors.INVALID_INCREASE_VALUE)

        # Modify base value of the lock
        self.data.locks[params.token_id].base_value += params.value

        # Only add a checkpoint if the lock has not already expired
        with sp.if_(lock.end > now_):
            # Fetch current updated bias
            index_ = sp.compute(self.data.num_token_checkpoints[params.token_id])
            last_tc = sp.compute(self.data.token_checkpoints[(params.token_id, index_)])
            bias_ = sp.as_nat(last_tc.bias - (last_tc.slope * sp.as_nat(now_ - last_tc.ts)) // SLOPE_MULTIPLIER)

            # Time left in lock
            d_ts = sp.compute(sp.as_nat(lock.end - now_))

            # Increase in bias
            i_bias = (params.value * d_ts) // MAX_TIME

            # New bias & slope
            n_bias = sp.compute(bias_ + i_bias)
            n_slope = (n_bias * SLOPE_MULTIPLIER) // d_ts

            # Record new token checkpoint
            self.data.token_checkpoints[(params.token_id, index_ + 1)] = sp.record(
                slope=n_slope,
                bias=n_bias,
                ts=now_,
            )

            # Updated later to prevent access error
            self.data.num_token_checkpoints[params.token_id] += 1

            # Store as local variable to keep on stack
            index__ = sp.compute(self.data.num_token_checkpoints[params.token_id])

            # Record global checkpoint
            old_cp = self.data.token_checkpoints[(params.token_id, sp.as_nat(index__ - 1))]
            new_cp = self.data.token_checkpoints[(params.token_id, index__)]
            self.record_global_checkpoint(
                sp.record(
                    old_cp=old_cp,
                    new_cp=new_cp,
                    prev_end=lock.end,
                    new_end=lock.end,
                )
            )

        with sp.if_(sp.sender != sp.self_address):
            # Retrieve the increased value in base token
            TokenUtils.transfer_FA12(
                sp.record(
                    from_=sp.sender,
                    to_=sp.self_address,
                    value=params.value,
                    token_address=self.data.base_token,
                )
            )

            # Increase locked supply
            self.data.locked_supply += params.value

    @sp.entry_point
    def increase_lock_end(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, end=sp.TNat).layout(("token_id", "end")))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # nat version of block timestamp
        now_ = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        # Find a timestamp rounded off to nearest week
        ts = sp.compute((params.end // WEEK) * WEEK)

        # Lock period in seconds
        d_ts = sp.compute(sp.as_nat(ts - now_, Errors.INVALID_LOCK_TIME))

        # Verify that lock with token-id exists
        sp.verify(self.data.locks.contains(params.token_id), Errors.LOCK_DOES_NOT_EXIST)

        # Store as local variable to keep on stack
        lock = sp.compute(self.data.locks[params.token_id])

        # Sanity checks
        sp.verify(self.data.ledger[(sp.sender, params.token_id)] == 1, Errors.NOT_AUTHORISED)
        sp.verify(lock.end > now_, Errors.LOCK_HAS_EXPIRED)
        sp.verify((ts > lock.end) & (d_ts <= MAX_TIME), Errors.INVALID_INCREASE_END_TIMESTAMP)

        # Calculate new bias and slope
        bias = sp.compute((lock.base_value * d_ts) // MAX_TIME)
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Update lock end
        self.data.locks[params.token_id].end = ts

        # Update checkpoint index
        self.data.num_token_checkpoints[params.token_id] += 1

        # Store as local variable to keep on stack
        index_ = sp.compute(self.data.num_token_checkpoints[params.token_id])

        # Add new checkpoint for token
        self.data.token_checkpoints[(params.token_id, index_)] = sp.record(
            slope=slope,
            bias=bias,
            ts=now_,
        )

        # Record global checkpoint
        old_cp = self.data.token_checkpoints[(params.token_id, sp.as_nat(index_ - 1))]
        new_cp = self.data.token_checkpoints[(params.token_id, index_)]
        self.record_global_checkpoint(
            sp.record(
                old_cp=old_cp,
                new_cp=new_cp,
                prev_end=lock.end,
                new_end=ts,
            )
        )

    # NOTE: called once during origination sequence
    @sp.entry_point
    def set_voter(self, address):
        sp.set_type(address, sp.TAddress)
        with sp.if_(self.data.voter == Addresses.CONTRACT):
            self.data.voter = address

    @sp.entry_point
    def add_inflation(self, params):
        sp.set_type(params, sp.TRecord(epoch=sp.TNat, value=sp.TNat).layout(("epoch", "value")))

        # Verify that the sender is the Voter contract
        sp.verify(sp.sender == self.data.voter, Errors.NOT_AUTHORISED)

        # Update inflation value for the epoch
        self.data.epoch_inflation[params.epoch] = params.value

        # Increase locked supply
        self.data.locked_supply += params.value

    @sp.entry_point
    def claim_inflation(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, epochs=sp.TList(sp.TNat)).layout(("token_id", "epochs")))

        # Reject tez
        sp.verify(sp.amount == sp.tez(0), Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ)

        # Sanity checks
        sp.verify(self.data.ledger.get((sp.sender, params.token_id), 0) == 1, Errors.NOT_AUTHORISED)

        # Local variable to store through the inflation share
        inflation_share = sp.local("inflation_share", sp.nat(0))

        # Iterate through requested epochs
        with sp.for_("epochs", params.epochs) as epoch:
            sp.verify(
                ~self.data.claim_ledger.contains(sp.record(token_id=params.token_id, epoch=epoch)),
                Errors.ALREADY_CLAIMED_INFLATION,
            )
            sp.verify(self.data.epoch_inflation.contains(epoch), Errors.INFLATION_NOT_ADDED)

            # Get epoch ending from Voter
            epoch_end = sp.view("get_epoch_end", self.data.voter, epoch, sp.TNat).open_some(Errors.INVALID_VIEW)

            ts_ = sp.compute(sp.as_nat(epoch_end - WEEK))

            # Get token voting power at the beginning of epoch
            token_vp = sp.view(
                "get_token_voting_power",
                sp.self_address,
                sp.record(token_id=params.token_id, ts=ts_, time=Types.WHOLE_WEEK),
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            # Get total voting power at the beginning of epoch
            total_vp = sp.view(
                "get_total_voting_power",
                sp.self_address,
                sp.record(ts=ts_, time=Types.WHOLE_WEEK),
                sp.TNat,
            ).open_some(Errors.INVALID_VIEW)

            # Calculate inflation share for the token/lock
            inflation_share.value += (token_vp * self.data.epoch_inflation[epoch]) // total_vp

            # Mark as claimed
            self.data.claim_ledger[sp.record(token_id=params.token_id, epoch=epoch)] = sp.unit

        # Increase lock value using the inflation share
        c = sp.self_entry_point("increase_lock_value")
        sp.transfer(sp.record(token_id=params.token_id, value=inflation_share.value), sp.tez(0), c)

    @sp.onchain_view()
    def get_token_voting_power(self, params):
        sp.set_type(
            params,
            sp.TRecord(
                token_id=sp.TNat,
                ts=sp.TNat,
                time=sp.TNat,
            ),
        )

        # Find a operating timestamp based on user supplied time type in parameters
        factor = sp.local("factor", WEEK)
        with sp.if_(params.time == Types.CURRENT):
            factor.value = 1
        ts = sp.compute((params.ts // factor.value) * factor.value)

        # Sanity checks
        sp.verify((params.time == Types.CURRENT) | (params.time == Types.WHOLE_WEEK), Errors.INVALID_TIME)
        sp.verify(self.data.locks.contains(params.token_id), Errors.LOCK_DOES_NOT_EXIST)
        sp.verify(ts >= self.data.token_checkpoints[(params.token_id, 1)].ts, Errors.TOO_EARLY_TIMESTAMP)

        # Store as local variables to keep on stack
        index_ = sp.compute(self.data.num_token_checkpoints[params.token_id])
        last_checkpoint = sp.compute(self.data.token_checkpoints[(params.token_id, index_)])

        with sp.if_(ts >= last_checkpoint.ts):
            i_bias = last_checkpoint.bias
            slope = last_checkpoint.slope
            f_bias = sp.compute(i_bias - (sp.as_nat(ts - last_checkpoint.ts) * slope) // SLOPE_MULTIPLIER)
            with sp.if_(f_bias < 0):
                sp.result(sp.nat(0))
            with sp.else_():
                sp.result(sp.as_nat(f_bias))
        with sp.else_():
            high = sp.local("high", sp.as_nat(index_ - 2))
            low = sp.local("low", sp.nat(0))
            mid = sp.local("mid", sp.nat(0))

            with sp.while_(
                (low.value < high.value) & (self.data.token_checkpoints[(params.token_id, mid.value + 1)].ts != ts)
            ):
                mid.value = (low.value + high.value + 1) // 2
                with sp.if_(self.data.token_checkpoints[(params.token_id, mid.value + 1)].ts < ts):
                    low.value = mid.value
                with sp.else_():
                    high.value = sp.as_nat(mid.value - 1)

            with sp.if_(self.data.token_checkpoints[(params.token_id, mid.value + 1)].ts == ts):
                sp.result(self.data.token_checkpoints[(params.token_id, mid.value + 1)].bias)
            with sp.else_():
                checkpoint = sp.compute(self.data.token_checkpoints[(params.token_id, low.value + 1)])
                bias = checkpoint.bias
                slope = checkpoint.slope
                d_ts = ts - checkpoint.ts
                sp.result(sp.as_nat(bias - (sp.as_nat(d_ts) * slope) // SLOPE_MULTIPLIER))

    @sp.onchain_view()
    def get_total_voting_power(self, params):
        sp.set_type(
            params,
            sp.TRecord(
                ts=sp.TNat,
                time=sp.TNat,
            ),
        )

        # Find a operating timestamp based on user supplied time type in parameters
        factor = sp.local("factor", WEEK)
        with sp.if_(params.time == Types.CURRENT):
            factor.value = 1
        ts = sp.compute((params.ts // factor.value) * factor.value)

        # Sanity check
        sp.verify((params.time == Types.CURRENT) | (params.time == Types.WHOLE_WEEK), Errors.INVALID_TIME)
        sp.verify(ts >= self.data.global_checkpoints[1].ts, Errors.TOO_EARLY_TIMESTAMP)

        # Checkpoint closest to requested ts
        c_cp = sp.local("c_cp", self.data.global_checkpoints[self.data.gc_index])

        # Find the closest checkpoint using binary search
        with sp.if_(ts < c_cp.value.ts):
            high = sp.local("high", sp.as_nat(self.data.gc_index - 2))
            low = sp.local("low", sp.nat(0))
            mid = sp.local("mid", sp.nat(0))

            with sp.while_((low.value < high.value) & (self.data.global_checkpoints[mid.value + 1].ts != ts)):
                mid.value = (low.value + high.value + 1) // 2
                with sp.if_(self.data.global_checkpoints[mid.value + 1].ts < ts):
                    low.value = mid.value
                with sp.else_():
                    high.value = sp.as_nat(mid.value - 1)
            with sp.if_(self.data.global_checkpoints[mid.value + 1].ts == ts):
                c_cp.value = self.data.global_checkpoints[mid.value + 1]
            with sp.else_():
                c_cp.value = self.data.global_checkpoints[low.value + 1]

        # Calculate the linear drop across remaining seconds
        c_bias = sp.local("c_bias", c_cp.value.bias)
        c_slope = sp.local("c_slope", c_cp.value.slope)

        n_ts = sp.local("n_ts", ((c_cp.value.ts + WEEK) // WEEK) * WEEK)
        c_ts = sp.local("c_ts", c_cp.value.ts)

        with sp.if_(n_ts.value < ts):
            # Can go upto ts here, since ts is a whole WEEK
            with sp.while_((n_ts.value < ts) & (c_bias.value != 0)):
                d_ts = sp.as_nat(n_ts.value - c_ts.value)
                c_bias.value = sp.as_nat(c_bias.value - (d_ts * c_slope.value) // SLOPE_MULTIPLIER)

                # Update slope
                c_slope.value = sp.as_nat(c_slope.value - self.data.slope_changes.get(n_ts.value, 0))

                # Update n_ts
                c_ts.value = n_ts.value
                n_ts.value = n_ts.value + WEEK

        with sp.if_(c_bias.value != 0):
            d_ts = sp.as_nat(ts - c_ts.value)
            c_bias.value = sp.as_nat(c_bias.value - (d_ts * c_slope.value) // SLOPE_MULTIPLIER)

        sp.result(c_bias.value)

    @sp.onchain_view()
    def is_owner(self, params):
        sp.set_type(params, sp.TRecord(address=sp.TAddress, token_id=sp.TNat))

        balance = self.data.ledger.get((params.address, params.token_id), 0)

        with sp.if_(balance != 1):
            sp.result(sp.bool(False))
        with sp.else_():
            sp.result(sp.bool(True))

    @sp.onchain_view()
    def get_locked_supply(self):
        sp.result(self.data.locked_supply)

    @sp.offchain_view(pure=False)
    def token_metadata(self, token_id):
        sp.set_type(token_id, sp.TNat)

        # Verify that the lock with supplied token-id exists
        sp.verify(self.data.locks.contains(token_id), Errors.LOCK_DOES_NOT_EXIST)

        # Current timestamp as nat
        ts = sp.compute(sp.as_nat(sp.now - sp.timestamp(0)))

        lock = sp.compute(self.data.locks[token_id])
        bytes_of_nat = sp.compute(Utils.bytes_of_nat)

        voting_power = sp.local("voting_power", 0)
        expiry = sp.local("expiry", 0)

        with sp.if_(lock.end > ts):
            # Number of days left to expire
            expiry.value = sp.as_nat(lock.end - ts) // 86400

        index_ = self.data.num_token_checkpoints[token_id]
        last_checkpoint = sp.compute(self.data.token_checkpoints[(token_id, index_)])

        # Find the current voting power. `ts` is bound to be >= the timestamp of last checkpoint.
        i_bias = last_checkpoint.bias
        slope = last_checkpoint.slope
        f_bias = sp.compute(i_bias - (sp.as_nat(ts - last_checkpoint.ts) * slope) // SLOPE_MULTIPLIER)
        with sp.if_(f_bias < 0):
            voting_power.value = 0
        with sp.else_():
            voting_power.value = sp.as_nat(f_bias)

        # Segments of the SVG data URI
        segments = sp.local("segments", SVG.DATA_SEGMENTS.GOLD)

        # Select the correct set of segments based on days to expire to generate the SVG
        # >= 3 years = gold
        # >= 2 years = violet
        # >= 6 months = red
        # < 6 months = green
        # expired = grey
        with sp.if_((expiry.value >= 728) & (expiry.value < 1092)):
            segments.value = SVG.DATA_SEGMENTS.VIOLET
        with sp.else_():
            with sp.if_((expiry.value >= 180) & (expiry.value < 728)):
                segments.value = SVG.DATA_SEGMENTS.RED
            with sp.else_():
                with sp.if_(expiry.value < 180):
                    segments.value = SVG.DATA_SEGMENTS.GREEN
                with sp.if_(lock.end < ts):
                    segments.value = SVG.DATA_SEGMENTS.GREY

        get_floating_point = sp.compute(Utils.get_floating_point)

        f_locked_ply = get_floating_point(lock.base_value)
        f_voting_power = get_floating_point(voting_power.value)

        b_locked_ply = sp.local("b_locked_ply", bytes_of_nat(sp.fst(f_locked_ply)))
        b_voting_power = sp.local("b_voting_power", bytes_of_nat(sp.fst(f_voting_power)))

        with sp.if_(sp.snd(f_locked_ply) > 0):
            b_locked_ply.value += sp.utils.bytes_of_string(".") + bytes_of_nat(sp.snd(f_locked_ply))
        with sp.if_(sp.snd(f_voting_power) > 0):
            b_voting_power.value += sp.utils.bytes_of_string(".") + bytes_of_nat(sp.snd(f_voting_power))

        # Build the SVG data URI
        image_uri = sp.compute(
            SVG.build_svg(
                sp.record(
                    segments=segments.value,
                    token_id=bytes_of_nat(token_id),
                    locked_ply=b_locked_ply.value,
                    voting_power=b_voting_power.value,
                    expiry=bytes_of_nat(expiry.value),
                )
            )
        )

        # Create a TZIP-21 compliant token-info
        metadata_tzip_21 = {
            "name": sp.utils.bytes_of_string("Plenty veNFT"),
            "symbol": sp.utils.bytes_of_string("veNFT"),
            "decimals": sp.utils.bytes_of_string("0"),
            "thumbnailUri": image_uri,
            "artifactUri": image_uri,
            "displayUri": image_uri,
            "ttl": bytes_of_nat(sp.nat(900)),
        }

        # Return the TZIP-16 compliant metadata
        sp.result(
            sp.record(
                token_id=token_id,
                token_info=metadata_tzip_21,
            )
        )


if __name__ == "__main__":

    ###############
    # Test Helpers
    ###############
    NOW = int(0.5 * DAY)
    DECIMALS = 10**18

    ###########################
    # create_lock (valid test)
    ###########################

    @sp.add_test(name="create_lock works correctly for locks shorter than maxtime")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()
        ve = VoteEscrow(base_token=ply_token.address)

        scenario += ply_token
        scenario += ve

        # Mint and approve tokens for ALICE
        scenario += ply_token.mint(
            address=Addresses.ALICE,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)
        scenario += ply_token.approve(
            spender=ve.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ALICE)

        # When ALICE create a lock for 1000 PLY tokens
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=1000 * DECIMALS,
            end=2 * WEEK + 2 * DAY,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(NOW))

        # NFT is minted correctly
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 1)

        # Lock is registered correctly
        scenario.verify(ve.data.locks[1] == sp.record(base_value=1000 * DECIMALS, end=2 * WEEK))

        # Predicted bias and slope
        d_ts = 2 * WEEK - NOW
        bias = (1000 * DECIMALS * d_ts) // MAX_TIME
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Correct checkpoint is created for the token
        scenario.verify(ve.data.token_checkpoints[(1, 1)] == sp.record(bias=bias, slope=slope, ts=NOW))

        # Global checkpoint is recorded correctly
        scenario.verify(ve.data.global_checkpoints[1] == sp.record(bias=bias, slope=slope, ts=NOW))
        scenario.verify(ve.data.slope_changes[2 * WEEK] == slope)

        # Tokens get lock in ve
        scenario.verify(ply_token.data.balances[ve.address].balance == 1000 * DECIMALS)

        # Locked supply is updated correctly
        scenario.verify(ve.data.locked_supply == 1000 * DECIMALS)

    @sp.add_test(name="create_lock works correctly for locks of maxtime")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()
        ve = VoteEscrow(base_token=ply_token.address)

        scenario += ply_token
        scenario += ve

        # Mint and approve tokens for ALICE
        scenario += ply_token.mint(
            address=Addresses.ALICE,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)
        scenario += ply_token.approve(
            spender=ve.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ALICE)

        # When ALICE create a lock for 1000 PLY tokens for maxtime
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=1000 * DECIMALS,
            end=MAX_TIME + 2 * DAY,  # + 2 days to test rounding down
        ).run(
            sender=Addresses.ALICE, now=sp.timestamp(0)
        )  # ts taken as 0 to get maximum lock duration

        # NFT is minted correctly
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 1)

        # Lock is registered correctly
        scenario.verify(ve.data.locks[1] == sp.record(base_value=1000 * DECIMALS, end=MAX_TIME))

        # Predicted bias and slope
        d_ts = MAX_TIME
        bias = 1000 * DECIMALS
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Correct checkpoint is created for the token
        scenario.verify(ve.data.token_checkpoints[(1, 1)] == sp.record(bias=bias, slope=slope, ts=0))

        # Global checkpoint is recorded correctly
        scenario.verify(ve.data.global_checkpoints[1] == sp.record(bias=bias, slope=slope, ts=0))
        scenario.verify(ve.data.slope_changes[MAX_TIME] == slope)

        # Tokens get locked in ve
        scenario.verify(ply_token.data.balances[ve.address].balance == 1000 * DECIMALS)

        # Locked supply is updated correctly
        scenario.verify(ve.data.locked_supply == 1000 * DECIMALS)

    #############################
    # create_lock (failure test)
    #############################

    @sp.add_test(name="create_lock fails if tez is sent to the entrypoint")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow()
        scenario += ve

        # When ALICE sends tez to the entrypoint, the txn fails
        scenario += ve.create_lock(user_address=Addresses.ALICE, base_value=1000 * DECIMALS, end=2 * YEAR,).run(
            sender=Addresses.ALICE,
            amount=sp.tez(1),
            now=sp.timestamp(3 * YEAR),
            valid=False,
            exception=Errors.ENTRYPOINT_DOES_NOT_ACCEPT_TEZ,
        )

    @sp.add_test(name="create_lock fails for invalid lock time")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow()
        scenario += ve

        # When ALICE create a lock with ending before current time, the txn fails
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=1000 * DECIMALS,
            end=2 * YEAR,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(3 * YEAR), valid=False, exception=Errors.INVALID_LOCK_TIME)

        # When ALICE create a lock with lock time greater than max-time, the txn fails
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=1000 * DECIMALS,
            end=MAX_TIME + 2 * WEEK,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(0), valid=False, exception=Errors.INVALID_LOCK_TIME)

        # When ALICE create a lock with lock time less than a week (4 days here), the txn fails
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=1000 * DECIMALS,
            end=8 * DAY,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(3 * DAY), valid=False, exception=Errors.INVALID_LOCK_TIME)

    ########################
    # withdraw (valid test)
    ########################

    @sp.add_test(name="withdraw allows unlocking of vePLY")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()

        # Setup a lock with base value of 100 PLY and ending in 7 days
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100 * DECIMALS, end=7 * DAY)}),
            base_token=ply_token.address,
            locked_supply=100 * DECIMALS,
        )

        scenario += ply_token
        scenario += ve

        # Mint PLY for ve
        scenario += ply_token.mint(address=ve.address, value=100 * DECIMALS).run(sender=Addresses.ADMIN)

        # When ALICE withdraws from her lock under token_id 1
        scenario += ve.withdraw(1).run(sender=Addresses.ALICE, now=sp.timestamp(NOW + 7 * DAY))

        # Storage is updated correctly
        scenario.verify(~ve.data.locks.contains(1))
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 0)

        # ALICE gets back the underlying PLY
        scenario.verify(ply_token.data.balances[Addresses.ALICE].balance == 100 * DECIMALS)

        # Locked supply is updated correctly
        scenario.verify(ve.data.locked_supply == 0)

    ##########################
    # withdraw (failure test)
    ##########################

    @sp.add_test(name="withdraw fails if lock does not exist or does not belong to the user")
    def test():
        scenario = sp.test_scenario()

        # Setup a lock with base value of 100 PLY and ending in 7 days for ALICE
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
        )

        scenario += ve

        # When ALICE tries withdrawing from a lock belonging to invalid token-id 2, txn fails
        scenario += ve.withdraw(2).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 7 * DAY),
            valid=False,
            exception=Errors.LOCK_DOES_NOT_EXIST,
        )

        # When BOB tries withdrawing from a lock that does not belong to him, txn fails
        scenario += ve.withdraw(1).run(
            sender=Addresses.BOB,
            now=sp.timestamp(NOW + 7 * DAY),
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

    @sp.add_test(name="withdraw fails if lock is yet to expire")
    def test():
        scenario = sp.test_scenario()

        # Setup a lock with base value of 100 PLY and ending in 7 days for ALICE
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
        )

        scenario += ve

        # When ALICE tries withdrawing before the lock expires, txn fails
        scenario += ve.withdraw(1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 6 * DAY),
            valid=False,
            exception=Errors.LOCK_YET_TO_EXPIRE,
        )

    @sp.add_test(name="withdraw fails if lock is attached")
    def test():
        scenario = sp.test_scenario()

        # Setup a lock with base value of 100 PLY and ending in 7 days for ALICE
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
            attached=sp.big_map(l={1: Addresses.CONTRACT}),
        )

        scenario += ve

        # When ALICE tries withdrawing before the lock expires, txn fails
        scenario += ve.withdraw(1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 8 * DAY),
            valid=False,
            exception=Errors.LOCK_IS_ATTACHED,
        )

    ###################################
    # increase_lock_value (valid test)
    ###################################

    @sp.add_test(name="increase_lock_value allows increasing locked PLY value without changing end time")
    def test():
        scenario = sp.test_scenario()

        # Initial values for simulated storage
        base_value_ = 1000 * DECIMALS
        end_ = 4 * WEEK
        d_ts = end_ - NOW
        bias_ = (1000 * DECIMALS * d_ts) // MAX_TIME
        slope_ = (bias_ * SLOPE_MULTIPLIER) // d_ts

        ply_token = FA12()
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=base_value_,
                        end=end_,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                },
            ),
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                }
            ),
            slope_changes=sp.big_map(l={end_: slope_}),
            gc_index=sp.nat(1),
            base_token=ply_token.address,
        )

        scenario += ply_token
        scenario += ve

        # Mint and approve tokens for ALICE
        scenario += ply_token.mint(
            address=Addresses.ALICE,
            value=100 * DECIMALS,
        ).run(sender=Addresses.ADMIN)
        scenario += ply_token.approve(
            spender=ve.address,
            value=100 * DECIMALS,
        ).run(sender=Addresses.ALICE)

        # Taken randomly - the timestamp at which ALICE increases lock value
        increase_ts = 9 * DAY
        increase_val = 100 * DECIMALS

        # When ALICE adds 100 PLY to the lock for token id 1
        scenario += ve.increase_lock_value(token_id=1, value=100 * DECIMALS).run(
            sender=Addresses.ALICE, now=sp.timestamp(increase_ts)
        )

        # Lock's base value is updated correctly
        scenario.verify(ve.data.locks[1] == sp.record(base_value=1100 * DECIMALS, end=end_))

        # Predicted bias and slope
        i_bias = (increase_val * (end_ - increase_ts)) // MAX_TIME
        bias = (bias_ - (slope_ * (increase_ts - NOW)) // SLOPE_MULTIPLIER) + i_bias
        slope = (bias * SLOPE_MULTIPLIER) // (end_ - increase_ts)

        # Correct checkpoint is added
        scenario.verify(ve.data.num_token_checkpoints[1] == 2)
        scenario.verify(ve.data.token_checkpoints[(1, 2)] == sp.record(bias=bias, slope=slope, ts=increase_ts))

        # Global checkpoint is recorded correctly
        scenario.verify(ve.data.global_checkpoints[2] == sp.record(bias=bias, slope=slope, ts=increase_ts))
        scenario.verify(ve.data.slope_changes[end_] == slope)

        # Tokens get locked in ve
        scenario.verify(ply_token.data.balances[ve.address].balance == 100 * DECIMALS)

        # Locked supply is updated correctly
        scenario.verify(ve.data.locked_supply == 100 * DECIMALS)

    #####################################
    # increase_lock_value (failure test)
    #####################################

    # NOTE: invalid lock and ownership failures are same as 'withdraw'

    @sp.add_test(name="increase_lock_value fails if lock is expired or invalid increase value is provided")
    def test():
        scenario = sp.test_scenario()

        # Setup a lock with base value of 100 PLY and ending in 7 days for ALICE
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
        )

        scenario += ve

        # When ALICE tries increasing lock value after the lock expires, txn fails
        scenario += ve.increase_lock_value(token_id=1, value=100 * DECIMALS).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 8 * DAY),
            valid=False,
            exception=Errors.LOCK_HAS_EXPIRED,
        )

        # When ALICE provides invalid increase value, txn fails
        scenario += ve.increase_lock_value(token_id=1, value=0).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 5 * DAY),
            valid=False,
            exception=Errors.INVALID_INCREASE_VALUE,
        )

    #################################
    # increase_lock_end (valid test)
    #################################

    @sp.add_test(name="increase_lock_end correctly makes smaller than maxtime increase")
    def test():
        scenario = sp.test_scenario()

        # Initial values for simulated storage
        base_value_ = 1000 * DECIMALS
        end_ = 4 * WEEK
        d_ts = end_ - NOW
        bias_ = (1000 * DECIMALS * d_ts) // MAX_TIME
        slope_ = (bias_ * SLOPE_MULTIPLIER) // d_ts

        ply_token = FA12()
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=base_value_,
                        end=end_,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                },
            ),
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                }
            ),
            slope_changes=sp.big_map(l={end_: slope_}),
            gc_index=sp.nat(1),
            base_token=ply_token.address,
        )

        scenario += ply_token
        scenario += ve

        # Taken randomly - the timestamp at which ALICE increases lock end
        increase_ts = 9 * DAY

        # New lock ending
        n_end = 10 * WEEK

        # When ALICE increases the lock end
        scenario += ve.increase_lock_end(token_id=1, end=n_end).run(
            sender=Addresses.ALICE, now=sp.timestamp(increase_ts)
        )

        # Predicted bias and slope for new checkpoint
        bias = (base_value_ * (n_end - increase_ts)) // MAX_TIME
        slope = (bias * SLOPE_MULTIPLIER) // (n_end - increase_ts)

        # Lock is modified correctly
        scenario.verify(ve.data.locks[1].end == n_end)

        # Global checkpoint is recorded correctly
        scenario.verify(ve.data.global_checkpoints[2] == sp.record(bias=bias, slope=slope, ts=increase_ts))
        scenario.verify(ve.data.slope_changes[end_] == 0)
        scenario.verify(ve.data.slope_changes[n_end] == slope)

        # Correct checkpoint is added
        scenario.verify(ve.data.token_checkpoints[(1, 2)] == sp.record(bias=bias, slope=slope, ts=increase_ts))

    @sp.add_test(name="increase_lock_end correctly makes maxtime increase")
    def test():
        scenario = sp.test_scenario()

        # Initial values for simulated storage
        base_value_ = 1000 * DECIMALS
        end_ = 4 * WEEK
        d_ts = end_ - NOW
        bias_ = (1000 * DECIMALS * d_ts) // MAX_TIME
        slope_ = (bias_ * SLOPE_MULTIPLIER) // d_ts

        ply_token = FA12()
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=base_value_,
                        end=end_,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                },
            ),
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=bias_,
                        slope=slope_,
                        ts=NOW,
                    )
                }
            ),
            slope_changes=sp.big_map(l={end_: slope_}),
            gc_index=sp.nat(1),
            base_token=ply_token.address,
        )

        scenario += ply_token
        scenario += ve

        # Taken randomly - the timestamp at which ALICE increases lock end
        increase_ts = 1 * WEEK

        # New lock ending
        n_end = 1 * WEEK + MAX_TIME

        # When ALICE increases the lock end
        scenario += ve.increase_lock_end(token_id=1, end=n_end).run(
            sender=Addresses.ALICE, now=sp.timestamp(increase_ts)
        )

        # Predicted bias and slope for new checkpoint
        bias = base_value_
        slope = (bias * SLOPE_MULTIPLIER) // (n_end - increase_ts)

        # Lock is modified correctly
        scenario.verify(ve.data.locks[1].end == n_end)

        # Global checkpoint is recorded correctly
        scenario.verify(ve.data.global_checkpoints[2] == sp.record(bias=bias, slope=slope, ts=increase_ts))
        scenario.verify(ve.data.slope_changes[end_] == 0)
        scenario.verify(ve.data.slope_changes[n_end] == slope)

        # Correct checkpoint is added
        scenario.verify(ve.data.token_checkpoints[(1, 2)] == sp.record(bias=bias, slope=slope, ts=increase_ts))

    #################################
    # increase_lock_end (failure test)
    #################################

    # NOTE: only the new lock time failure test is relevant. Other failure statements are already verified in
    # previous tests.

    @sp.add_test(name="increase_lock_end fails if new lock time is not within bounds")
    def test():
        scenario = sp.test_scenario()

        # Setup a lock with base value of 100 PLY and ending in 7 days for ALICE
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
        )

        scenario += ve

        # When ALICE tries increasing lock end by less than a week, txn fails
        scenario += ve.increase_lock_end(token_id=1, end=9 * DAY).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 5 * DAY),
            valid=False,
            exception=Errors.INVALID_INCREASE_END_TIMESTAMP,
        )

        # When ALICE tries increasing lock by more than 4 years, txn fails
        scenario += ve.increase_lock_end(token_id=1, end=MAX_TIME + YEAR).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(NOW + 5 * DAY),
            valid=False,
            exception=Errors.INVALID_INCREASE_END_TIMESTAMP,
        )

    ############################
    # record_global_checkpoint
    ############################

    @sp.add_test(name="record_global_checkpoint works correctly for overlapping locks")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()
        ve = VoteEscrow(base_token=ply_token.address)

        scenario += ply_token
        scenario += ve

        # Mint and approve tokens for ALICE
        scenario += ply_token.mint(
            address=Addresses.ALICE,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)
        scenario += ply_token.approve(
            spender=ve.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ALICE)

        # Max-time lockup values
        lock_1_bias = 200 * DECIMALS
        lock_1_slope = (lock_1_bias * SLOPE_MULTIPLIER) // MAX_TIME

        # 1/4th of Max-time lockup values
        lock_2_bias = 100 * DECIMALS
        lock_2_slope = (lock_2_bias * SLOPE_MULTIPLIER) // YEAR

        # ALICE creates first lock (for 4 Years) at timestamp - 0 (Genesis for tests)
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=200 * DECIMALS,
            end=MAX_TIME,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(0))

        # ALICE creates second lock (for 1 Year) at 2 Years after first lock
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=400 * DECIMALS,
            end=(2 * YEAR) + (YEAR),
        ).run(sender=Addresses.ALICE, now=sp.timestamp(2 * YEAR))

        # ALICE increase lock end for 1 lock to an additional YEAR, 3 Days after 2nd lock ends
        scenario += ve.increase_lock_end(token_id=1, end=MAX_TIME + YEAR).run(
            sender=Addresses.ALICE, now=sp.timestamp(3 * YEAR + 3 * DAY)
        )

        # This is required since due to limited precision, a small (usually order of 1/10^17) global bias
        # is left out when calculating decrease in bias over time.
        def precision_verify(a, b, p):
            scenario.verify((a >= (b - p)) & (a <= (b + p)))

        # Global checkpoints are recorded correctly
        scenario.verify(ve.data.global_checkpoints[1].bias == lock_1_bias)
        scenario.verify(ve.data.global_checkpoints[1].slope == lock_1_slope)
        scenario.verify(ve.data.global_checkpoints[1].ts == 0)

        precision_verify(
            ve.data.global_checkpoints[2].bias,
            lock_1_bias - (lock_1_slope * 2 * YEAR) // SLOPE_MULTIPLIER + lock_2_bias,
            100,
        )
        scenario.verify(ve.data.global_checkpoints[2].slope == lock_1_slope + lock_2_slope)
        scenario.verify(ve.data.global_checkpoints[2].ts == 2 * YEAR)

        bias_ = (lock_1_bias * (2 * YEAR - 3 * DAY)) // MAX_TIME
        slope_ = (bias_ * SLOPE_MULTIPLIER) // (2 * YEAR - 3 * DAY)

        precision_verify(ve.data.global_checkpoints[3].bias, bias_, 100)
        scenario.verify(ve.data.global_checkpoints[3].slope == slope_)
        scenario.verify(ve.data.global_checkpoints[3].ts == 3 * YEAR + 3 * DAY)

        # Slope changes are recorded correctly
        scenario.verify(ve.data.slope_changes[MAX_TIME] == 0)
        scenario.verify(ve.data.slope_changes[3 * YEAR] == lock_2_slope)
        scenario.verify(ve.data.slope_changes[5 * YEAR] == slope_)

    @sp.add_test(name="record_global_checkpoint works correctly for non overlapping locks")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()
        ve = VoteEscrow(base_token=ply_token.address)

        scenario += ply_token
        scenario += ve

        # Mint and approve tokens for ALICE
        scenario += ply_token.mint(
            address=Addresses.ALICE,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ADMIN)
        scenario += ply_token.approve(
            spender=ve.address,
            value=1000 * DECIMALS,
        ).run(sender=Addresses.ALICE)

        # 2 Year lock up
        lock_1_bias = 200 * DECIMALS
        lock_1_slope = (lock_1_bias * SLOPE_MULTIPLIER) // (2 * YEAR)

        # 1 Year lock up
        lock_2_bias = (400 * DECIMALS * (YEAR - 3 * DAY)) // MAX_TIME
        lock_2_slope = (lock_2_bias * SLOPE_MULTIPLIER) // (YEAR - 3 * DAY)

        # ALICE creates first lock at timestamp - 0 (Genesis for tests)
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=400 * DECIMALS,
            end=2 * YEAR,
        ).run(sender=Addresses.ALICE, now=sp.timestamp(0))

        # ALICE creates second lock (for 1 Year) 3 days after first lock expires
        scenario += ve.create_lock(
            user_address=Addresses.ALICE,
            base_value=400 * DECIMALS,
            end=(2 * YEAR) + (3 * DAY) + (YEAR),
        ).run(sender=Addresses.ALICE, now=sp.timestamp(2 * YEAR + 3 * DAY))

        # This is required since due to limited precision, a small (usually order of 1/10^17) global bias
        # is left out when calculating decrease in bias over time.
        def precision_verify(a, b, p):
            scenario.verify((a >= (b - p)) & (a <= (b + p)))

        # Global checkpoints are recorded correctly
        scenario.verify(ve.data.global_checkpoints[1].bias == lock_1_bias)
        scenario.verify(ve.data.global_checkpoints[1].slope == lock_1_slope)
        scenario.verify(ve.data.global_checkpoints[1].ts == 0)

        precision_verify(
            ve.data.global_checkpoints[2].bias,
            lock_2_bias,
            100,
        )
        scenario.verify(ve.data.global_checkpoints[2].slope == lock_2_slope)
        scenario.verify(ve.data.global_checkpoints[2].ts == (2 * YEAR + 3 * DAY))

        # Slope changes are recorded correctly
        scenario.verify(ve.data.slope_changes[2 * YEAR] == lock_1_slope)
        scenario.verify(ve.data.slope_changes[3 * YEAR] == lock_2_slope)

    #####################
    # update_attachments
    #####################

    @sp.add_test(name="update_attachments works correctly")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1, (Addresses.BOB, 2): 1}),
            operators=sp.big_map(
                l={
                    sp.record(
                        token_id=1,
                        owner=Addresses.ALICE,
                        operator=Addresses.CONTRACT,
                    ): sp.unit
                },
            ),
        )

        scenario += ve

        # When CONTRACT (operator for ALICE's token) attaches token/lock 1
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("add_attachment", 1)]).run(
            sender=Addresses.CONTRACT
        )

        # and BOB attaches his own token/lock 2
        scenario += ve.update_attachments(owner=Addresses.BOB, attachments=[sp.variant("add_attachment", 2)]).run(
            sender=Addresses.BOB
        )

        # Storage is updated correctly
        scenario.verify(ve.data.attached[1] == Addresses.CONTRACT)
        scenario.verify(ve.data.attached[2] == Addresses.BOB)

        # When JOHN (not operator for ALICE's token) tries changing attachment status of token/lock 1, txn fails
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("remove_attachment", 1)]).run(
            sender=Addresses.JOHN,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

        # When ALICE (did not attach her own token) herself tries changing attachment status of token/lock 1, txn fails
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("remove_attachment", 1)]).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

        # When CONTRACT removes ALICE's attachment
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("remove_attachment", 1)]).run(
            sender=Addresses.CONTRACT
        )

        # Storage is updated correctly
        scenario.verify(~ve.data.attached.contains(1))

    #########################
    # get_token_voting_power
    #########################

    @sp.add_test(name="get_token_voting_power works for one checkpoint")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            # Only 1 checkpoint
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Predicted voting power (bias) for ts = 10 * DAY
        ts = 10 * DAY
        bias = (1000 * DECIMALS) - (5 * DAY) * 2

        # Correct voting power is received for 10 * DAY
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts, time=Types.CURRENT)) == bias)

    @sp.add_test(name="get_token_voting_power works for two checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 2,
                },
            ),
            # Only 2 checkpoints
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Predicted voting power (bias_1) for ts = 15 * DAY
        ts_1 = 14 * DAY  # rounded ts
        bias_1 = (1000 * DECIMALS) - (5 * DAY) * 6

        # Predicted voting power (bias_2) for ts = 19 * DAY
        ts_2 = 19 * DAY
        bias_2 = (800 * DECIMALS) - (2 * DAY) * 2

        # Correct voting powers are received
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_1, time=Types.WHOLE_WEEK)) == bias_1)
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_2, time=Types.CURRENT)) == bias_2)

    @sp.add_test(name="get_token_voting_power works for three checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 2,
                },
            ),
            # Only 3 checkpoints
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                    (1, 3): sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Predicted voting power (bias_1) for ts = 19 * DAY
        ts_1 = 19 * DAY
        bias_1 = (800 * DECIMALS) - (2 * DAY) * 2

        # Predicted voting power (bias_2) for ts = 22 * DAY
        ts_2 = 21 * DAY  # rounded ts
        bias_2 = (800 * DECIMALS) - (2 * DAY) * 4

        # Correct voting powers are received
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_1, time=Types.CURRENT)) == bias_1)
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_2, time=Types.WHOLE_WEEK)) == bias_2)

    @sp.add_test(name="get_token_voting_power works for odd number of checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 5,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                    (1, 3): sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    (1, 4): sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    (1, 5): sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Predicted voting power (bias_1) for ts = 23 * DAY
        ts_1 = 21 * DAY  # rounded ts
        bias_1 = (800 * DECIMALS) - (4 * DAY) * 2

        # Predicted voting power (bias_2) for ts = 29 * DAY
        ts_2 = 28 * DAY  # rounded ts
        bias_2 = (700 * DECIMALS) - (4 * DAY) * 3

        # Predicted voting power for unrounded current time at ts = 29 * DAY
        bias_unrounded = (700 * DECIMALS) - (5 * DAY) * 3

        # Correct voting power is received for 23 * DAY
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_1, time=Types.WHOLE_WEEK)) == bias_1)

        # Correct voting power is received for 29 * DAY
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_2, time=Types.WHOLE_WEEK)) == bias_2)

        # Correct voting power is received for 29 * DAY (unrounded)
        scenario.verify(
            ve.get_token_voting_power(sp.record(token_id=1, ts=29 * DAY, time=Types.CURRENT)) == bias_unrounded
        )

    @sp.add_test(name="get_token_voting_power works for even number of checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 6,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                    (1, 3): sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    (1, 4): sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    (1, 5): sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                    (1, 6): sp.record(
                        bias=500 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=40 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Predicted voting power (bias_1) for ts = 29 * DAY
        ts_1 = 28 * DAY  # rounded ts
        bias_1 = (700 * DECIMALS) - (4 * DAY) * 3

        # Predicted voting power (bias_2) for ts = 38 * DAY
        ts_2 = 35 * DAY  # rounded ts
        bias_2 = (1000 * DECIMALS) - (5 * DAY) * 6

        # Predicted voting power for unrounded current time at ts = 37 * DAY
        bias_unrounded = (900 * DECIMALS) - (1 * DAY) * 5

        # Correct voting power is received for 29 * DAY
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_1, time=Types.WHOLE_WEEK)) == bias_1)

        # Correct voting power is received for 38 * DAY
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=ts_2, time=Types.WHOLE_WEEK)) == bias_2)

        # Correct voting power is received for 37 * DAY (unrounded)
        scenario.verify(
            ve.get_token_voting_power(sp.record(token_id=1, ts=37 * DAY, time=Types.CURRENT)) == bias_unrounded
        )

    @sp.add_test(name="get_token_voting_power works for timestamp that is within the checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 6,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                    (1, 3): sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    (1, 4): sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    (1, 5): sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=35 * DAY,  # Whole week timestamp
                    ),
                    (1, 6): sp.record(
                        bias=500 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=40 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Correct voting power is received for 36 * DAY
        scenario.verify(
            ve.get_token_voting_power(sp.record(token_id=1, ts=36 * DAY, time=Types.WHOLE_WEEK)) == 900 * DECIMALS
        )

    @sp.add_test(name="get_token_voting_power works for timestamps after expiry")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            locks=sp.big_map(
                l={
                    1: sp.record(
                        # Random values. Inconsequential for this test.
                        base_value=1000,
                        end=4 * YEAR,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 6,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=8 * DAY,
                    ),
                    (1, 2): sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=17 * DAY,
                    ),
                    (1, 3): sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    (1, 4): sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    (1, 5): sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                    (1, 6): sp.record(
                        bias=500 * DECIMALS,
                        slope=2 * DECIMALS * SLOPE_MULTIPLIER,  # High slope to ease out testing
                        ts=40 * DAY,
                    ),
                },
            ),
        )

        scenario += ve

        # Correct voting power is received after expiry - i.e 0
        scenario.verify(ve.get_token_voting_power(sp.record(token_id=1, ts=44 * DAY, time=Types.WHOLE_WEEK)) == 0)

    #########################
    # get_total_voting_power
    #########################

    @sp.add_test(name="get_total_voting_power works for one checkpoint")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=1,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Predicted global voting power (bias) for ts = 23 * DAY (21 * DAY if rounded)
        bias = (1000 * DECIMALS) - (4 * DAY * 5) - (WEEK * 3) - (WEEK * 2)

        # Correct voting power is received for ts = 23 * DAY (rounded)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=23 * DAY, time=Types.WHOLE_WEEK)) == bias)

    @sp.add_test(name="get_total_voting_power works for two checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=2,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=22 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Predicted global voting power (bias_1) for ts = 23
        ts_1 = 21 * DAY  # rounded ts
        bias_1 = (1000 * DECIMALS) - (4 * DAY * 5) - (WEEK * 3) - (WEEK * 2)

        # Predicted global voting power (bias_2) for ts = 23
        ts_2 = 23 * DAY
        bias_2 = (800 * DECIMALS) - (2 * DAY)

        # Correct voting powers are received
        scenario.verify(ve.get_total_voting_power(sp.record(ts=ts_1, time=Types.WHOLE_WEEK)) == bias_1)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=ts_2, time=Types.CURRENT)) == bias_2)

    @sp.add_test(name="get_total_voting_power works for three checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=3,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=22 * DAY,
                    ),
                    3: sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Predicted global voting power (bias_1) for ts = 23
        ts_1 = 21 * DAY  # rounded ts
        bias_1 = (1000 * DECIMALS) - (4 * DAY * 5) - (WEEK * 3) - (WEEK * 2)

        # Predicted global voting power (bias_2) for ts = 23
        ts_2 = 23 * DAY
        bias_2 = (800 * DECIMALS) - (2 * DAY)

        # Correct voting powers are received
        scenario.verify(ve.get_total_voting_power(sp.record(ts=ts_1, time=Types.WHOLE_WEEK)) == bias_1)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=ts_2, time=Types.CURRENT)) == bias_2)

    @sp.add_test(name="get_total_voting_power works for odd number of global checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=5,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=22 * DAY,
                    ),
                    3: sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    4: sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    5: sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Predicted global voting power (bias_1) for ts = 23 * DAY (21 * DAY if rounded)
        bias_1 = (1000 * DECIMALS) - (4 * DAY * 5) - (WEEK * 3) - (WEEK * 2)

        # Predicted global voting power (bias_2) for ts = 38 * DAY (35 * DAY if rounded)
        bias_2 = (1000 * DECIMALS) - (5 * DAY * 6)

        # Predicted global voting power for ts = 38 * DAY (unrounded)
        bias_unrounded = (900 * DECIMALS) - (2 * DAY * 5)

        # Correct voting powers are received
        scenario.verify(ve.get_total_voting_power(sp.record(ts=23 * DAY, time=Types.WHOLE_WEEK)) == bias_1)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=38 * DAY, time=Types.WHOLE_WEEK)) == bias_2)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=38 * DAY, time=Types.CURRENT)) == bias_unrounded)

    @sp.add_test(name="get_total_voting_power works for even number of global checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=6,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=22 * DAY,
                    ),
                    3: sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    4: sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    5: sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                    6: sp.record(
                        bias=800 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=40 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Predicted global voting power (bias_1) for ts = 23 * DAY (21 * DAY if rounded)
        bias_1 = (1000 * DECIMALS) - (4 * DAY * 5) - (WEEK * 3) - (WEEK * 2)

        # Predicted global voting power (bias_2) for ts = 38 * DAY (35 * DAY if rounded)
        bias_2 = (1000 * DECIMALS) - (5 * DAY * 6)

        # Predicted global voting power for ts = 38 * DAY (unrounded)
        bias_unrounded = (900 * DECIMALS) - (2 * DAY * 5)

        # Correct voting powers are received
        scenario.verify(ve.get_total_voting_power(sp.record(ts=23 * DAY, time=Types.WHOLE_WEEK)) == bias_1)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=38 * DAY, time=Types.WHOLE_WEEK)) == bias_2)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=38 * DAY, time=Types.CURRENT)) == bias_unrounded)

    @sp.add_test(name="get_total_voting_power works when given timestamp is in the global checkpoints")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=6,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=21 * DAY,
                    ),
                    3: sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    4: sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    5: sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                    6: sp.record(
                        bias=800 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=40 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={
                    7 * DAY: 2 * SLOPE_MULTIPLIER,
                    14 * DAY: 1 * SLOPE_MULTIPLIER,
                }
            ),
        )

        scenario += ve

        # Voting power for 21 * DAY (rounded)
        scenario.verify(ve.get_total_voting_power(sp.record(ts=23 * DAY, time=Types.WHOLE_WEEK)) == 800 * DECIMALS)

    @sp.add_test(name="get_total_voting_power works when given timestamp is beyond the last checkpoint")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            gc_index=6,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=1000 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=3 * DAY,
                    ),
                    2: sp.record(
                        bias=800 * DECIMALS,
                        slope=2 * SLOPE_MULTIPLIER,
                        ts=21 * DAY,
                    ),
                    3: sp.record(
                        bias=700 * DECIMALS,
                        slope=3 * SLOPE_MULTIPLIER,
                        ts=24 * DAY,
                    ),
                    4: sp.record(
                        bias=1000 * DECIMALS,
                        slope=6 * SLOPE_MULTIPLIER,
                        ts=30 * DAY,
                    ),
                    5: sp.record(
                        bias=900 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=36 * DAY,
                    ),
                    6: sp.record(
                        bias=800 * DECIMALS,
                        slope=5 * SLOPE_MULTIPLIER,
                        ts=40 * DAY,
                    ),
                },
            ),
            slope_changes=sp.big_map(
                l={7 * DAY: 2 * SLOPE_MULTIPLIER, 14 * DAY: 1 * SLOPE_MULTIPLIER, 42 * DAY: 2 * SLOPE_MULTIPLIER}
            ),
        )

        scenario += ve

        # Predicted global voting power (bias_) for ts = 52 * DAY (49 * DAY if rounded)
        bias_ = (800 * DECIMALS) - (2 * DAY * 5) - (WEEK * 3)

        # Correct voting power is received for 52 * DAY
        scenario.verify(ve.get_total_voting_power(sp.record(ts=52 * DAY, time=Types.WHOLE_WEEK)) == bias_)

    ###########
    # is_owner
    ###########

    @sp.add_test(name="is_owner works correctly")
    def test():
        scenario = sp.test_scenario()

        # ALICE has 1 token of token-id 1
        ve = VoteEscrow(ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}))

        scenario += ve

        # Verify that ALICE is owner of token-id 1
        scenario.verify(ve.is_owner(sp.record(address=Addresses.ALICE, token_id=1)))

        # Verify that BOB is not owner of token-id 1
        scenario.verify(~ve.is_owner(sp.record(address=Addresses.BOB, token_id=1)))

    ####################
    # get_locked_supply
    ####################

    @sp.add_test(name="get_locked_supply works correctly")
    def test():
        scenario = sp.test_scenario()

        # Setup default locked supply value
        ve = VoteEscrow(locked_supply=100)

        scenario += ve

        # Verify that correct value is returned
        scenario.verify(ve.get_locked_supply() == 100)

    #################
    # FA2 - transfer
    #################

    @sp.add_test(name="FA2 transfer works correctly")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            ledger=sp.big_map(
                l={
                    (Addresses.ALICE, 1): 1,
                    (Addresses.BOB, 2): 1,
                    (Addresses.JOHN, 3): 1,
                    (Addresses.JOHN, 4): 1,
                    (Addresses.JOHN, 5): 0,
                }
            ),
            locks=sp.big_map(
                l={
                    1: sp.record(base_value=sp.nat(0), end=sp.nat(0)),
                    2: sp.record(base_value=sp.nat(0), end=sp.nat(0)),
                    3: sp.record(base_value=sp.nat(0), end=sp.nat(0)),
                    4: sp.record(base_value=sp.nat(0), end=sp.nat(0)),
                    5: sp.record(base_value=sp.nat(0), end=sp.nat(0)),
                }
            ),
            operators=sp.big_map(
                l={
                    sp.record(
                        token_id=1,
                        owner=Addresses.ALICE,
                        operator=Addresses.CONTRACT,
                    ): sp.unit
                },
            ),
            attached=sp.big_map(l={3: Addresses.CONTRACT}),
        )

        scenario += ve

        # When CONTRACT transfers ALICE's token to JOHN
        scenario += ve.transfer(
            [sp.record(from_=Addresses.ALICE, txs=[sp.record(to_=Addresses.JOHN, token_id=1, amount=1)])]
        ).run(sender=Addresses.CONTRACT)

        # and BOB transfer his token to JOHN
        scenario += ve.transfer(
            [sp.record(from_=Addresses.BOB, txs=[sp.record(to_=Addresses.JOHN, token_id=2, amount=1)])]
        ).run(sender=Addresses.BOB)

        # JOHN received the tokens
        scenario.verify(ve.data.ledger[(Addresses.JOHN, 1)] == 1)
        scenario.verify(ve.data.ledger[(Addresses.JOHN, 2)] == 1)

        # Transfer attempt by non-operator fails
        scenario += ve.transfer(
            [sp.record(from_=Addresses.JOHN, txs=[sp.record(to_=Addresses.BOB, token_id=4, amount=1)])]
        ).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=FA2_Errors.FA2_NOT_OPERATOR,
        )

        # Transfer of attached token 3 fails
        scenario += ve.transfer(
            [sp.record(from_=Addresses.JOHN, txs=[sp.record(to_=Addresses.BOB, token_id=3, amount=1)])]
        ).run(
            sender=Addresses.JOHN,
            valid=False,
            exception=Errors.LOCK_IS_ATTACHED,
        )

        # Transfer of amount > 1 fails
        scenario += ve.transfer(
            [sp.record(from_=Addresses.JOHN, txs=[sp.record(to_=Addresses.BOB, token_id=4, amount=2)])]
        ).run(
            sender=Addresses.JOHN,
            valid=False,
            exception=FA2_Errors.FA2_INSUFFICIENT_BALANCE,
        )

        # Transfer of amount > balance fails
        scenario += ve.transfer(
            [sp.record(from_=Addresses.JOHN, txs=[sp.record(to_=Addresses.BOB, token_id=5, amount=1)])]
        ).run(
            sender=Addresses.JOHN,
            valid=False,
            exception=FA2_Errors.FA2_INSUFFICIENT_BALANCE,
        )

    #########################
    # FA2 - update_operators
    #########################

    @sp.add_test(name="FA2 update_operators works correctly")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            ledger=sp.big_map(
                l={
                    (Addresses.ALICE, 1): 1,
                    (Addresses.ALICE, 2): 1,
                }
            ),
            operators=sp.big_map(
                l={
                    sp.record(
                        token_id=1,
                        owner=Addresses.ALICE,
                        operator=Addresses.CONTRACT,
                    ): sp.unit
                },
            ),
        )

        scenario += ve

        # When ALICE makes CONTRACT the operator of token 2 and remove operator for token 1
        scenario += ve.update_operators(
            [
                sp.variant("add_operator", sp.record(owner=Addresses.ALICE, token_id=2, operator=Addresses.CONTRACT)),
                sp.variant(
                    "remove_operator", sp.record(owner=Addresses.ALICE, token_id=1, operator=Addresses.CONTRACT)
                ),
            ]
        ).run(sender=Addresses.ALICE)

        # Storage is update correctly
        scenario.verify(
            ve.data.operators.contains(sp.record(owner=Addresses.ALICE, token_id=2, operator=Addresses.CONTRACT))
        )
        scenario.verify(
            ~ve.data.operators.contains(sp.record(owner=Addresses.ALICE, token_id=1, operator=Addresses.CONTRACT))
        )

    ################
    # add_inflation
    ################

    @sp.add_test(name="add_inflation works correctly")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(voter=Addresses.CONTRACT)

        scenario += ve

        # When Voter adds inflation to ve
        scenario += ve.add_inflation(epoch=1, value=sp.nat(10)).run(sender=Addresses.CONTRACT)

        # Storage is updated correctly
        scenario.verify(ve.data.epoch_inflation[1] == 10)
        scenario.verify(ve.data.locked_supply == 10)

    ###############################
    # claim_inflation (valid test)
    ###############################

    @sp.add_test(name="claim_inflation correctly updates the lock value for one epoch")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(end=sp.timestamp(2 * WEEK))

        # Initialize with dummy values for testing
        ve = VoteEscrow(
            voter=voter.address,
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=100 * DECIMALS,
                        end=3 * WEEK,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=100 * DECIMALS,
                        slope=5,
                        ts=WEEK,
                    )
                },
            ),
            gc_index=1,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=250 * DECIMALS,
                        slope=7,
                        ts=WEEK,
                    )
                }
            ),
            slope_changes=sp.big_map(l={3 * WEEK: 100}),
            epoch_inflation=sp.big_map(
                l={
                    1: 100 * DECIMALS,
                }
            ),
            locked_supply=350 * DECIMALS,
        )

        scenario += voter
        scenario += ve

        # When ALICE claims the inflation for her token/lock 1
        scenario += ve.claim_inflation(epochs=[1], token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * WEEK + 5),
        )

        # Storage is updated correctly
        scenario.verify(ve.data.locks[1].base_value == 140 * DECIMALS)  # Inflation share added to original value
        scenario.verify(ve.data.locked_supply == 350 * DECIMALS)
        scenario.verify(ve.data.claim_ledger[sp.record(token_id=1, epoch=1)] == sp.unit)

    @sp.add_test(name="claim_inflation correctly updates the lock value even after lock expiry")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(end=sp.timestamp(2 * WEEK))

        # Initialize with dummy values for testing
        ve = VoteEscrow(
            voter=voter.address,
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=100 * DECIMALS,
                        end=3 * WEEK,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=100 * DECIMALS,
                        slope=5,
                        ts=WEEK,
                    )
                },
            ),
            gc_index=1,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=250 * DECIMALS,
                        slope=7,
                        ts=WEEK,
                    )
                }
            ),
            slope_changes=sp.big_map(l={3 * WEEK: 100}),
            epoch_inflation=sp.big_map(
                l={
                    1: 100 * DECIMALS,
                }
            ),
            locked_supply=350 * DECIMALS,
        )

        scenario += voter
        scenario += ve

        # When ALICE claims the inflation for her token/lock 1
        scenario += ve.claim_inflation(epochs=[1], token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(3 * WEEK + 5),
        )

        # Storage is updated correctly
        scenario.verify(ve.data.locks[1].base_value == 140 * DECIMALS)  # Inflation share added to original value
        scenario.verify(ve.data.locked_supply == 350 * DECIMALS)
        scenario.verify(ve.data.claim_ledger[sp.record(token_id=1, epoch=1)] == sp.unit)

    @sp.add_test(name="claim_inflation correctly updates the lock value for multiple epochs")
    def test():
        scenario = sp.test_scenario()

        voter = Voter(end=sp.timestamp(2 * WEEK))

        # Initialize with dummy values for testing
        ve = VoteEscrow(
            voter=voter.address,
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(
                l={
                    1: sp.record(
                        base_value=100 * DECIMALS,
                        end=3 * WEEK,
                    )
                }
            ),
            num_token_checkpoints=sp.big_map(
                l={
                    1: 1,
                },
            ),
            token_checkpoints=sp.big_map(
                l={
                    (1, 1): sp.record(
                        bias=100 * DECIMALS,
                        slope=5,
                        ts=WEEK,
                    )
                },
            ),
            gc_index=1,
            global_checkpoints=sp.big_map(
                l={
                    1: sp.record(
                        bias=250 * DECIMALS,
                        slope=7,
                        ts=WEEK,
                    )
                }
            ),
            slope_changes=sp.big_map(l={3 * WEEK: 100}),
            epoch_inflation=sp.big_map(
                l={
                    1: 100 * DECIMALS,
                    2: 200 * DECIMALS,
                    3: 300 * DECIMALS,
                }
            ),
            locked_supply=850 * DECIMALS,
        )

        scenario += voter
        scenario += ve

        # When ALICE claims the inflation for her token/lock 1 for epochs 1, 2, 3
        scenario += ve.claim_inflation(epochs=[1, 2, 3], token_id=1).run(
            sender=Addresses.ALICE,
            now=sp.timestamp(2 * WEEK + 5),
        )

        # Storage is updated correctly
        scenario.verify(ve.data.locks[1].base_value == 340 * DECIMALS)  # Inflation share added to original value
        scenario.verify(ve.data.locked_supply == 850 * DECIMALS)
        scenario.verify(ve.data.claim_ledger[sp.record(token_id=1, epoch=1)] == sp.unit)
        scenario.verify(ve.data.claim_ledger[sp.record(token_id=1, epoch=2)] == sp.unit)
        scenario.verify(ve.data.claim_ledger[sp.record(token_id=1, epoch=3)] == sp.unit)

    #################################
    # claim_inflation (failure test)
    #################################

    @sp.add_test(name="claim_inflation fails if already claimed or if inflation has not been added")
    def test():
        scenario = sp.test_scenario()

        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            claim_ledger=sp.big_map(
                l={
                    sp.record(token_id=1, epoch=1): sp.unit,
                }
            ),
        )

        scenario += ve

        # When ALICE tries to claim inflation for token/lock 1 a second time, txn fails
        scenario += ve.claim_inflation(epochs=[1], token_id=1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.ALREADY_CLAIMED_INFLATION,
        )

        # When ALICE tries to claim inflation for an epoch that has not been added, txn fails
        scenario += ve.claim_inflation(epochs=[2], token_id=1).run(
            sender=Addresses.ALICE,
            valid=False,
            exception=Errors.INFLATION_NOT_ADDED,
        )

    sp.add_compilation_target("vote_escrow", VoteEscrow())
