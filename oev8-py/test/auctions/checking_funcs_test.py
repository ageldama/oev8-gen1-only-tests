from pytest import raises  # type:ignore
from oev8.funcs.tradings import chk_not_existing_trading_id_auction, \
    chk_trading_id_exists_auction, \
    chk_auction_buying_price, \
    chk_auction_buying_order_option, \
    chk_is_selling_auction
from oev8.values.auctions import Auction
from oev8.typedefs import OrderOption, AuctionSide
from oev8.excs import ExistingTradingId, TradingIsNotFound, \
    UnsatisfyingAuctionBidPrice, UnsupportedOrderOption, NotCertainAuctionSide


def test_chk_not_existing_trading_id_auction():
    chk_not_existing_trading_id_auction('123', {})

    with raises(ExistingTradingId):
        chk_not_existing_trading_id_auction('123',
                                            {'123': Auction()})


def test_chk_trading_id_exists_auction():
    chk_trading_id_exists_auction('123', {'123': Auction()})

    with raises(TradingIsNotFound):
        chk_trading_id_exists_auction('123', {})


def test_chk_auction_buying_price():
    trd_id = '123'
    auction = Auction(price=1_000)

    # given `price` is lesser.
    with raises(UnsatisfyingAuctionBidPrice):
        chk_auction_buying_price(trd_id, 123, auction)

    # equals.
    chk_auction_buying_price(trd_id, 1_000, auction)

    # greater.
    chk_auction_buying_price(trd_id, 1_000_000, auction)


def test_chk_auction_buying_order_option():
    trd_id = '123'

    chk_auction_buying_order_option(trd_id, OrderOption.NONE)

    chk_auction_buying_order_option(trd_id, OrderOption.FILL_OR_KILL)

    with raises(UnsupportedOrderOption):
        chk_auction_buying_order_option(
            trd_id, OrderOption.IMMEDIATE_OR_CANCEL)


def test_chk_is_selling_auction():
    trd_id = '123'

    chk_is_selling_auction(
        trd_id, Auction(auction_side=AuctionSide.SELLING))

    with raises(NotCertainAuctionSide):
        chk_is_selling_auction(
            trd_id, Auction(auction_side=AuctionSide.BUYING))
