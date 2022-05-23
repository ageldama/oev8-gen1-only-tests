"""oev8.svcs.trading.TradingService 테스트."""
from pytest import raises  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import CustomerId, CurrencyType
from oev8.typedefs import TradingId, ItemQty, TradingState
from oev8.typedefs import BalanceType
from oev8.values.tradings import Trading
from oev8.svcs.trading import TradingService
from oev8.svcs.balance import BalanceService
from oev8.excs import ExistingTradingId, TradingIsNotFound
from oev8.excs import TradingIsNotOpened, TradingIsNotPaused
from oev8.excs import ItemQtyShouldBePositive


def test_load(trading_service):
    """fixture 정상인지?"""
    assert trading_service


def test_start_new_trading(
        trading_service,
        balance_service,
        item_count_service,
        event_writer_mock
):
    """start_new_trading() 테스트."""
    trd_id = '1'
    curr = 1

    trd = trading_service.start_new_trading(trd_id, curr)
    assert trd
    assert isinstance(trd, Trading)
    event_writer_mock.on_trading_new.assert_called_with(trd_id)

    #
    assert balance_service is trading_service.balance_service
    assert item_count_service is trading_service.item_count_service
    assert BalanceService() is not BalanceService()

    # 이미 존재하는 trading_id은 거절.
    event_writer_mock.on_trading_new.reset_mock()
    with raises(ExistingTradingId):
        trading_service.start_new_trading(trd_id, curr)

    event_writer_mock.on_trading_new.assert_not_called()


def test_pause_trading_and_resume_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """TradingService의 pause_trading(), resume_trading() 테스트."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    trd = trading_service.start_new_trading(trd_id, curr)

    # pause_trading: opened 상태일 때만 가능.
    assert trd.state == TradingState.OPEN
    assert trading_service.pause_trading(trd_id) == TradingState.PAUSED
    assert trd.state == TradingState.PAUSED
    event_writer_mock.on_trading_pause.assert_called_with(trd_id)

    # -- 실패시 trd 상태 그대로여야함.
    event_writer_mock.on_trading_pause.reset_mock()
    with raises(TradingIsNotOpened):
        trading_service.pause_trading(trd_id)
    assert trd.state == TradingState.PAUSED
    event_writer_mock.on_trading_pause.assert_not_called()

    # resume_trading: paused 상태일 때만 가능.
    #  -- trd 상태 그대로여야함.
    event_writer_mock.on_trading_resume.reset_mock()
    assert trd.state == TradingState.PAUSED
    assert trading_service.resume_trading(trd_id) == TradingState.OPEN
    assert trd.state == TradingState.OPEN
    event_writer_mock.on_trading_resume.assert_called_with(trd_id)

    # -- 실패시 trd 상태 그대로여야함.
    event_writer_mock.on_trading_resume.reset_mock()
    with raises(TradingIsNotPaused):
        trading_service.resume_trading(trd_id)
    assert trd.state == TradingState.OPEN
    event_writer_mock.on_trading_resume.assert_not_called()


def test_get_trading(
        trading_service: TradingService
):
    """TradingService의 get_trading() 테스트."""
    trd_id = TradingId('1')
    trd_id_nf = TradingId('18')
    curr = CurrencyType(1)
    # get_trading: 있는 trading_id만 가능.
    with raises(TradingIsNotFound):
        trading_service.get_trading(trd_id)
    trd = trading_service.start_new_trading(trd_id, curr)
    got = trading_service.get_trading(trd_id)
    assert trd is got
    with raises(TradingIsNotFound):
        trading_service.get_trading(trd_id_nf)


def test_provide_item(trading_service: TradingService):
    """provide_item() 테스트."""
    trd_id = TradingId('1')
    trd_id_nf = TradingId('2')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_nobody = CustomerId('3')

    # setup
    trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service

    # 존재하는 trading_id만 가능.
    with raises(TradingIsNotFound):
        trading_service.provide_item(trd_id_nf, cust_a, ItemQty(123))

    # qty >= 0
    with raises(ItemQtyShouldBePositive):
        trading_service.provide_item(trd_id, cust_a, ItemQty(-1))

    # cust의 item-count에 증가해야한다. not overwritten.
    assert trading_service.provide_item(trd_id, cust_a, ItemQty(1)) == 1
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_a, curr) == 0
    assert item_count_service.get(cust_a, trd_id) == 1
    # +2
    assert trading_service.provide_item(trd_id, cust_a, ItemQty(2)) == 3
    assert item_count_service.get(cust_a, trd_id) == 3
    assert item_count_service.get(cust_a, trd_id_nf) == 0
    assert item_count_service.get(cust_nobody, trd_id) == 0

    # 그러면서 balance에 변경이 생기면 안됨.
    # -- customer, svc-customer 모두.
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_a, curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, SERVICE_CUSTOMER, curr) == 0

    # 다른 고객이 제공을 동시에 할 수도 있다.
    assert trading_service.provide_item(trd_id, cust_b, ItemQty(100)) == 100
    assert trading_service.provide_item(trd_id, cust_b, ItemQty(8)) == 108

    # 각자의 item_count으로 적립.
    assert item_count_service.get(cust_a, trd_id) == 3
    assert item_count_service.get(cust_b, trd_id) == 108
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    # trading이 opened 상태일 때만.
    trading_service.pause_trading(trd_id)
    with raises(TradingIsNotOpened):
        trading_service.provide_item(trd_id, cust_a, ItemQty(1))
