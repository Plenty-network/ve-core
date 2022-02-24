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


#########
# Errors
#########


class Errors:
    INVALID_LOCK_TIME = "INVALID_LOCK_TIME"
    LOCK_DOES_NOT_EXIST = "LOCK_DOES_NOT_EXIST"
    NOT_AUTHORISED = "NOT_AUTHORISED"
    LOCK_YET_TO_EXPIRE = "LOCK_YET_TO_EXPIRE"


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
        base_token=Addresses.TOKEN,
    ):
        self.init(
            ledger=ledger,
            operators=operators,
            locks=locks,
            uid=sp.nat(0),
            token_checkpoints=token_checkpoints,
            num_token_checkpoints=num_token_checkpoints,
            base_token=base_token,
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
        slope = params.base_value // d_ts
        bias = (params.base_value * d_ts) // MAX_TIME

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

        # Retrieve base token to self address
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.sender,
                to_=sp.self_address,
                value=params.base_value,
                token_address=self.data.base_token,
            )
        )

    @sp.entry_point
    def withdraw(self, token_id):
        sp.set_type(token_id, sp.TNat)

        # nat version of block timestamp
        now_ = sp.as_nat(sp.now - sp.timestamp(0))

        # Sanity checks
        sp.verify(self.data.locks.contains(token_id), Errors.LOCK_DOES_NOT_EXIST)
        sp.verify(self.data.ledger.get((sp.sender, token_id), 0) == 1, Errors.NOT_AUTHORISED)
        sp.verify(now_ > self.data.locks[token_id].end, Errors.LOCK_YET_TO_EXPIRE)

        # Transfer underlying PLY
        TokenUtils.transfer_FA12(
            sp.record(
                from_=sp.self_address,
                to_=sp.sender,
                value=self.data.locks[token_id].base_value,
                token_address=self.data.base_token,
            )
        )

        # Remove associated token
        self.data.ledger[(sp.sender, token_id)] = 0

        # Delete the lock
        del self.data.locks[token_id]


if __name__ == "__main__":

    ###############
    # Test Helpers
    ###############
    NOW = int(0.5 * DAY)
    DECIMALS = 10 ** 18

    ##############
    # create_lock
    ##############
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
        slope = (1000 * DECIMALS) // d_ts

        # Correct checkpoint is created for the token
        scenario.verify(ve.data.token_checkpoints[(1, 1)] == sp.record(bias=bias, slope=slope, ts=NOW))

        # Tokens get lock in ve
        scenario.verify(ply_token.data.balances[ve.address].balance == 1000 * DECIMALS)

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
        slope = (1000 * DECIMALS) // d_ts

        # Correct checkpoint is created for the token
        scenario.verify(ve.data.token_checkpoints[(1, 1)] == sp.record(bias=bias, slope=slope, ts=0))

        # Tokens get lock in ve
        scenario.verify(ply_token.data.balances[ve.address].balance == 1000 * DECIMALS)

    ###########
    # withdraw
    ###########

    @sp.add_test(name="withdraw works correctly")
    def test():
        scenario = sp.test_scenario()

        ply_token = FA12()

        # Setup a lock with base value of 100 PLY and ending in 7 days
        ve = VoteEscrow(
            ledger=sp.big_map(l={(Addresses.ALICE, 1): 1}),
            locks=sp.big_map(l={1: sp.record(base_value=100, end=7 * DAY)}),
            base_token=ply_token.address,
        )

        scenario += ply_token
        scenario += ve

        # Mint PLY for ve
        scenario += ply_token.mint(address=ve.address, value=100).run(sender=Addresses.ADMIN)

        # When ALICE withdraw from her lock under token_id 1
        scenario += ve.withdraw(1).run(sender=Addresses.ALICE, now=sp.timestamp(NOW + 7 * DAY))

        # Storage is updated correctly
        scenario.verify(~ve.data.locks.contains(1))
        scenario.verify(ve.data.ledger[(Addresses.ALICE, 1)] == 0)

        # ALICE gets back the underlying PLY
        scenario.verify(ply_token.data.balances[Addresses.ALICE].balance == 100)

    sp.add_compilation_target("vote_escrow", VoteEscrow())
