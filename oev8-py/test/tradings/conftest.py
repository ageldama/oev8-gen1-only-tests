from pytest import fixture  # type: ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty


@fixture
def nonono_trading_fixture(trading_service: TradingService):
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_1 = CustomerId('1')
    cust_2 = CustomerId('2')
    cust_3 = CustomerId('3')
    #
    trd = trading_service.start_new_trading(trd_id, curr)
    trading_service.provide_item(trd_id, cust_1, ItemQty(10))
    return trd_id
