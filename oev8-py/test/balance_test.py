from pytest import raises  # type: ignore
from oev8.typedefs import BalanceType
from oev8.consts import SERVICE_CUSTOMER
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBeZeroOrPositive


def test_loaded(balance_service):
    assert balance_service


def test_get_and_set(balance_service):
    bal_type = BalanceType.BALANCE
    cust = str(123)
    cust2 = str(456)
    curr = 1
    curr2 = 2
    #
    assert balance_service.get(bal_type, cust, curr) == 0
    assert balance_service.set(bal_type, cust, curr, 100) == 100
    assert balance_service.get(bal_type, cust, curr) == 100
    assert balance_service.get(bal_type, cust2, curr) == 0
    assert balance_service.get(bal_type, cust, curr2) == 0
    with raises(CurrencyAmtShouldBeZeroOrPositive):
        balance_service.set(bal_type, cust, curr, -1)


def test_deposit(balance_service):
    bal_type = BalanceType.BALANCE
    cust = str(123)
    cust2 = str(456)
    curr = 1
    curr2 = 2
    assert balance_service.get(bal_type, cust, curr) == 0
    assert balance_service.deposit(bal_type, cust, curr, 23) == 23
    assert balance_service.deposit(bal_type, cust, curr, 100) == 123
    assert balance_service.get(bal_type, cust, curr) == 123
    assert balance_service.get(bal_type, cust2, curr) == 0
    assert balance_service.get(bal_type, cust, curr2) == 0
    with raises(CurrencyAmtShouldBeZeroOrPositive):
        balance_service.deposit(bal_type, cust, curr, -1)


def test_withdraw(balance_service):
    bal_type = BalanceType.BALANCE
    cust = str(123)
    cust2 = str(456)
    curr = 1
    curr2 = 2
    balance_service.deposit(bal_type, cust, curr, 100)
    balance_service.deposit(bal_type, cust2, curr2, 789)
    assert balance_service.withdraw(bal_type, cust, curr, 1) == 99
    assert balance_service.get(bal_type, cust, curr) == 99
    assert balance_service.get(bal_type, cust, curr2) == 0
    assert balance_service.get(bal_type, cust2, curr2) == 789
    assert balance_service.withdraw(bal_type, cust, curr, 99) == 0
    assert balance_service.get(bal_type, cust, curr) == 0
    with raises(NotEnoughBalance):
        balance_service.withdraw(bal_type, cust, curr, 1)
    with raises(CurrencyAmtShouldBeZeroOrPositive):
        balance_service.withdraw(bal_type, cust, curr, -1)


def test_separated_earnings(balance_service):
    bal_type = BalanceType.BALANCE
    bal_type2 = BalanceType.EARNING
    cust = str(123)
    curr = 1
    #
    assert balance_service.set(bal_type2, cust, curr, 1_000) == 1_000
    assert balance_service.get(bal_type2, cust, curr) == 1_000
    assert balance_service.get(bal_type, cust, curr) == 0


def test_delete_by_currency(balance_service):
    bal_type = BalanceType.BALANCE
    cust = str(123)
    cust2 = str(456)
    curr = 1
    curr2 = 2
    # setup
    balance_service.deposit(bal_type, cust, curr, 100)
    balance_service.deposit(bal_type, cust, curr2, 200)
    balance_service.deposit(bal_type, cust2, curr, 1)
    balance_service.deposit(bal_type, cust2, curr2, 2)
    #
    assert not balance_service.delete_by_currency(3)
    assert balance_service.delete_by_currency(curr)
    assert balance_service.get(bal_type, cust, curr) == 0
    assert balance_service.get(bal_type, cust2, curr) == 0
    assert balance_service.get(bal_type, cust, curr2) == 200
    assert balance_service.get(bal_type, cust2, curr2) == 2


def test_delete_by_customer(balance_service):
    bal_type = BalanceType.BALANCE
    cust = str(123)
    cust2 = str(456)
    curr = 1
    curr2 = 2
    # setup
    balance_service.deposit(bal_type, cust, curr, 100)
    balance_service.deposit(bal_type, cust, curr2, 200)
    balance_service.deposit(bal_type, cust2, curr, 1)
    balance_service.deposit(bal_type, cust2, curr2, 2)
    #
    assert not balance_service.delete_by_customer(3)
    assert balance_service.delete_by_customer(cust2)
    assert balance_service.get(bal_type, cust2, curr) == 0
    assert balance_service.get(bal_type, cust2, curr2) == 0
    assert balance_service.get(bal_type, cust, curr) == 100
    assert balance_service.get(bal_type, cust, curr2) == 200


def test_xfer_from_to(balance_service):
    cust = str(123)
    cust2 = str(456)
    curr = 1
    # setup
    balance_service.deposit(BalanceType.BALANCE, cust, curr, 100)
    balance_service.deposit(BalanceType.BALANCE, cust2, curr, 23)
    # xfer_from
    assert balance_service.get(BalanceType.BALANCE, cust, curr) == 100
    assert balance_service.get(BalanceType.EARNING, cust, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, cust2, curr) == 23
    assert balance_service.xfer_from(BalanceType.BALANCE, cust, curr, 100) \
        == (0, 100)  # (cust, SERVICE_CUSTOMER)
    assert balance_service.get(BalanceType.BALANCE, cust, curr) == 0
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 100
    assert balance_service.xfer_from(BalanceType.BALANCE, cust2, curr, 21) \
        == (2, 121)  # (cust2, SERVICE_CUSTOMER)
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 121
    assert balance_service.get(BalanceType.EARNING, SERVICE_CUSTOMER, curr) \
        == 0
    # xfer_to
    assert balance_service.xfer_to(BalanceType.BALANCE, cust, curr, 50) \
        == (50, 71)  # (cust, SERVICE_CUSTOMER)
    assert balance_service.xfer_to(BalanceType.BALANCE, cust2, curr, 21) \
        == (23, 50)  # (cust2, SERVICE_CUSTOMER)
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 50
    #
    with raises(NotEnoughBalance):
        balance_service.xfer_from(BalanceType.BALANCE, cust, curr, 100)
    assert balance_service.get(BalanceType.BALANCE, cust, curr) == 50
    with raises(NotEnoughBalance):
        balance_service.xfer_to(BalanceType.BALANCE, cust, curr, 1_000)
    assert balance_service.get(BalanceType.BALANCE, cust, curr) == 50
    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == 50
