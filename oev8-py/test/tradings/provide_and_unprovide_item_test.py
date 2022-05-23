"""TradingService.provide_item, unprovide_item 테스트."""
from unittest.mock import Mock
from pytest import raises  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.item_count import ItemCountService
from oev8.typedefs import TradingId, ItemQty, CustomerId
from oev8.typedefs import CurrencyType
from oev8.consts import SERVICE_CUSTOMER
from oev8.excs import TradingIsNotFound, TradingIsNotOpened
from oev8.excs import NotAnItemProvider
from oev8.excs import NotEnoughItemProviding


def test_provide_does_not_exist(
        trading_service: TradingService,
        event_writer_mock
):
    """provide_item 아예 없을 때."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')

    # 없는 Trading --> err.
    with raises(TradingIsNotFound):
        trading_service.provide_item(trd_id, cust_a, ItemQty(111))

    event_writer_mock.on_trading_provide_item.assert_not_called()


def test_provide_on_paused(
        trading_service: TradingService,
        event_writer_mock
):
    """provide_item 을 paused된 Trading에 하면 에러."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    # providing on paused Trading --> err.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.provide_item(trd_id, cust_a, ItemQty(1))

    event_writer_mock.on_trading_provide_item.assert_not_called()


def test_provide_on_cancelled(
        trading_service: TradingService,
        event_writer_mock
):
    """provide_item 을 cancelled Trading에 하면 에러."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    #
    trading_service.cancel_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.provide_item(trd_id, cust_a, ItemQty(1))

    event_writer_mock.on_trading_provide_item.assert_not_called()


def test_provide_increases_item_count(
        trading_service: TradingService,
        item_count_service: ItemCountService,
        event_writer_mock
):
    """provide_item은 아이템 수량을 증가시킨다."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    trd = trading_service.get_trading(trd_id)

    item_count_service.inc(cust_a, trd_id, ItemQty(18))

    assert item_count_service.get(cust_a, trd_id) == 18
    assert item_count_service.get(
        SERVICE_CUSTOMER, trd_id) == 0
    assert cust_a not in trd.item_providings

    # 증가: item_providings 와 item_count 은 같지 않을 수 있음.
    assert trading_service.provide_item(trd_id, cust_a,
                                        ItemQty(11)) == 11

    assert item_count_service.get(cust_a, trd_id) == 18 + 11
    assert item_count_service.get(
        SERVICE_CUSTOMER, trd_id) == 0  # no-chg.

    assert trd.item_providings[cust_a] == 11

    event_writer_mock.on_trading_provide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a,
        qty=ItemQty(11), new_qty=ItemQty(11))

    # 증가.
    assert trading_service.provide_item(
        trd_id, cust_a, ItemQty(18)) == 18 + 11

    assert item_count_service.get(cust_a, trd_id) == 47
    assert item_count_service.get(
        SERVICE_CUSTOMER, trd_id) == 0  # no-chg.

    assert trd.item_providings[cust_a] == 29

    event_writer_mock.on_trading_provide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a,
        qty=ItemQty(18), new_qty=ItemQty(29))


def test_unprovide_does_not_exist(
        trading_service: TradingService,
        event_writer_mock
):
    """unprovide_item 아예 없을 때."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')

    # 없는 Trading --> err.
    with raises(TradingIsNotFound):
        trading_service.unprovide_item(trd_id, cust_a, ItemQty(111))

    event_writer_mock.on_trading_unprovide_item.assert_not_called()


def test_unprovide_on_paused(
        trading_service: TradingService,
        event_writer_mock
):
    """unprovide_item 을 paused된 Trading에 하면 에러."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    # providing on paused Trading --> err.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.unprovide_item(trd_id, cust_a, ItemQty(1))

    event_writer_mock.on_trading_unprovide_item.assert_not_called()


def test_unprovide_on_cancelled(
        trading_service: TradingService,
        event_writer_mock
):
    """unprovide_item 을 cancelled Trading에 하면 에러."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    #
    trading_service.cancel_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.unprovide_item(trd_id, cust_a, ItemQty(1))

    event_writer_mock.on_trading_unprovide_item.assert_not_called()


def test_unprovide_for_non_provider(
        trading_service: TradingService,
        item_count_service: ItemCountService,
        event_writer_mock
):
    """item-provider이 아닌, 그냥 아이템소유자(reseller등)은 unprovide 불가."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    trd = trading_service.get_trading(trd_id)

    #
    item_count_service.inc(cust_a, trd_id, ItemQty(100))
    assert item_count_service.get(cust_a, trd_id) == 100
    assert cust_a not in trd.item_providings

    #
    with raises(NotAnItemProvider):
        trading_service.unprovide_item(trd_id, cust_a, ItemQty(20))

    assert item_count_service.get(cust_a, trd_id) == 100  # no-chg.

    event_writer_mock.on_trading_unprovide_item.assert_not_called()


def test_unprovide_01(
        trading_service: TradingService,
        item_count_service: ItemCountService,
        event_writer_mock
):
    """item-provider이 성공하면."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    trd = trading_service.get_trading(trd_id)

    # 적립.
    assert trading_service.provide_item(
        trd_id, cust_a, ItemQty(10)) == 10
    assert trading_service.provide_item(
        trd_id, cust_a, ItemQty(18)) == 28

    assert item_count_service.get(cust_a, trd_id) == 28

    # unprovidings
    assert trading_service.unprovide_item(
        trd_id, cust_a, ItemQty(11)) == 17

    event_writer_mock.on_trading_unprovide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a, decrease_qty=ItemQty(11),
        new_qty=ItemQty(17))

    assert item_count_service.get(cust_a, trd_id) == 17

    assert trading_service.unprovide_item(
        trd_id, cust_a, ItemQty(13)) == 4

    assert item_count_service.get(cust_a, trd_id) == 4

    assert trd.item_providings[cust_a] == 4

    event_writer_mock.on_trading_unprovide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a,
        decrease_qty=ItemQty(13), new_qty=ItemQty(4))


def test_unprovide_only_on_providing_counts(
        trading_service: TradingService,
        item_count_service: ItemCountService,
        event_writer_mock: Mock
):
    """item-provider은 제공 물량에 대해서만 가능."""

    trd_id = TradingId('123')
    cust_a = CustomerId('1')
    curr = CurrencyType(1)

    # start new trading
    trading_service.start_new_trading(trd_id, curr)

    # 적립.
    item_count_service.inc(cust_a, trd_id, ItemQty(1))

    assert trading_service.provide_item(
        trd_id, cust_a, ItemQty(11)) == 11

    assert trading_service.provide_item(
        trd_id, cust_a, ItemQty(22)) == 33

    assert item_count_service.get(cust_a, trd_id) == 1 + 11 + 22

    # unprovidings.
    assert trading_service.unprovide_item(
        trd_id, cust_a, ItemQty(11)) == 22

    event_writer_mock.on_trading_unprovide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a,
        decrease_qty=ItemQty(11), new_qty=ItemQty(22))

    assert item_count_service.get(cust_a, trd_id) == 1 + 22

    assert trading_service.unprovide_item(
        trd_id, cust_a, ItemQty(22)) == 0

    event_writer_mock.on_trading_unprovide_item.assert_called_with(
        trd_id=trd_id, cust_id=cust_a,
        decrease_qty=ItemQty(22), new_qty=ItemQty(0))

    assert item_count_service.get(cust_a, trd_id) == 1

    event_writer_mock.on_trading_unprovide_item.reset_mock()

    with raises(NotEnoughItemProviding):
        trading_service.unprovide_item(trd_id, cust_a, ItemQty(1))

    event_writer_mock.on_trading_unprovide_item.assert_not_called()
