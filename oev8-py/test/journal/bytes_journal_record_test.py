import struct
from pytest import mark, raises
from oev8.journal.bytes import BytesJournalRecords
from test.testsup import rand_uint256, rand_bytes, inverse_bytes


@mark.repeat(50)
def test_pack_unpack():
    seq_num = rand_uint256()
    bs = rand_bytes()

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    unpacked = BytesJournalRecords.unpack_or_error(pack_result[1])

    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs


@mark.repeat(20)
def test_extra_body_bs():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1] + b'cafebabe6910'

    # Should be okay
    unpacked = BytesJournalRecords.unpack_or_error(packed)

    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs


@mark.repeat(10)
def test_short_body_bs():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1]
    packed = packed[:len(packed)-5]

    with raises(Exception):
        BytesJournalRecords.unpack_or_error(packed)


@mark.repeat(10)
def test_extract_and_replace_body_checksum_bs():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1]

    #
    unpacked = BytesJournalRecords.unpack_or_error(packed)
    body_checksum_bs = BytesJournalRecords.extract_body_checksum_bs(packed)

    assert unpacked.body_bs_xxh64 == struct.unpack('!Q', body_checksum_bs)[0]
    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs

    # replacing
    body_checksum_bs2 = inverse_bytes(body_checksum_bs)
    packed2 = BytesJournalRecords.replace_body_checksum_bs(packed, body_checksum_bs2)

    unpacked2 = BytesJournalRecords.unpack(packed2)

    # 변조된 값이 이전 체크섬과 다르고, unpack해서 얻어졌을 때 동일:
    assert body_checksum_bs != body_checksum_bs2
    assert unpacked2.body_bs_xxh64 == struct.unpack('!Q', body_checksum_bs2)[0]

    # 나머지는 그대로.
    assert unpacked2.seq_num == seq_num
    assert unpacked2.body_bs == bs
    assert unpacked2.seq_num_bs_xxh64 == unpacked.seq_num_bs_xxh64
    assert unpacked2.body_bs_len == unpacked.body_bs_len


@mark.repeat(10)
def test_extract_and_replace_seq_num_checksum_bs():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1]

    #
    unpacked = BytesJournalRecords.unpack_or_error(packed)
    ok_checksum_bs = BytesJournalRecords.extract_seq_num_checksum_bs(packed)

    assert unpacked.seq_num_bs_xxh64 == struct.unpack('!Q', ok_checksum_bs)[0]
    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs

    # replacing
    inv_checksum_bs = inverse_bytes(ok_checksum_bs)
    packed2 = BytesJournalRecords.replace_seq_num_checksum_bs(packed, inv_checksum_bs)
    unpacked2 = BytesJournalRecords.unpack(packed2)

    # 변조된 값이 이전 체크섬과 다르고, unpack해서 얻어졌을 때 동일:
    assert ok_checksum_bs != inv_checksum_bs
    assert unpacked2.seq_num_bs_xxh64 == struct.unpack('!Q', inv_checksum_bs)[0]

    # 나머지는 그대로.
    assert unpacked2.seq_num == seq_num
    assert unpacked2.body_bs == bs
    assert unpacked2.seq_num_bs_xxh64 != unpacked.seq_num_bs_xxh64
    assert unpacked2.body_bs_len == unpacked.body_bs_len
    assert unpacked2.body_bs_xxh64 == unpacked.body_bs_xxh64


@mark.repeat(10)
def test_invalid_body_checksum():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1]

    ok_checksum_bs = BytesJournalRecords.extract_body_checksum_bs(packed)
    inv_checksum_bs = inverse_bytes(ok_checksum_bs)
    inv_checksum = struct.unpack('!Q', inv_checksum_bs)[0]
    packed_inv = BytesJournalRecords.replace_body_checksum_bs(packed, inv_checksum_bs)
    assert ok_checksum_bs != inv_checksum_bs

    unpacked_with_inv = BytesJournalRecords.unpack(packed_inv)
    assert unpacked_with_inv.seq_num == seq_num  # 내용은 같지만.
    assert unpacked_with_inv.body_bs == bs
    assert unpacked_with_inv.body_bs_xxh64 != unpacked_with_inv.actual_body_bs_xxh64
    assert unpacked_with_inv.body_bs_xxh64 == inv_checksum

    with raises(Exception):
        BytesJournalRecords.unpack_or_error(packed_inv)

    # 다시 복구:
    packed2 = BytesJournalRecords.replace_body_checksum_bs(packed_inv, ok_checksum_bs)
    unpacked = BytesJournalRecords.unpack_or_error(packed2)
    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs


@mark.repeat(10)
def test_invalid_seq_num_checksum():
    seq_num = rand_uint256()
    bs = rand_bytes(min_len=10)

    pack_result = BytesJournalRecords.pack(seq_num, bs)
    packed = pack_result[1]

    ok_checksum_bs = BytesJournalRecords.extract_seq_num_checksum_bs(packed)
    inv_checksum_bs = inverse_bytes(ok_checksum_bs)
    inv_checksum = struct.unpack('!Q', inv_checksum_bs)[0]
    packed_inv = BytesJournalRecords.replace_seq_num_checksum_bs(packed, inv_checksum_bs)
    assert ok_checksum_bs != inv_checksum_bs

    unpacked_with_inv = BytesJournalRecords.unpack(packed_inv)
    assert unpacked_with_inv.seq_num == seq_num  # 내용은 같지만.
    assert unpacked_with_inv.body_bs == bs
    assert unpacked_with_inv.seq_num_bs_xxh64 != unpacked_with_inv.actual_seq_num_bs_xxh64
    assert unpacked_with_inv.seq_num_bs_xxh64 == inv_checksum

    with raises(Exception):
        BytesJournalRecords.unpack_or_error(packed_inv)

    # 다시 복구:
    packed2 = BytesJournalRecords.replace_seq_num_checksum_bs(packed_inv, ok_checksum_bs)
    unpacked = BytesJournalRecords.unpack_or_error(packed2)
    assert unpacked.seq_num == seq_num
    assert unpacked.body_bs == bs
