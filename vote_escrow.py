import smartpy as sp

Addresses = sp.io.import_script_from_url("file:helpers/addresses.py")
TokenUtils = sp.io.import_script_from_url("file:utils/token.py")
FA12 = sp.io.import_script_from_url("file:ply_fa12.py").FA12

############
# Constants
############

DAY = 86400
WEEK = 7 * DAY
YEAR = 52 * WEEK
MAX_TIME = 4 * YEAR

# Increase precision during slope and associated bias calculation
SLOPE_MULTIPLIER = 10 ** 18

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

    # Enumeration for voting power readers
    CURRENT = 0
    WHOLE_WEEK = 1


#########
# Errors
#########


class Errors:
    INVALID_LOCK_TIME = "INVALID_LOCK_TIME"
    LOCK_DOES_NOT_EXIST = "LOCK_DOES_NOT_EXIST"
    NOT_AUTHORISED = "NOT_AUTHORISED"
    LOCK_YET_TO_EXPIRE = "LOCK_YET_TO_EXPIRE"
    LOCK_HAS_EXPIRED = "LOCK_HAS_EXPIRED"
    INVALID_INCREASE_VALUE = "INVALID_INCREASE_VALUE"
    INVALID_INCREASE_END_TIMESTAMP = "INVALID_INCREASE_END_TIMESTAMP"
    TOO_EARLY_TIMESTAMP = "TOO_EARLY_TIMESTAMP"
    INVALID_TIME = "INVALID_TIME"
    LOCK_IS_ATTACHED = "LOCK_IS_ATTACHED"


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
            tvalue=sp.TUnit,
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
        base_token=Addresses.TOKEN,
        locked_supply=sp.nat(0),
    ):
        self.init(
            ledger=ledger,
            operators=operators,
            locks=locks,
            attached=attached,
            uid=sp.nat(0),
            token_checkpoints=token_checkpoints,
            num_token_checkpoints=num_token_checkpoints,
            gc_index=gc_index,
            global_checkpoints=global_checkpoints,
            slope_changes=slope_changes,
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
                # VE specific
                locks=sp.TBigMap(sp.TNat, Types.LOCK),
                attached=sp.TBigMap(sp.TNat, sp.TUnit),
                uid=sp.TNat,
                token_checkpoints=sp.TBigMap(sp.TPair(sp.TNat, sp.TNat), Types.POINT),
                num_token_checkpoints=sp.TBigMap(sp.TNat, sp.TNat),
                gc_index=sp.TNat,
                global_checkpoints=sp.TBigMap(sp.TNat, Types.POINT),
                slope_changes=sp.TBigMap(sp.TNat, sp.TNat),
                base_token=sp.TAddress,
                locked_supply=sp.TNat,
            )
        )

    # Default tzip-12 specified transfer for NFTs
    @sp.entry_point
    def transfer(self, params):
        sp.set_type(params, Types.TRANSFER_PARAMS)

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

                # Each token is unique, so transfer amount must be 1
                with sp.if_(tx.amount == 1):
                    # Verify that the address has sufficient balance for transfer
                    sp.verify(
                        self.data.ledger[(current_from, tx.token_id)] >= tx.amount,
                        FA2_Errors.FA2_INSUFFICIENT_BALANCE,
                    )

                    # Make transfer
                    self.data.ledger[(current_from, tx.token_id)] = sp.as_nat(
                        self.data.ledger[(current_from, tx.token_id)] - tx.amount
                    )
                    with sp.if_(~self.data.ledger.contains((tx.to_, tx.token_id))):
                        self.data.ledger[(tx.to_, tx.token_id)] = 0
                    self.data.ledger[(tx.to_, tx.token_id)] += tx.amount

                with sp.else_():
                    sp.failwith(FA2_Errors.FA2_INVALID_AMOUNT)

    # Default tzip-12 specified balance_of
    @sp.entry_point
    def balance_of(self, params):
        sp.set_type(params, Types.BALANCE_OF_PARAMS)

        # Response object
        response = sp.local("response", [])

        with sp.for_("request", params.requests) as request:
            sp.verify(self.data.locks.contains(request.token_id), FA2_Errors.FA2_TOKEN_UNDEFINED)

            with sp.if_(self.data.ledger.contains((request.owner, request.token_id))):
                response.value.push(
                    sp.record(request=request, balance=self.data.ledger[(request.owner, request.token_id)])
                )
            with sp.else_():
                response.value.push(sp.record(request=request, balance=sp.nat(0)))

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
                    self.data.attached[token_id] = sp.unit
                with arg.match("remove_attachment") as token_id:
                    # Sanity checks
                    sp.verify(self.data.ledger.get((params.owner, token_id), 0) == 1, Errors.NOT_AUTHORISED)
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
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

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
            # Calculate current global bias and slope
            c_bias = sp.local("c_bias", self.data.global_checkpoints[self.data.gc_index].bias)
            c_slope = sp.local("c_slope", self.data.global_checkpoints[self.data.gc_index].slope)

            n_ts = sp.local("n_ts", ((self.data.global_checkpoints[self.data.gc_index].ts + WEEK) // WEEK) * WEEK)
            c_ts = sp.local("c_ts", self.data.global_checkpoints[self.data.gc_index].ts)

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
            with sp.if_(~self.data.slope_changes.contains(params.new_end)):
                self.data.slope_changes[params.new_end] = 0
            self.data.slope_changes[params.new_end] += params.new_cp.slope

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

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Find a timestamp rounded off to nearest week
        ts = (params.end // WEEK) * WEEK

        # Lock period in seconds
        d_ts = sp.as_nat(ts - now_, Errors.INVALID_LOCK_TIME)

        # Verify that calculated timestamp falls in the correct range
        sp.verify((d_ts >= WEEK) & (d_ts <= MAX_TIME), Errors.INVALID_LOCK_TIME)

        # Calculate slope & bias for linearly decreasing voting power
        bias = (params.base_value * d_ts) // MAX_TIME
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Update uid and mint associated NFT for params.user_address
        self.data.uid += 1
        self.data.ledger[(params.user_address, self.data.uid)] = sp.nat(1)

        # Register a lock
        self.data.locks[self.data.uid] = sp.record(
            base_value=params.base_value,
            end=ts,
        )

        # Record token checkpoint
        self.data.num_token_checkpoints[self.data.uid] = 1
        self.data.token_checkpoints[(self.data.uid, self.data.num_token_checkpoints[self.data.uid])] = sp.record(
            slope=slope,
            bias=bias,
            ts=now_,
        )

        # Record global checkpoint for lock creation
        old_cp = sp.record(bias=0, slope=0, ts=0)
        new_cp = self.data.token_checkpoints[(self.data.uid, self.data.num_token_checkpoints[self.data.uid])]
        self.record_global_checkpoint(
            sp.record(
                old_cp=old_cp,
                new_cp=new_cp,
                prev_end=0,
                new_end=self.data.locks[self.data.uid].end,
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

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Sanity checks
        sp.verify(self.data.locks.contains(token_id), Errors.LOCK_DOES_NOT_EXIST)
        sp.verify(self.data.ledger.get((sp.sender, token_id), 0) == 1, Errors.NOT_AUTHORISED)
        sp.verify(now_ > self.data.locks[token_id].end, Errors.LOCK_YET_TO_EXPIRE)
        sp.verify(~self.data.attached.contains(token_id), Errors.LOCK_IS_ATTACHED)

        # Transfer underlying PLY
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.self_address,
                to_=sp.sender,
                value=self.data.locks[token_id].base_value,
                token_address=self.data.base_token,
            )
        )

        # Decrease locked supply
        self.data.locked_supply = sp.as_nat(self.data.locked_supply - self.data.locks[token_id].base_value)

        # Remove associated token
        self.data.ledger[(sp.sender, token_id)] = 0

        # Delete the lock
        del self.data.locks[token_id]

    @sp.entry_point
    def increase_lock_value(self, params):
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, value=sp.TNat))

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Sanity checks
        sp.verify(self.data.locks.contains(params.token_id), Errors.LOCK_DOES_NOT_EXIST)
        sp.verify(self.data.ledger.get((sp.sender, params.token_id), 0) == 1, Errors.NOT_AUTHORISED)
        sp.verify(self.data.locks[params.token_id].end > now_, Errors.LOCK_HAS_EXPIRED)
        sp.verify(params.value > 0, Errors.INVALID_INCREASE_VALUE)

        # Modify base value of the lock
        self.data.locks[params.token_id].base_value += params.value

        # Fetch current updated bias
        index_ = self.data.num_token_checkpoints[params.token_id]
        last_tc = self.data.token_checkpoints[(params.token_id, index_)]
        bias_ = sp.as_nat(last_tc.bias - (last_tc.slope * sp.as_nat(now_ - last_tc.ts)) // SLOPE_MULTIPLIER)

        # Time left in lock
        d_ts = sp.as_nat(self.data.locks[params.token_id].end - now_)

        # Increase in bias
        i_bias = (params.value * d_ts) // MAX_TIME

        # New bias & slope
        n_bias = bias_ + i_bias
        n_slope = (n_bias * SLOPE_MULTIPLIER) // d_ts

        # Record new token checkpoint
        self.data.token_checkpoints[
            (params.token_id, self.data.num_token_checkpoints[params.token_id] + 1)
        ] = sp.record(
            slope=n_slope,
            bias=n_bias,
            ts=now_,
        )

        # Updated later to prevent access error
        self.data.num_token_checkpoints[params.token_id] += 1

        # Record global checkpoint
        old_cp = self.data.token_checkpoints[
            (params.token_id, sp.as_nat(self.data.num_token_checkpoints[params.token_id] - 1))
        ]
        new_cp = self.data.token_checkpoints[(params.token_id, self.data.num_token_checkpoints[params.token_id])]
        self.record_global_checkpoint(
            sp.record(
                old_cp=old_cp,
                new_cp=new_cp,
                prev_end=self.data.locks[params.token_id].end,
                new_end=self.data.locks[params.token_id].end,
            )
        )

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
        sp.set_type(params, sp.TRecord(token_id=sp.TNat, end=sp.TNat))

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Find a timestamp rounded off to nearest week
        ts = (params.end // WEEK) * WEEK

        # Lock period in seconds
        d_ts = sp.as_nat(ts - now_, Errors.INVALID_LOCK_TIME)

        # Sanity checks
        sp.verify(self.data.ledger[(sp.sender, params.token_id)] == 1, Errors.NOT_AUTHORISED)
        sp.verify(self.data.locks[params.token_id].end > now_, Errors.LOCK_HAS_EXPIRED)
        sp.verify(
            (ts > self.data.locks[params.token_id].end) & (d_ts <= MAX_TIME), Errors.INVALID_INCREASE_END_TIMESTAMP
        )

        # Locally record previous end
        prev_end = sp.local("prev_end", self.data.locks[params.token_id].end)

        # Update lock
        self.data.locks[params.token_id].end = ts

        # Calculate new bias and slope
        bias = (self.data.locks[params.token_id].base_value * d_ts) // MAX_TIME
        slope = (bias * SLOPE_MULTIPLIER) // d_ts

        # Add new checkpoint for token
        self.data.num_token_checkpoints[params.token_id] += 1
        self.data.token_checkpoints[(params.token_id, self.data.num_token_checkpoints[params.token_id])] = sp.record(
            slope=slope,
            bias=bias,
            ts=now_,
        )

        # Record global checkpoint
        old_cp = self.data.token_checkpoints[
            (params.token_id, sp.as_nat(self.data.num_token_checkpoints[params.token_id] - 1))
        ]
        new_cp = self.data.token_checkpoints[(params.token_id, self.data.num_token_checkpoints[params.token_id])]
        self.record_global_checkpoint(
            sp.record(
                old_cp=old_cp,
                new_cp=new_cp,
                prev_end=prev_end.value,
                new_end=self.data.locks[params.token_id].end,
            )
        )

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
        ts = (params.ts // factor.value) * factor.value

        # Sanity checks
        sp.verify((params.time == Types.CURRENT) | (params.time == Types.WHOLE_WEEK), Errors.INVALID_TIME)
        sp.verify(self.data.locks.contains(params.token_id), Errors.LOCK_DOES_NOT_EXIST)
        sp.verify(ts >= self.data.token_checkpoints[(params.token_id, 1)].ts, Errors.TOO_EARLY_TIMESTAMP)

        last_checkpoint = self.data.token_checkpoints[
            (params.token_id, self.data.num_token_checkpoints[params.token_id])
        ]

        with sp.if_(ts >= last_checkpoint.ts):
            i_bias = last_checkpoint.bias
            slope = last_checkpoint.slope
            f_bias = i_bias - (sp.as_nat(ts - last_checkpoint.ts) * slope) // SLOPE_MULTIPLIER
            with sp.if_(f_bias < 0):
                sp.result(sp.nat(0))
            with sp.else_():
                sp.result(sp.as_nat(f_bias))
        with sp.else_():
            high = sp.local("high", sp.as_nat(self.data.num_token_checkpoints[params.token_id] - 2))
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
                bias = self.data.token_checkpoints[(params.token_id, low.value + 1)].bias
                slope = self.data.token_checkpoints[(params.token_id, low.value + 1)].slope
                d_ts = ts - self.data.token_checkpoints[(params.token_id, low.value + 1)].ts
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
        ts = (params.ts // factor.value) * factor.value

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

        with sp.if_(~self.data.ledger.contains((params.address, params.token_id))):
            sp.result(sp.bool(False))
        with sp.else_():
            with sp.if_(self.data.ledger[(params.address, params.token_id)] != 1):
                sp.result(sp.bool(False))
            with sp.else_():
                sp.result(sp.bool(True))

    @sp.onchain_view()
    def get_locked_supply(self):
        sp.result(self.data.locked_supply)


if __name__ == "__main__":

    ###############
    # Test Helpers
    ###############
    NOW = int(0.5 * DAY)
    DECIMALS = 10 ** 18

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
    # increase_lock_end (valid test)
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

    #########
    # attach
    #########

    @sp.add_test(name="attach works correctly")
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
        scenario.verify(ve.data.attached[1] == sp.unit)
        scenario.verify(ve.data.attached[2] == sp.unit)

        # When JOHN (not operator for ALICE's token) tries changing attachment status of token/lock 1, txn fails
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("remove_attachment", 1)]).run(
            sender=Addresses.JOHN,
            valid=False,
            exception=Errors.NOT_AUTHORISED,
        )

        # When ALICE removes her attachment
        scenario += ve.update_attachments(owner=Addresses.ALICE, attachments=[sp.variant("remove_attachment", 1)]).run(
            sender=Addresses.ALICE
        )

        # Storage is updated correctly
        scenario.verify(~ve.data.attached.contains(1))

    #########################
    # get_token_voting_power
    #########################

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
            attached=sp.big_map(l={3: sp.unit}),
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
            exception=FA2_Errors.FA2_INVALID_AMOUNT,
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

    sp.add_compilation_target("vote_escrow", VoteEscrow())
