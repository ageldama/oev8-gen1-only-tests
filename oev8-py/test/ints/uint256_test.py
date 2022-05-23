from pytest import mark
from oev8.ints import UInt256
from test.testsup import rand_uint256


def test_uint256_max_be():
    bs = UInt256.to_be_bytes(UInt256.MAX)
    assert all(0xff == b for b in bs)


@mark.repeat(50)
def test_uint256_from_to_be_bytes():
    n = rand_uint256()
    bs = UInt256.to_be_bytes(n)
    n2 = UInt256.from_be_bytes(bs)
    assert n == n2


@mark.repeat(50)
def test_uint256_from_to_be_hex():
    n = rand_uint256()
    hex_str = UInt256.to_be_hex(n)
    n2 = UInt256.from_be_hex(hex_str)
    assert n == n2
