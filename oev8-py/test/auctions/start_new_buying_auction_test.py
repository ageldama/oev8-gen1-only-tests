from unittest.mock import call, ANY
from pytest import mark  # type:ignore
from pytest import raises  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, TradingState, TradingType
from oev8.typedefs import AuctionSide
from oev8.values.event_writer import \
    BalanceXferFromCauseSecurityDeposit, \
    BalanceXferFromCauseBuyingAuction, \
    ItemCountXferFromCauseSellingAuction
from oev8.excs import NotEnoughBalance, ExistingTradingId, \
    CurrencyAmtShouldBePositive, ItemQtyShouldBePositive
from oev8.svcs.trading import TradingService


def test_start_new_buying_auction__simply_ok(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '그냥 잘 동작하는 별거 없는 실행 예.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # 담보금 입금.
    balance_deposit = params.security_deposit_amt * 1.5

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

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == \
                               balance_deposit + purchase_amt

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    # BEFORE: 아이템(SERVICE_CUSTOMER)
    assert item_count_service.get(cust_id=params.cust_id,
                                  trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER,
                                  trd_id=trd_id) == 0

    # 실행: 에러 없이 그냥 동작.
    trading_service.start_new_buying_auction(
        **params._asdict())

    # AFTER: new Tradings and Auctions.
    #   - 새로운 trd_id, trading, auction을 생성한다.
    assert trd_id in trading_service.tradings
    assert trd_id in trading_service.auctions

    # 생성한 Trading 체크.
    trd = trading_service.tradings[trd_id]
    assert trd.state == TradingState.OPEN
    assert trd.trading_type == TradingType.AUCTION
    assert trd.curr == params.curr
    assert trd.item_providings == {}

    # 생성한 Auction 체크.
    auction = trading_service.auctions[trd_id]
    assert auction.auction_side == AuctionSide.BUYING
    assert auction.cust_id == params.cust_id
    assert auction.price == params.price
    assert auction.qty == params.qty

    # AFTER: Balances -- 담보금+구매대금 이체 확인.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == \
                               balance_deposit - params.security_deposit_amt

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == \
                               params.security_deposit_amt + purchase_amt

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        # 담보금
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id,
             curr=params.curr,
             amt=params.security_deposit_amt,
             new_amt=(balance_deposit - params.security_deposit_amt) + purchase_amt,
             new_svc=params.security_deposit_amt,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=params.trd_id)),
        # 구매대금
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id,
             curr=params.curr,
             amt=purchase_amt,
             new_amt=(balance_deposit - params.security_deposit_amt),
             new_svc=params.security_deposit_amt + purchase_amt,
             why=BalanceXferFromCauseBuyingAuction(trd_id=params.trd_id)),

    ])

    # AFTER: 아이템(SERVICE_CUSTOMER) & 이벤트 item_count.xfer_from
    assert item_count_service.get(cust_id=params.cust_id,
                                  trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER,
                                  trd_id=trd_id) == 0

    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    # Item Providings + 이벤트: 갯수는 이미 위에서 Trading 생성 부분에서 검증.
    event_writer_mock.on_trading_provide_item.assert_not_called()

    # 이벤트 on_trading_new
    event_writer_mock.on_trading_new.assert_has_calls([
        call(trd_id)
    ])

    # clockwork.regist 호출.
    trading_clockwork_service.regist.assert_has_calls([
        call(trd_id, params.until_utc_timestamp_secs)
    ])


def test_start_new_buying_auction__insufficient_for_sec_deposit_amt(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '담보금 제출 불가.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    # 실행: 에러.
    with raises(NotEnoughBalance):
        trading_service.start_new_buying_auction(
            **params._asdict())

    # AFTER: auctions and tradings
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # AFTER: Balances and Item counts
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=params.cust_id) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=SERVICE_CUSTOMER) == 0

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__insufficient_for_purchase_amt(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '구매대금 제출 불가.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    #
    purchase_amt = params.price * params.qty

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=params.security_deposit_amt)

    # BEFORE: Balances.

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == params.security_deposit_amt

    # 실행: 에러.
    with raises(NotEnoughBalance):
        trading_service.start_new_buying_auction(
            **params._asdict())

    # AFTER: auctions and tradings
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # AFTER: Balances and Item counts
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == params.security_deposit_amt

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=params.cust_id) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=SERVICE_CUSTOMER) == 0

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__existing_trd_id(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '이미 존재하는 trd_id.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # 담보금 입금.
    balance_deposit = params.security_deposit_amt * 10

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # EXCHANGE-trading을 시작.
    trading_service.start_new_trading_as_seller(
        cust_id=params.cust_id,
        trd_id=trd_id,
        curr=params.curr,
        security_deposit_amt=params.security_deposit_amt,
        qty=params.qty,
        limit_sell_unit_price=1,
        until_utc_timestamp_secs=params.until_utc_timestamp_secs
    )

    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_provide_item.reset_mock()
    event_writer_mock.on_trading_new.reset_mock()
    trading_clockwork_service.regist.reset_mock()

    # BEFORE: Tradings and Auctions.
    assert trd_id in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == \
                               (balance_deposit - params.security_deposit_amt)

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == \
                               params.security_deposit_amt

    # BEFORE: 아이템(SERVICE_CUSTOMER)
    assert item_count_service.get(cust_id=params.cust_id,
                                  trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER,
                                  trd_id=trd_id) == params.qty

    # 실행: 에러.
    with raises(ExistingTradingId):
        trading_service.start_new_buying_auction(
            **params._asdict())

    # AFTER: new Tradings and Auctions.
    assert trd_id in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # Trading 체크.
    trd = trading_service.tradings[trd_id]
    assert trd.state == TradingState.OPEN
    assert trd.trading_type == TradingType.EXCHANGE
    assert trd.curr == params.curr
    assert trd.item_providings == {params.cust_id: params.qty}

    # AFTER: Balances -- 담보금 이체 확인. (그대로)
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == \
                               (balance_deposit - params.security_deposit_amt)

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == \
                               params.security_deposit_amt

    # AFTER: 아이템(SERVICE_CUSTOMER) (그대로)
    assert item_count_service.get(cust_id=params.cust_id,
                                  trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER,
                                  trd_id=trd_id) == params.qty

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__zero_sec_deposit_amt(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '지정 담보금이 양수가 아님.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # 담보금 이체.
    balance_deposit = 1_000

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    # 실행: 에러.
    d = params._asdict()
    d['security_deposit_amt'] = 0
    with raises(CurrencyAmtShouldBePositive):
        trading_service.start_new_buying_auction(**d)

    # AFTER: auctions and tradings
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # AFTER: Balances and Item counts
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=params.cust_id) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=SERVICE_CUSTOMER) == 0

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__zero_price(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '가격이 양수가 아님.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # 담보금 이체.
    balance_deposit = 1_000

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    # 실행: 에러.
    d = params._asdict()
    d['price'] = 0
    with raises(CurrencyAmtShouldBePositive):
        trading_service.start_new_buying_auction(**d)

    # AFTER: auctions and tradings
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # AFTER: Balances and Item counts
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=params.cust_id) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=SERVICE_CUSTOMER) == 0

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__zero_qty(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '수량이 양수가 아님.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # 담보금 이체.
    balance_deposit = 1_000

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=balance_deposit)

    # BEFORE: Tradings and Auctions.
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # BEFORE: Balances.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    # 실행: 에러.
    d = params._asdict()
    d['qty'] = 0
    with raises(ItemQtyShouldBePositive):
        trading_service.start_new_buying_auction(**d)

    # AFTER: auctions and tradings
    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions

    # AFTER: Balances and Item counts
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == balance_deposit

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=params.cust_id) == 0

    assert item_count_service.get(trd_id=trd_id,
                                  cust_id=SERVICE_CUSTOMER) == 0

    # Events
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_trading_new.assert_not_called()

    # Clockwork
    trading_clockwork_service.regist.assert_not_called()


def test_start_new_buying_auction__existing_auction_trd_id(
        trading_service: TradingService,
        balance_service,
        item_count_service,
        event_writer_mock,
        trading_clockwork_service,
        start_new_buying_auction_params
):
    '존재하는 경매 trd_id.'

    params = start_new_buying_auction_params

    trd_id = params.trd_id

    # [(담보금 + 구매대금) * 2] 입금.
    total_deposit = \
        (params.security_deposit_amt + params.price * params.qty) * 2
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=total_deposit)

    # 실행: 에러 없이 그냥 동작. (1st)
    trading_service.start_new_buying_auction(
        **params._asdict())

    # 실행: (2nd) 에러
    with raises(ExistingTradingId):
        trading_service.start_new_buying_auction(
            **params._asdict())

    # AFTER: Balances -- 담보금+구매대금 이체 확인.
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id,
                               curr=params.curr) == \
                               (total_deposit / 2)

    assert balance_service.get(BalanceType.EARNING,
                               cust_id=params.cust_id,
                               curr=params.curr) == 0

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=SERVICE_CUSTOMER,
                               curr=params.curr) == \
                               (total_deposit / 2)

    # AFTER: 아이템(SERVICE_CUSTOMER) & 이벤트 item_count.xfer_from
    assert item_count_service.get(cust_id=params.cust_id,
                                  trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER,
                                  trd_id=trd_id) == 0

    # Item Providings + 이벤트: 갯수는 이미 위에서 Trading 생성 부분에서 검증.
    event_writer_mock.on_trading_provide_item.assert_not_called()

    # 이벤트 on_trading_new
    event_writer_mock.on_trading_new.assert_has_calls([
        call(trd_id)
    ])

    # clockwork.regist 호출.
    trading_clockwork_service.regist.assert_has_calls([
        call(trd_id, params.until_utc_timestamp_secs)
    ])
