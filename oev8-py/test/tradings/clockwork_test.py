from datetime import datetime
from unittest.mock import Mock, call
from pytest import raises  # type:ignore
from pytest import mark  # type:ignore
from oev8.excs import TradingIsNotFound
from oev8.svcs.clockwork.trading import TradingClockworkService


def finalize_trading_mock(trd_id) -> bool:
    if trd_id == '111':
        return False
    return True


def evict_trading_mock(trd_id) -> bool:
    if trd_id == '222':
        return False
    return True


def new_trading_clockwork_svc():
    return TradingClockworkService(
        do_complete_trading=Mock(side_effect=finalize_trading_mock),
        do_evict_trading=Mock(side_effect=evict_trading_mock))


def test_find_fail():
    trading_clockwork_svc = new_trading_clockwork_svc()
    with raises(TradingIsNotFound):
        trading_clockwork_svc.find('1818')


def test_regist_ok():
    trading_clockwork_svc = new_trading_clockwork_svc()
    trading_clockwork_svc.regist('1818', datetime.utcnow().timestamp())
    assert trading_clockwork_svc.find('1818')


def test_unregist_ok():
    trading_clockwork_svc = new_trading_clockwork_svc()
    trading_clockwork_svc.regist('1818', datetime.utcnow().timestamp())
    trading_clockwork_svc.unregist('1818')


def test_unregist_fail():
    trading_clockwork_svc = new_trading_clockwork_svc()
    trading_clockwork_svc.regist('1818', datetime.utcnow().timestamp())
    with raises(TradingIsNotFound):
        trading_clockwork_svc.unregist('1819')
    assert trading_clockwork_svc.find('1818')


def test_update_ok():
    trading_clockwork_svc = new_trading_clockwork_svc()
    dt_1 = datetime(2011, 10, 13, 12, 31, 59).timestamp()
    dt_2 = datetime(2020, 10, 13, 12, 31, 59).timestamp()
    trading_clockwork_svc.regist('1818', dt_1)
    assert trading_clockwork_svc.find('1818') == dt_1
    trading_clockwork_svc.update('1818', dt_2)
    assert trading_clockwork_svc.find('1818') == dt_2


def test_update_fail():
    trading_clockwork_svc = new_trading_clockwork_svc()
    dt_1 = datetime(2011, 10, 13, 12, 31, 59).timestamp()
    dt_2 = datetime(2020, 10, 13, 12, 31, 59).timestamp()
    trading_clockwork_svc.regist('1818', dt_1)
    with raises(TradingIsNotFound):
        trading_clockwork_svc.update('1819', dt_2)


def test_batch_ok():
    trading_clockwork_svc = new_trading_clockwork_svc()

    dt_1 = datetime(1982, 10, 13, 12, 31, 59).timestamp()
    dt_2 = datetime(1999, 10, 13, 12, 31, 59).timestamp()
    dt_3 = datetime(3983, 10, 13, 12, 31, 59).timestamp()
    dt_4 = datetime(1983, 10, 13, 12, 31, 59).timestamp()

    dt_now = datetime(2020, 5, 20, 6, 30, 21).timestamp()

    trading_clockwork_svc.regist('11', dt_1)
    trading_clockwork_svc.regist('111', dt_2)  # will fail at completion.
    trading_clockwork_svc.regist('64', dt_3)   # never.
    trading_clockwork_svc.regist('222', dt_4)  # will fail at eviction.

    results = trading_clockwork_svc.batch(dt_now)

    assert results == ['11']

    trading_clockwork_svc.do_complete_trading.assert_has_calls([
        # 시간순 호출.
        call('11'), call('222'), call('111'),
    ])

    trading_clockwork_svc.do_evict_trading.assert_has_calls([
        # 시간순 호출.
        call('11'), call('222'),
    ])
