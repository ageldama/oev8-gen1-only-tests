"""TradingService.cancel_trading 테스트"""
from unittest.mock import call
from pytest import raises, fixture  # type: ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import TradingId, TradingState, CurrencyType
from oev8.typedefs import CustomerId, BalanceType, CurrencyAmt
from oev8.typedefs import ItemQty
from oev8.consts import SERVICE_CUSTOMER
from oev8.excs import TradingIsNotFound, TradingIsNotCancellable
from oev8.values.event_writer import BalanceXferToCauseTradingCancellation


def assert_event_writer_not_called(event_writer_mock):
    """event_writer_mock에서 cancel_trading이 부르는 이벤트 호출 없음을 검증"""
    event_writer_mock.on_balance_xfer_to.assert_not_called()
    event_writer_mock.on_trading_cancelled.assert_not_called()


def test_cancel_trading_on_invalid_trading_id(
        trading_service: TradingService,
        event_writer_mock
):
    """존재하는 trading_id이어야 한다."""
    with raises(TradingIsNotFound):
        trading_service.cancel_trading(TradingId(12345))
    assert_event_writer_not_called(event_writer_mock)


def test_cancel_trading_on_invalid_trading_state(
        trading_service: TradingService,
        event_writer_mock
):
    """trading.state == {OPEN | PAUSED} 이어야 한다."""
    curr = CurrencyType(1)
    trd_id = TradingId('123')
    trd = trading_service.start_new_trading(trd_id, curr)

    #
    trd.state = TradingState.COMPLETED
    with raises(TradingIsNotCancellable):
        trading_service.cancel_trading(trd_id)

    assert_event_writer_not_called(event_writer_mock)


def test_cancel_trading_on_paused(
        trading_service: TradingService,
        event_writer_mock
):
    """trading.state == {OPEN | PAUSED} 이어야 한다."""
    trd_id = TradingId('123')
    curr = CurrencyType(1)

    _ = trading_service.start_new_trading(trd_id, curr)

    trading_service.pause_trading(trd_id)

    trading_service.cancel_trading(trd_id)

    # event_writer.
    # -- 거래 없었었으니까.
    event_writer_mock.on_balance_xfer_to.assert_not_called()
    # -- 하지만 취소는 진행.
    event_writer_mock.on_trading_cancelled.assert_called_with(trd_id=trd_id)


def test_cancel_trading_on_opened(
        trading_service: TradingService,
        event_writer_mock
):
    """trading.state == {OPEN | PAUSED} 이어야 한다."""
    curr = CurrencyType(1)
    trd_id = TradingId('123')
    trd = trading_service.start_new_trading(trd_id, curr)

    trading_service.pause_trading(trd_id)
    trading_service.resume_trading(trd_id)

    trading_service.cancel_trading(trd_id)

    assert trd.state == TradingState.CANCELLED

    # event_writer.
    # -- 거래 없었었으니까.
    event_writer_mock.on_balance_xfer_to.assert_not_called()
    # -- 하지만 취소는 진행.
    event_writer_mock.on_trading_cancelled.assert_called_with(trd_id=trd_id)


@fixture
def cancel_trading_fixture(
        trading_service: TradingService
):
    """취소를 위한 픽스쳐.
    왠만한 거래들이 일어난 상태."""
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')
    cust_e = CustomerId('5')

    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(23))

    trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(9), ItemQty(22))

    trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(8), ItemQty(21))

    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    trading_service.provide_item(trd_id, cust_e, ItemQty(200))

    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(7), ItemQty(30))

    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(8), ItemQty(30))

    trading_service.order_limit_sell(
        trd_id, cust_e, CurrencyAmt(10), ItemQty(13))

    return {
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'cust_d': cust_d,
        'cust_e': cust_e,
        'trading_service': trading_service,
        'balance_service': balance_service,
        'item_count_service': trading_service.item_count_service,
        'trd': trd,
        'trd_id': trd_id,
        'curr': curr,
    }


def test_cancel_trading_01(
        cancel_trading_fixture,
        event_writer_mock
):
    """cancel_trading 테스트 01"""
    # pylint: disable=redefined-outer-name, too-many-statements
    trading_service = cancel_trading_fixture['trading_service']
    balance_service = cancel_trading_fixture['balance_service']
    item_count_service = cancel_trading_fixture['item_count_service']
    trd_id = cancel_trading_fixture['trd_id']
    curr = cancel_trading_fixture['curr']
    cust_a = cancel_trading_fixture['cust_a']
    cust_b = cancel_trading_fixture['cust_b']
    cust_c = cancel_trading_fixture['cust_c']
    cust_d = cancel_trading_fixture['cust_d']
    cust_e = cancel_trading_fixture['cust_e']

    # 취소하기 전에 체크: 물량, 계좌, 수익.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 13
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 37
    assert item_count_service.get(cust_c, trd_id) == 0
    assert item_count_service.get(cust_d, trd_id) == 40
    assert item_count_service.get(cust_e, trd_id) == 187

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 596
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 770
    assert balance_service.get(BalanceType.BALANCE, cust_b, curr) == 634
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1000
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, cust_e, curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_a, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_b, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_c, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_d, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_e, curr) == 0

    assert trd_id in trading_service.tradings

    # 취소.
    trading_service.cancel_trading(trd_id)

    # 취소 후 체크: 물량은 그대로. (아직은 evict전이니까.)
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 13
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 37
    assert item_count_service.get(cust_c, trd_id) == 0
    assert item_count_service.get(cust_d, trd_id) == 40
    assert item_count_service.get(cust_e, trd_id) == 187

    # buy으로 svc-cust에 제출한 금액이 모두 환불되어야 한다.
    # - 체결된 주문이든, 아니든.
    # - 체결된 sale으로 얻은 수익금이 svc-cust에서 사라져야 한다.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 1_000
    assert balance_service.get(BalanceType.BALANCE, cust_b, curr) == 1_000
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, cust_e, curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_a, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_b, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_c, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_d, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_e, curr) == 0

    # trading 매핑도 아직 그대로.
    assert trd_id in trading_service.tradings

    # event_writer.
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_a, curr=1, amt=230, new_amt=1000, new_svc=366,
             why=BalanceXferToCauseTradingCancellation(trd_id='1')),
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_b, curr=1, amt=198, new_amt=832, new_svc=168,
             why=BalanceXferToCauseTradingCancellation(trd_id='1')),
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_b, curr=1, amt=168, new_amt=1000, new_svc=0,
             why=BalanceXferToCauseTradingCancellation(trd_id='1'))
    ])
    event_writer_mock.on_trading_cancelled.assert_called_with(trd_id=trd_id)
