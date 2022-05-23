from collections import namedtuple
from pytest import fixture  # type:ignore
from oev8.typedefs import BalanceType


StartedSellingAuctionFixture = \
    namedtuple('StartedSellingAuctionFixture',
               ['trd_id',
                'trading_service',
                'balance_service',
                'item_count_service',
                'event_writer_mock',
                'trading_clockwork_service',
                'start_new_selling_auction_params'])


StartedBuyingAuctionFixture = \
    namedtuple('StartedBuyingAuctionFixture',
               ['trd_id',
                'trading_service',
                'balance_service',
                'item_count_service',
                'event_writer_mock',
                'trading_clockwork_service',
                'start_new_buying_auction_params'])


@fixture
def started_selling_auction(
        trading_service,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_selling_auction_params
):
    params = start_new_selling_auction_params

    # 담보금 입금.
    balance_deposit = params.security_deposit_amt

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # 시작.
    trading_service.start_new_selling_auction(
        **params._asdict())

    # reset mocks
    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_provide_item.reset_mock()
    event_writer_mock.on_trading_new.reset_mock()
    trading_clockwork_service.regist.reset_mock()

    #
    return StartedSellingAuctionFixture(
        trd_id=params.trd_id,
        trading_service=trading_service,
        balance_service=balance_service,
        item_count_service=item_count_service,
        event_writer_mock=event_writer_mock,
        trading_clockwork_service=trading_clockwork_service,
        start_new_selling_auction_params=start_new_selling_auction_params
    )


@fixture
def started_buying_auction(
        trading_service,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    params = start_new_buying_auction_params

    # 담보금 입금.
    balance_deposit = params.security_deposit_amt

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # 구매대금 입금.
    purchase_amt = params.price * params.qty

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=purchase_amt)

    # 시작.
    trading_service.start_new_buying_auction(
        **params._asdict())

    # reset mocks
    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_trading_new.reset_mock()
    trading_clockwork_service.regist.reset_mock()

    #
    return StartedBuyingAuctionFixture(
        trd_id=params.trd_id,
        trading_service=trading_service,
        balance_service=balance_service,
        item_count_service=item_count_service,
        event_writer_mock=event_writer_mock,
        trading_clockwork_service=trading_clockwork_service,
        start_new_buying_auction_params=start_new_buying_auction_params
    )
