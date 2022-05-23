from pytest import raises  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.excs import NotEnoughItemCount, ItemQtyShouldBeZeroOrPositive


def test_loaded(item_count_service):
    assert item_count_service


def test_set_and_get(item_count_service):
    cust_id = '123'
    trading = '1'
    assert item_count_service.get(cust_id, trading) == 0
    assert item_count_service.set(cust_id, trading, 123) == 123
    assert item_count_service.get(cust_id, trading) == 123
    assert item_count_service.set(cust_id, trading, 10) == 10
    assert item_count_service.get(cust_id, trading) == 10
    with raises(ItemQtyShouldBeZeroOrPositive):
        item_count_service.set(cust_id, trading, -1)


def test_inc(item_count_service):
    cust = '123'
    trading = '1'
    trading2 = '2'
    assert item_count_service.get(cust, trading) == 0
    assert item_count_service.inc(cust, trading, 100) == 100
    assert item_count_service.inc(cust, trading, 23) == 123
    with raises(ItemQtyShouldBeZeroOrPositive):
        item_count_service.inc(cust, trading, -1)
    assert item_count_service.get(cust, trading2) == 0


def test_dec(item_count_service):
    cust = '123'
    trading = '1'
    trading2 = '2'
    with raises(ItemQtyShouldBeZeroOrPositive):
        item_count_service.dec(cust, trading, -1)
    with raises(NotEnoughItemCount):
        item_count_service.dec(cust, trading, 1)
    assert item_count_service.inc(cust, trading, 12) == 12
    assert item_count_service.dec(cust, trading, 10) == 2
    assert item_count_service.dec(cust, trading, 2) == 0
    assert item_count_service.inc(cust, trading2, 12) == 12
    assert item_count_service.get(cust, trading) == 0


def test_delete_by_trading(item_count_service):
    cust = '123'
    cust2 = '456'
    trd = '1'
    trd2 = '2'
    item_count_service.inc(cust, trd, 100)
    item_count_service.inc(cust, trd2, 200)
    item_count_service.inc(cust2, trd, 1)
    item_count_service.inc(cust2, trd2, 2)
    assert not item_count_service.delete_by_trading('3')
    assert item_count_service.delete_by_trading(trd)
    assert item_count_service.get(cust, trd) == 0
    assert item_count_service.get(cust2, trd) == 0
    assert item_count_service.get(cust, trd2) == 200
    assert item_count_service.get(cust2, trd2) == 2


def test_delete_by_customer(item_count_service):
    cust = '123'
    cust2 = '456'
    trd = '1'
    trd2 = '2'
    item_count_service.inc(cust, trd, 100)
    item_count_service.inc(cust, trd2, 200)
    item_count_service.inc(cust2, trd, 1)
    item_count_service.inc(cust2, trd2, 2)
    assert not item_count_service.delete_by_customer('3')
    assert item_count_service.delete_by_customer(cust2)
    assert item_count_service.get(cust2, trd) == 0
    assert item_count_service.get(cust2, trd2) == 0
    assert item_count_service.get(cust, trd) == 100
    assert item_count_service.get(cust, trd2) == 200


def test_xfer_from_to(item_count_service):
    cust = '123'
    cust2 = '456'
    trd = '1'
    trd2 = '2'
    # setup
    assert item_count_service.inc(cust, trd, 100) == 100
    assert item_count_service.inc(cust2, trd, 123) == 123
    # xfer_from
    assert item_count_service.xfer_from(cust, trd, 99) == (1, 99)
    assert item_count_service.xfer_from(cust2, trd, 23) == (100, 99 + 23)
    assert item_count_service.get(SERVICE_CUSTOMER, trd) == 99 + 23
    assert item_count_service.get(SERVICE_CUSTOMER, trd2) == 0
    # xfer_to
    assert item_count_service.xfer_to(cust, trd, 99) == (100, 23)
    assert item_count_service.xfer_to(cust2, trd, 23) == (123, 0)
    assert item_count_service.get(cust, trd) == 100
    assert item_count_service.get(cust2, trd) == 123
    assert item_count_service.get(SERVICE_CUSTOMER, trd) == 0
    #
    with raises(NotEnoughItemCount):
        item_count_service.xfer_from(cust, trd2, 100)
    assert item_count_service.get(cust, trd) == 100
    assert item_count_service.get(cust, trd2) == 0
    #
    with raises(NotEnoughItemCount):
        item_count_service.xfer_to(cust, trd, 100)
    assert item_count_service.get(SERVICE_CUSTOMER, trd) == 0
