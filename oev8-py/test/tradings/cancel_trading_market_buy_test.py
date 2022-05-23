"""TradingService.cancel_trading + order_market_buy 테스트."""
from unittest.mock import call
from pytest import raises, fixture  # type: ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.balance import BalanceService
from oev8.svcs.item_count import ItemCountService
from oev8.typedefs import TradingId, TradingState, CurrencyType
from oev8.typedefs import CustomerId, BalanceType, CurrencyAmt
from oev8.typedefs import ItemQty
from oev8.consts import SERVICE_CUSTOMER
from oev8.excs import TradingIsNotFound, TradingIsNotCancellable
from oev8.values.event_writer import BalanceXferToCauseTradingCancellation


@fixture
def cancel_fixture(
        trading_service: TradingService
):
    """취소를 위한 픽스쳐.
    왠만한 거래들이 일어난 상태."""
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service: BalanceService = \
        trading_service.balance_service
    item_count_service: ItemCountService = \
        trading_service.item_count_service

    # SELL
    trading_service.provide_item(trd_id, cust_a, ItemQty(100))

    oid_sell = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(7), ItemQty(30))

    # BUY
    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(1_000))

    oid_buy = trading_service.order_market_buy(
        trd_id, cust_b, ItemQty(25))

    return {
        'cust_a': cust_a,
        'cust_b': cust_b,
        'oid_sell': oid_sell, 'oid_buy': oid_buy,
        'trading_service': trading_service,
        'balance_service': balance_service,
        'item_count_service': item_count_service,
        'trd': trd,
        'trd_id': trd_id,
        'curr': curr,
    }


def test_cancel_trading_01(
        cancel_fixture
):
    """cancel_trading + order_market_buy 환불 테스트: 단순 매칭 이후."""
    # pylint: disable=redefined-outer-name, too-many-statements
    trading_service = cancel_fixture['trading_service']
    balance_service = cancel_fixture['balance_service']
    item_count_service = cancel_fixture['item_count_service']
    trd_id = cancel_fixture['trd_id']
    curr = cancel_fixture['curr']
    cust_a = cancel_fixture['cust_a']
    cust_b = cancel_fixture['cust_b']

    # 취소하기 전에 체크: 물량, 계좌, 수익.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 5  # 잔여 매물.
    assert item_count_service.get(cust_a, trd_id) == 70
    assert item_count_service.get(cust_b, trd_id) == 25  # 구매 완료.

    # 25-qty * 7-amt = 175-amt :: 구매 대금 --> cust_a의 earning.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 175
    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 825

    assert balance_service.get(
        BalanceType.EARNING, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_a, curr) == 0
    assert balance_service.get(BalanceType.EARNING, cust_b, curr) == 0

    assert trd_id in trading_service.tradings

    # 취소.
    trading_service.cancel_trading(trd_id)

    # 취소 후 체크: 물량은 그대로. (아직은 evict전이니까.)
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 5  # 잔여 매물.
    assert item_count_service.get(cust_a, trd_id) == 70
    assert item_count_service.get(cust_b, trd_id) == 25  # 구매 완료.

    # buy으로 svc-cust에 제출한 금액이 모두 환불되어야 한다.
    # - 체결된 주문이든, 아니든.
    # - 체결된 sale으로 얻은 수익금이 svc-cust에서 사라져야 한다.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 0
    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 1_000


def test_cancel_trading_on_market_buy_w_multiple_matches(
        trading_service: TradingService
):
    """market-buy을 여러건에 매칭이 일어나도록 만들고, cancel_trading 했을 때, buyer에게 환불 테스트."""
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')  # 판매자들
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')  # 구매자들
    cust_d = CustomerId('4')

    trd = trading_service.start_new_trading(trd_id, curr)

    balance_service: BalanceService = \
        trading_service.balance_service

    item_count_service: ItemCountService = \
        trading_service.item_count_service

    # SELL
    trading_service.provide_item(trd_id, cust_a, ItemQty(10))

    trading_service.provide_item(trd_id, cust_b, ItemQty(10))

    oid_sell_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    oid_sell_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(2), ItemQty(10))

    # BUY
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    oid_buy_1 = trading_service.order_market_buy(
        trd_id, cust_c, ItemQty(11))  # [10 x 2-amt, 1 x 5-amt] 매칭.

    assert trd.orders[oid_sell_2].fulfilled  # 2-amt x 10-qty 먼저 fulfill.
    assert not trd.orders[oid_sell_1].fulfilled  # 5-amt x 10-qty 은 잔여.
    # 구매액: 20 + 2 = 25.

    oid_buy_2 = trading_service.order_market_buy(
        trd_id, cust_d, ItemQty(10))  # [9 x 5-amt] 만 매칭되겠지.
    # 구매액: 45.

    # BEFORE
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 25 + 45

    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000 - 25

    assert balance_service.get(
        BalanceType.BALANCE, cust_d, curr) == 1_000 - 45

    # 취소
    trading_service.cancel_trading(trd_id)

    # AFTER: 환불 완료.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0

    # cust_c의 구매는 fulfilled이고 여러건의 sell에 걸쳐 있었음에도 환불 성공.
    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000

    assert balance_service.get(
        BalanceType.BALANCE, cust_d, curr) == 1_000


def test_cancel_trading_on_market_buy_w_no_match(
        trading_service: TradingService
):
    """market-buy 매칭 없을 때, cancel_trading 후 buyer에게 환불 테스트."""
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_c = CustomerId('3')  # 구매자들
    cust_d = CustomerId('4')

    trd = trading_service.start_new_trading(trd_id, curr)

    balance_service: BalanceService = \
        trading_service.balance_service

    # BUY
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    oid_buy_1 = trading_service.order_market_buy(
        trd_id, cust_c, ItemQty(11))  # [10 x 2-amt, 1 x 5-amt] 매칭.

    oid_buy_2 = trading_service.order_market_buy(
        trd_id, cust_d, ItemQty(10))  # [9 x 5-amt] 만 매칭되겠지.

    # BEFORE: 이체 없음.
    # 시장가 구매는 매칭되어야만 이체하니까.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000

    assert balance_service.get(
        BalanceType.BALANCE, cust_d, curr) == 1_000

    # 취소
    trading_service.cancel_trading(trd_id)

    # AFTER: 환불 완료 -- 변화 없음.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000

    assert balance_service.get(
        BalanceType.BALANCE, cust_d, curr) == 1_000
