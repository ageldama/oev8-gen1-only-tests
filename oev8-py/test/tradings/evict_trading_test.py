"""TradingService.evict_trading 테스트."""
from unittest.mock import call
from pytest import fixture, raises  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import TradingId, CurrencyType
from oev8.excs import TradingIsNotEvictable, TradingIsNotFound
from oev8.typedefs import CurrencyAmt, CustomerId, BalanceType, ItemQty
from oev8.consts import SERVICE_CUSTOMER


def test_evict_on_opened(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """OPEN 상태의 trading은 불가."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)

    trading_service.start_new_trading(trd_id, curr)

    with raises(TradingIsNotEvictable):
        trading_service.evict_trading(trd_id)

    event_writer_mock.on_item_count_delete_by_trading.assert_not_called()
    event_writer_mock.on_trading_evicted.assert_not_called()

    trading_clockwork_service.unregist.assert_not_called()


def test_evict_on_paused(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """PAUSED 상태의 trading은 불가."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)

    trading_service.start_new_trading(trd_id, curr)
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotEvictable):
        trading_service.evict_trading(trd_id)

    event_writer_mock.on_item_count_delete_by_trading.assert_not_called()
    event_writer_mock.on_trading_evicted.assert_not_called()

    trading_clockwork_service.unregist.assert_not_called()


def test_evict_on_finalized(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """COMPLETED 상태의 trading은 가능."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)

    trading_service.start_new_trading(trd_id, curr)
    trading_service.finalize_trading(trd_id)

    # BEFORE
    assert trd_id in trading_service.tradings

    trading_service.evict_trading(trd_id)

    # AFTER: trading 매핑 삭제.
    assert trd_id not in trading_service.tradings

    event_writer_mock.on_item_count_delete_by_trading.assert_called_with(
        trd_id)
    event_writer_mock.on_trading_evicted.assert_called_with(
        trd_id=trd_id)

    trading_clockwork_service.unregist.assert_has_calls([
        call(trd_id)])


def test_evict_on_cancelled(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """CANCELLED 상태의 trading은 가능."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)

    trading_service.start_new_trading(trd_id, curr)
    trading_service.cancel_trading(trd_id)

    trading_service.evict_trading(trd_id)

    event_writer_mock.on_item_count_delete_by_trading.assert_called_with(
        trd_id)
    event_writer_mock.on_trading_evicted.assert_called_with(
        trd_id=trd_id)

    trading_clockwork_service.unregist.assert_has_calls([
        call(trd_id)])


def test_evict_on_not_found(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """있는 trading만 evict 가능."""
    trd_id = TradingId('1')

    with raises(TradingIsNotFound):
        trading_service.evict_trading(trd_id)

    event_writer_mock.on_item_count_delete_by_trading.assert_not_called()
    event_writer_mock.on_trading_evicted.assert_not_called()

    trading_clockwork_service.unregist.assert_not_called()


@fixture
def one_messy_state(trading_service: TradingService):
    """거래들이 있은 후의 상태."""
    # pylint: disable=too-many-locals
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    #
    trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    # buy-1 by cust_a
    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(100))

    trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    # sell-1 by cust_b
    trading_service.provide_item(trd_id, cust_b, ItemQty(20))
    trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(7), ItemQty(5))

    # resell-1 by cust_a
    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(20), ItemQty(5))

    # buy-2 by cust_c
    balance_service.deposit(BalanceType.BALANCE, cust_c,
                            curr, CurrencyAmt(100))
    trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(23), ItemQty(3))

    #
    return {
        'trd_id': trd_id,
        'curr': curr,
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'trading_service': trading_service,
        'balance_service': balance_service,
        'item_count_service': trading_service.item_count_service
    }


def test_evict_on_finalized_02(
        one_messy_state,
        event_writer_mock
):
    """finalized된 trading을 정리해도 모두 삭제: 하지만 수익 등은 보전해야함."""
    # pylint: disable=redefined-outer-name

    trd_id = one_messy_state['trd_id']
    curr = one_messy_state['curr']
    cust_a = one_messy_state['cust_a']
    cust_b = one_messy_state['cust_b']
    cust_c = one_messy_state['cust_c']
    trading_service = one_messy_state['trading_service']
    balance_service = one_messy_state['balance_service']
    item_count_service = one_messy_state['item_count_service']

    trading_service.finalize_trading(trd_id)
    trading_service.evict_trading(trd_id)

    # 잔고, 수익 등은 보전.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 50  # 사용금액 그대로.
    assert balance_service.get(
        BalanceType.EARNING, cust_a, curr) == 69  # 수익금액 그대로.
    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 0  # 사용금액 그대로.
    assert balance_service.get(
        BalanceType.EARNING, cust_b, curr) == 50  # 수익금액 그대로.
    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 31  # 사용금액 그대로.
    assert balance_service.get(
        BalanceType.EARNING, cust_c, curr) == 0  # 수익금액 그대로.

    # 하지만 아이템 관련은 삭제.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
    assert item_count_service.get(cust_a, trd_id) == 0
    assert item_count_service.get(cust_b, trd_id) == 0
    assert item_count_service.get(cust_c, trd_id) == 0

    #
    event_writer_mock.on_item_count_delete_by_trading(trd_id)
    event_writer_mock.on_trading_evicted(trd_id)


def test_evict_on_cancelled_02(
        one_messy_state,
        event_writer_mock
):
    """cancelled trading을 정리해도 모두 삭제: 수익 등도 모두."""
    # pylint: disable=redefined-outer-name

    trd_id = one_messy_state['trd_id']
    curr = one_messy_state['curr']
    cust_a = one_messy_state['cust_a']
    cust_b = one_messy_state['cust_b']
    cust_c = one_messy_state['cust_c']
    trading_service = one_messy_state['trading_service']
    balance_service = one_messy_state['balance_service']
    item_count_service = one_messy_state['item_count_service']

    trading_service.cancel_trading(trd_id)
    trading_service.evict_trading(trd_id)

    # 잔고, 수익 등 삭제.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 100  # 원래 잔고.
    assert balance_service.get(
        BalanceType.EARNING, cust_a, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_b, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 100  # 원래 잔고.
    assert balance_service.get(
        BalanceType.EARNING, cust_c, curr) == 0

    #  아이템 관련도 삭제.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
    assert item_count_service.get(cust_a, trd_id) == 0
    assert item_count_service.get(cust_b, trd_id) == 0
    assert item_count_service.get(cust_c, trd_id) == 0

    #
    event_writer_mock.on_item_count_delete_by_trading(trd_id)
    event_writer_mock.on_trading_evicted(trd_id)
