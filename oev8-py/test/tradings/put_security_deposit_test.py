"""TradingService.put_security_deposit 테스트."""
from pytest import raises  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.balance import BalanceService
from oev8.typedefs import TradingId, CustomerId, CurrencyAmt, CurrencyType
from oev8.typedefs import BalanceType
from oev8.values.event_writer import BalanceXferFromCauseSecurityDeposit
from oev8.excs import TradingIsNotFound, TradingIsNotOpened
from oev8.excs import NotEnoughBalance


def test_put_security_deposit_on_non_existing_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """없는 Trading에."""

    trd_id = TradingId('1')
    cust_a = CustomerId('123')
    amt = CurrencyAmt(1_000)

    with raises(TradingIsNotFound):
        trading_service.put_security_deposit(trd_id, cust_a, amt)

    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_put_security_deposit_on_cancelled_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """취소된 Trading에."""

    trd_id = TradingId('1')
    curr = CurrencyType(111)
    cust_a = CustomerId('123')
    amt = CurrencyAmt(1_000)

    trading_service.start_new_trading(trd_id, curr)
    trading_service.cancel_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.put_security_deposit(trd_id, cust_a, amt)

    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_put_security_deposit_on_finalized_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """완료된 Trading에."""

    trd_id = TradingId('1')
    curr = CurrencyType(111)
    cust_a = CustomerId('123')
    amt = CurrencyAmt(1_000)

    trading_service.start_new_trading(trd_id, curr)
    trading_service.finalize_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.put_security_deposit(trd_id, cust_a, amt)

    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_put_security_deposit_with_not_enough_balance(
        trading_service: TradingService,
        event_writer_mock
):
    """완료된 Trading에."""

    trd_id = TradingId('1')
    curr = CurrencyType(111)
    cust_a = CustomerId('123')
    amt = CurrencyAmt(1_000)

    trading_service.start_new_trading(trd_id, curr)

    with raises(NotEnoughBalance):
        trading_service.put_security_deposit(trd_id, cust_a, amt)

    event_writer_mock.on_balance_xfer_from.assert_not_called()


def test_put_security_deposit_01(
        trading_service: TradingService,
        balance_service: BalanceService,
        event_writer_mock
):
    """완료된 Trading에."""

    trd_id = TradingId('1')
    curr = CurrencyType(111)
    cust_a = CustomerId('123')
    amt = CurrencyAmt(1_000)

    trading_service.start_new_trading(trd_id, curr)

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr, amt)

    trading_service.put_security_deposit(trd_id, cust_a, amt)

    event_writer_mock.on_balance_xfer_from.assert_called_with(
        balance_type=BalanceType.BALANCE, cust_id=cust_a, curr=curr,
        amt=amt, new_amt=0, new_svc=amt,
        why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id)
    )
