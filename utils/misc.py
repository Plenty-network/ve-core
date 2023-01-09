# Miscellenous utilies (mostly used for the token_metadata offchain view in vote_escrow.py)
import smartpy as sp

# Converts a number of type nat to bytes
def bytes_of_nat(num):
    sp.set_type(num, sp.TNat)

    nat_to_byte = sp.compute(
        sp.map(
            l={
                0: sp.bytes("0x30"),
                1: sp.bytes("0x31"),
                2: sp.bytes("0x32"),
                3: sp.bytes("0x33"),
                4: sp.bytes("0x34"),
                5: sp.bytes("0x35"),
                6: sp.bytes("0x36"),
                7: sp.bytes("0x37"),
                8: sp.bytes("0x38"),
                9: sp.bytes("0x39"),
            },
            tkey=sp.TNat,
            tvalue=sp.TBytes,
        )
    )

    b = sp.local("b", nat_to_byte[num % 10])
    n = sp.local("n", num / 10)

    with sp.while_(n.value > 0):
        b.value = nat_to_byte[n.value % 10] + b.value
        n.value /= 10

    sp.result(b.value)


# If the number is greater than 1000, it strips the decimals
# If the number is less than 1000, it keeps two decimal places
# Value returned as `Pair <whole> <fraction>`
def get_floating_point(num):
    sp.set_type(num, sp.TNat)

    # Strip the decimals
    whole_num = sp.compute(num // 10**18)  # PLY's decimals is fixed at 10^18

    with sp.if_(num >= (1000 * 10**18)):
        sp.result((whole_num, sp.nat(0)))
    with sp.else_():
        # fractional part limited to 2 decimal places
        fractional_num = sp.as_nat((num - whole_num * 10**18)) // 10**16
        sp.result((whole_num, fractional_num))
