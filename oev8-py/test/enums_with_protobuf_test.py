import oev8_pb2
from oev8.typedefs import BalanceType, OrderSide, OrderType
from oev8.typedefs import TradingState, OrderMakerTaker, OrderOption


def test_check_OrderSide():
    oev8_pb2.OrderSide.SIDE_BUY == \
        OrderSide.BUY.value
    oev8_pb2.OrderSide.SIDE_SELL == \
        OrderSide.SELL.value


def test_check_OrderType():
    oev8_pb2.OrderType.ORDER_TYPE_LIMIT == \
        OrderType.LIMIT.value
    oev8_pb2.OrderType.ORDER_TYPE_MARKET == \
        OrderType.MARKET.value


def test_check_OrderOption():
    oev8_pb2.OrderOption.ORDER_OPTION_NONE == \
        OrderOption.NONE.value
    oev8_pb2.OrderOption.ORDER_OPTION_IMMEDIATE_OR_CANCEL == \
        OrderOption.IMMEDIATE_OR_CANCEL.value
    oev8_pb2.OrderOption.ORDER_OPTION_FILL_OR_KILL == \
        OrderOption.FILL_OR_KILL.value


def test_check_OrderMakerTaker():
    oev8_pb2.OrderMakerTaker.ORDER_MAKER == \
        OrderMakerTaker.MAKER.value
    oev8_pb2.OrderMakerTaker.ORDER_TAKER == \
        OrderMakerTaker.TAKER.value


def test_check_BalanceType_enums():
    oev8_pb2.BalanceType.BALANCE_JUST \
        == BalanceType.BALANCE.value
    oev8_pb2.BalanceType.BALANCE_EARNING \
        == BalanceType.EARNING.value


def test_check_TradingState():
    assert oev8_pb2.TradingState.TRADING_STATE_OPENED == \
        TradingState.OPEN.value
    assert oev8_pb2.TradingState.TRADING_STATE_FINISHED == \
        TradingState.COMPLETED.value
    assert oev8_pb2.TradingState.TRADING_STATE_PAUSED == \
        TradingState.PAUSED.value
    assert oev8_pb2.TradingState.TRADING_STATE_CANCELLED == \
        TradingState.CANCELLED.value
