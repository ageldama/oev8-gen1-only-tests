# pylint: disable=redefined-outer-name

from pytest import fixture  # type:ignore
from uuid import uuid4
from oev8.u128_bytes import to_netord_bytes, from_netord_bytes


@fixture
def sample_u128():
    """테스트용 uint128

    - 269826686211054628168603528123472785419.
    - cafebabe_feedc0de_00bab10c_1badb00b.
    """
    high = 0xcafebabe_feedc0de
    low = 0x00bab10c_1badb00b
    return (high << 64) + low


def test_first_byte(sample_u128):
    u = sample_u128 >> 120
    assert u == 0xca


def test_to_netord_bytes(sample_u128):
    byte_seq = to_netord_bytes(sample_u128)
    assert byte_seq == \
        b'\xCA\xFE\xBA\xBE\xFE\xED\xC0\xDE\x00\xBA\xB1\x0C\x1B\xAD\xB0\x0B'


def test_to_netord_bytes_one():
    byte_seq = to_netord_bytes(1)
    print(byte_seq)
    assert byte_seq == \
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'


def test_from_netord_bytes(sample_u128):
    byte_seq = to_netord_bytes(sample_u128)
    back = from_netord_bytes(byte_seq)
    assert back == 269826686211054628168603528123472785419


def test_uuid_int():
    se = set([uuid4() for i in range(10)])
    assert len(se) == 10
    for i in se:
        u = uuid4().int
        byte_seq = to_netord_bytes(u)
        back = from_netord_bytes(byte_seq)
        assert u == back
