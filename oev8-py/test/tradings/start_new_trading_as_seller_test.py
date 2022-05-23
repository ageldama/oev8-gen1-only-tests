"""TradingService.start_new_trading_as_seller 테스트들."""
from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import TradingId, CurrencyType, CustomerId
from oev8.typedefs import CurrencyAmt, ItemQty, BalanceType, OrderOption
from oev8.typedefs import UtcTimestampSecs
from oev8.excs import ExistingTradingId
from oev8.excs import ItemQtyShouldBePositive
from oev8.excs import CurrencyAmtShouldBePositive
from oev8.excs import NotEnoughBalance
from oev8.consts import SERVICE_CUSTOMER
from oev8.values.event_writer import BalanceXferFromCauseSecurityDeposit


def test_not_with_existing_trading_id(
        trading_service: TradingService,
        event_writer_mock
):
    """이미 있는 trading-id은 피해가야함"""
    curr = CurrencyType(1)
    trd_id_exist = TradingId('1')
    cust_a = CustomerId('1')

    trading_service.balance_service.deposit(
        BalanceType.BALANCE, cust_a, curr, CurrencyAmt(10))

    # 하나 빈 Trading 시작.
    trading_service.start_new_trading(trd_id_exist, curr)
    event_writer_mock.on_trading_new.reset_mock()

    # 시도.
    with raises(ExistingTradingId):
        trading_service.start_new_trading_as_seller(
            cust_a, trd_id_exist, curr,
            CurrencyAmt(1), ItemQty(1), CurrencyAmt(1),
            UtcTimestampSecs(0))

    event_writer_mock.on_trading_new.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()


def test_parameter_validation(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """입력 값 validation 안 되면 어떤 일도 일어나면 안됨."""
    curr = CurrencyType(1)
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(10))

    # 시도 #1
    with raises(CurrencyAmtShouldBePositive):
        trading_service.start_new_trading_as_seller(
            cust_a, trd_id, curr,
            CurrencyAmt(0), ItemQty(0), CurrencyAmt(0),
            UtcTimestampSecs(0))

    assert trd_id not in trading_service.tradings
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 0

    event_writer_mock.on_trading_new.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()

    # 시도 #2
    with raises(ItemQtyShouldBePositive):
        trading_service.start_new_trading_as_seller(
            cust_a, trd_id, curr,
            CurrencyAmt(1), ItemQty(0), CurrencyAmt(0),
            UtcTimestampSecs(0))

    assert trd_id not in trading_service.tradings
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 0

    event_writer_mock.on_trading_new.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()

    # 시도 #3
    with raises(CurrencyAmtShouldBePositive):
        trading_service.start_new_trading_as_seller(
            cust_a, trd_id, curr,
            CurrencyAmt(1), ItemQty(1), CurrencyAmt(0),
            UtcTimestampSecs(0))

    assert trd_id not in trading_service.tradings
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 0

    event_writer_mock.on_trading_new.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()

    trading_clockwork_service.regist.assert_not_called()

    # 시도 #4
    trading_service.start_new_trading_as_seller(
        cust_a, trd_id, curr,
        CurrencyAmt(1), ItemQty(3), CurrencyAmt(1),
        UtcTimestampSecs(0))

    assert trd_id in trading_service.tradings
    # 담보금 제시했음.
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10 - 1
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 1

    trd = trading_service.get_trading(trd_id)

    assert item_count_service.get(cust_a, trd_id) == 0  # 제공해서.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 3  # 제공해서.
    assert trd.item_providings[cust_a] == 3

    event_writer_mock.on_trading_new.assert_has_calls([call(trd_id)])

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE, cust_id=cust_a, curr=curr,
             amt=1, new_amt=9, new_svc=1,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])

    event_writer_mock.on_trading_provide_item.assert_has_calls([
        call(trd_id=trd_id, cust_id=cust_a, qty=3, new_qty=3)
    ])

    event_writer_mock.on_trading_limit_sell_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_a,
             price=1, qty=3, option=OrderOption.NONE)
    ])

    trading_clockwork_service.regist.assert_called_once()


def test_not_enough_balance_to_put_security_deposit(
        trading_service: TradingService,
        event_writer_mock,
        trading_clockwork_service
):
    """잔고 부족으로 담보금 제시 불가."""
    curr = CurrencyType(1)
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    balance_service = trading_service.balance_service
    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(10))

    # 시도
    with raises(NotEnoughBalance):
        trading_service.start_new_trading_as_seller(
            cust_a, trd_id, curr,
            CurrencyAmt(100), ItemQty(3), CurrencyAmt(1),
            UtcTimestampSecs(0))
    assert trd_id not in trading_service.tradings
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 0

    event_writer_mock.on_trading_new.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()

    trading_clockwork_service.regist.assert_not_called()


def test_start_new_with_clockwork(
        trading_service: TradingService,
        trading_clockwork_service
):
    """clockwork.trading에 등록하기."""
    curr = CurrencyType(1)
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    balance_service = trading_service.balance_service
    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(10))

    trading_service.start_new_trading_as_seller(
        cust_a, trd_id, curr,
        CurrencyAmt(1), ItemQty(2), CurrencyAmt(3),
        UtcTimestampSecs(1818))

    trading_clockwork_service.regist.assert_has_calls([
        call('1', 1818)])
