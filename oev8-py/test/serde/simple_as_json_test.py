"oev8.values.event_writer 클래스들 JSON serializations."
from json import loads
from pytest import mark
from oev8_pb2 import \
    ERR_ITEM_QTY_SHOULD_BE_ZERO_OR_POSITIVE, \
    ERR_ITEM_QTY_SHOULD_BE_POSITIVE, \
    ERR_CURRENCY_AMT_SHOULD_BE_ZERO_OR_POSITIVE, \
    ERR_CURRENCY_AMT_SHOULD_BE_POSITIVE, \
    ERR_ORDER_ID_NOT_FOUND, \
    ERR_EXISTING_ORDER_ID, \
    ERR_NOT_ENOUGH_ITEM_COUNT, \
    ERR_ORDER_IS_FULFILLED, \
    ERR_ORDER_IS_CANCELLED, \
    ERR_TRADING_IS_NOT_OPENED, \
    ERR_TRADING_IS_NOT_PAUSED, \
    ERR_TRADING_IS_NOT_CANCELLABLE, \
    ERR_TRADING_IS_NOT_COMPLETABLE, \
    ERR_TRADING_IS_NOT_EVICTABLE, \
    ERR_TRADING_IS_NOT_FOUND, \
    ERR_EXISTING_TRADING_ID, \
    ERR_NOT_ENOUGH_BALANCE, \
    ERR_NOT_ITEM_PROVIDER, \
    ERR_NOT_ENOUGH_ITEM_PROVIDING
from oev8.excs import ItemQtyShouldBeZeroOrPositive, \
    ItemQtyShouldBePositive, \
    CurrencyAmtShouldBeZeroOrPositive, \
    CurrencyAmtShouldBePositive, \
    OrderIdNotFound, ExistingOrderId, \
    NotEnoughItemCount, \
    OrderOfferLineIsFulfilled, OrderOfferLineIsCancelled, \
    TradingIsNotOpened, TradingIsNotPaused, \
    TradingIsNotCancellable, TradingIsNotCompletable, \
    TradingIsNotEvictable, TradingIsNotFound, \
    ExistingTradingId, NotEnoughBalance, \
    NotAnItemProvider, NotEnoughItemProviding
from test.testsup import rand_1mil, rand_balance_type2, \
    rand_order_maker_taker2, rand_trading_state2, rand_curr


JSON_SERABLE_CLASSES = (
    # class, attrs, consts
    # CodedError
    (ItemQtyShouldBeZeroOrPositive,
     [('qty', rand_1mil,)],
     {'err_code': ERR_ITEM_QTY_SHOULD_BE_ZERO_OR_POSITIVE}),
    (ItemQtyShouldBePositive,
     [('qty', rand_1mil,)],
     {'err_code': ERR_ITEM_QTY_SHOULD_BE_POSITIVE}),
    (CurrencyAmtShouldBeZeroOrPositive,
     [('amt', rand_1mil,)],
     {'err_code': ERR_CURRENCY_AMT_SHOULD_BE_ZERO_OR_POSITIVE}),
    (CurrencyAmtShouldBePositive,
     [('amt', rand_1mil,)],
     {'err_code': ERR_CURRENCY_AMT_SHOULD_BE_POSITIVE}),
    (OrderIdNotFound,
     [('ord_id', rand_1mil), ('what', rand_order_maker_taker2,)],
     {'err_code': ERR_ORDER_ID_NOT_FOUND}),
    (ExistingOrderId,
     [('ord_id', rand_1mil,)],
     {'err_code': ERR_EXISTING_ORDER_ID}),
    (NotEnoughItemCount,
     [('cust_id', rand_1mil,),
      ('current_qty', rand_1mil,),
      ('requested_qty', rand_1mil,)],
     {'err_code': ERR_NOT_ENOUGH_ITEM_COUNT}),
    (OrderOfferLineIsFulfilled,
     [('ord_id', rand_1mil,)],
     {'err_code': ERR_ORDER_IS_FULFILLED}),
    (OrderOfferLineIsCancelled,
     [('ord_id', rand_1mil,)],
     {'err_code': ERR_ORDER_IS_CANCELLED}),
    (TradingIsNotOpened,
     [('trd_id', rand_1mil,),
      ('current_state', rand_trading_state2,)],
     {'err_code': ERR_TRADING_IS_NOT_OPENED}),
    (TradingIsNotPaused,
     [('trd_id', rand_1mil,),
      ('current_state', rand_trading_state2,)],
     {'err_code': ERR_TRADING_IS_NOT_PAUSED}),
    (TradingIsNotCancellable,
     [('trd_id', rand_1mil,),
      ('current_state', rand_trading_state2,)],
     {'err_code': ERR_TRADING_IS_NOT_CANCELLABLE}),
    (TradingIsNotCompletable,
     [('trd_id', rand_1mil,),
      ('current_state', rand_trading_state2,)],
     {'err_code': ERR_TRADING_IS_NOT_COMPLETABLE}),
    (TradingIsNotEvictable,
     [('trd_id', rand_1mil),
      ('current_state', rand_trading_state2,)],
     {'err_code': ERR_TRADING_IS_NOT_EVICTABLE}),
    (TradingIsNotFound,
     [('trd_id', rand_1mil,)],
     {'err_code': ERR_TRADING_IS_NOT_FOUND}),
    (ExistingTradingId,
     [('trd_id', rand_1mil)],
     {'err_code': ERR_EXISTING_TRADING_ID}),
    (NotEnoughBalance,
     [('balance_type', rand_balance_type2,),
      ('cust_id', rand_1mil,),
      ('curr', rand_curr,),
      ('current_amt', rand_1mil,),
      ('requested_amt', rand_1mil,)],
     {'err_code': ERR_NOT_ENOUGH_BALANCE}),
    (NotAnItemProvider,
     [('cust_id', rand_1mil,)],
     {'err_code': ERR_NOT_ITEM_PROVIDER}),
    (NotEnoughItemProviding,
     [('cust_id', rand_1mil,),
      ('current_qty', rand_1mil,),
      ('requested_qty', rand_1mil,)],
     {'err_code': ERR_NOT_ENOUGH_ITEM_PROVIDING}),
)


@mark.parametrize("cls,attr_names,consts", JSON_SERABLE_CLASSES)
def test_json_serable_class(cls, attr_names, consts):
    "attr_names, consts에 따라서 원하는 형태로 JSON을 만드는지?"
    params = {}
    expectations = {}

    for (attr_name, attr_gen,) in attr_names:
        rand_val = attr_gen()
        if isinstance(rand_val, tuple):
            params[attr_name] = rand_val[0]
            expectations[attr_name] = rand_val[1]
        else:
            params[attr_name] = rand_val
            expectations[attr_name] = rand_val

    for const_name, const_val in consts.items():
        expectations[const_name] = const_val

    #
    inst = cls(**params)
    obj_back = loads(inst.to_json())

    assert obj_back == expectations
