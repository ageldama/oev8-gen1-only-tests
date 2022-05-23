from copy import deepcopy
from oev8.typedefs import ItemQty, CustomerId, CurrencyAmt, AuctionSide
from oev8.values.auctions import Auction


def test_auction_eq_01():
    a_01 = Auction(cust_id='123', price=456, qty=789,
                   auction_side=AuctionSide.SELLING)

    # cust_id
    a_02 = deepcopy(a_01)
    a_02.cust_id = '1818'

    assert a_02 != a_01

    # price
    a_02 = deepcopy(a_01)
    a_02.price = 1818

    assert a_02 != a_01

    # qty
    a_02 = deepcopy(a_01)
    a_02.qty = 1818

    assert a_02 != a_01

    # auction_side
    a_02 = deepcopy(a_01)
    a_02.auction_side = AuctionSide.BUYING

    assert a_02 != a_01
