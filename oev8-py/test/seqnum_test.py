from pytest import raises  # type: ignore
from oev8.svcs.seq_num import SeqType
from oev8.svcs.seq_num import SeqNumService


def test_seq_num_svc_1st():
    svc = SeqNumService()
    assert svc.cur_val(SeqType.CMD_REQ) == 0
    assert svc.next(SeqType.CMD_REQ) == 1


def test_SeqNum(seq_num_service):
    assert seq_num_service

    assert seq_num_service.next(SeqType.CMD_REQ) == 1
    assert seq_num_service.next(SeqType.CMD_REQ) == 2
    assert seq_num_service.next(SeqType.ORDER) == 1
    assert seq_num_service.next(SeqType.MATCH) == 1
    assert seq_num_service.next(SeqType.MATCH) == 2

    assert seq_num_service.cur_val(SeqType.CMD_REQ) == 2
    assert seq_num_service.cur_val(SeqType.ORDER) == 1
    assert seq_num_service.cur_val(SeqType.MATCH) == 2

    with raises(Exception):
        assert seq_num_service.next(18)

    with raises(Exception):
        assert seq_num_service.cur_val(18)
