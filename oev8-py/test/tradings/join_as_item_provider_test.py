"""TradingService.join_as_item_provider 테스트."""
from unittest.mock import call
from pytest import raises  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.balance import BalanceService
from oev8.typedefs import TradingId, CurrencyType, CustomerId
from oev8.typedefs import CurrencyAmt, ItemQty, BalanceType
from oev8.excs import NotEnoughBalance
from oev8.excs import TradingIsNotFound
from oev8.consts import SERVICE_CUSTOMER
from oev8.values.event_writer import BalanceXferFromCauseSecurityDeposit


def test_with_not_existing_trading_id(
        trading_service: TradingService,
        event_writer_mock
):
    """없는 trading-id에 대해서."""
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    with raises(TradingIsNotFound):
        trading_service.join_as_item_provider(
            cust_a, trd_id, CurrencyAmt(1), ItemQty(1))

    with raises(TradingIsNotFound):
        # 새로 생성되지는 않았겠지.
        trading_service.get_trading(trd_id)

    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_with_not_enough_balance_for_security_deposit(
        trading_service: TradingService,
        event_writer_mock
):
    """없는 trading-id에 대해서."""
    curr = CurrencyType(1)
    curr2 = CurrencyType(2)
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    trading_service.start_new_trading(trd_id, curr)

    balance_service: BalanceService = trading_service.balance_service

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(10))

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr2,
                            CurrencyAmt(100))

    with raises(NotEnoughBalance):
        trading_service.join_as_item_provider(
            cust_a, trd_id, CurrencyAmt(100), ItemQty(1))

    trd = trading_service.get_trading(trd_id)

    assert cust_a not in trd.item_providings

    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 0
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr2) \
        == 0

    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 10
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr2) == 100

    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_ok(
        trading_service: TradingService,
        event_writer_mock
):
    """없는 trading-id에 대해서."""
    curr = CurrencyType(1)
    curr2 = CurrencyType(2)
    trd_id = TradingId('1')
    cust_a = CustomerId('1')

    trading_service.start_new_trading(trd_id, curr)

    balance_service: BalanceService = trading_service.balance_service

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(100))

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr2,
                            CurrencyAmt(100))

    trading_service.join_as_item_provider(
        cust_a, trd_id, CurrencyAmt(100), ItemQty(11))

    trd = trading_service.get_trading(trd_id)

    assert cust_a in trd.item_providings

    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 100
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr2) \
        == 0

    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr2) == 100

    event_writer_mock.on_trading_provide_item.assert_has_calls([
        call(trd_id=trd_id, cust_id=cust_a, qty=11, new_qty=11)
    ])

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_a, curr=curr,
             amt=100, new_amt=0, new_svc=100,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])
