import logging
import asyncio
from glob import glob
from pytest import mark, fixture  # type:ignore
from . import is_system_test_disabled
from test.testsup.retries import RetryFail, async_retry
from oev8.typedefs import BalanceType


logger = logging.getLogger('test.system_tests.recover_from_snapshot_test')


async def tbody_1st_session(
        oev8_sh_cmd,
        test_config_path,
        tcp_cmd_client
):
    # start process.
    cfg_fn = str(test_config_path.resolve())
    proc = await asyncio.create_subprocess_exec(
        *(oev8_sh_cmd + [cfg_fn]))

    logger.debug('PID(%s) Running?(%s)',
                 proc.pid, proc.returncode is None)

    logger.debug('tcp_cmd_client: %s',
                 tcp_cmd_client)

    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    # 1) Balance-Deposit(Cust=1, Curr=1, Amt=N)
    balance_deposit_resp = await tcp_cmd_client.balance_deposit(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1, amt=123)

    logger.info('BALANCE-DEPOSIT(Cust=1, Curr=1, Amt=N): %s',
                balance_deposit_resp)

    assert balance_deposit_resp.new_amt == '123'

    # 2) assert Balance-Get(Cust=1, Curr=1) == N
    balance_get_a = await tcp_cmd_client.balance_get(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1)

    logger.info('BALANCE-GET (Cust=1, Curr=1): %s', balance_get_a)

    assert balance_get_a.amt == '123'

    # 3) assert Balance-Get(Cust=2, Curr=1) == 0
    balance_get_b = await tcp_cmd_client.balance_get(
        cust_id='2', balance_type=BalanceType.BALANCE,
        curr=1)

    logger.info('BALANCE-GET (Cust=2, Curr=1): %s', balance_get_b)

    assert balance_get_b.amt == '0'

    # 4) assert Balance-Get(Cust=1, Curr=2) == 0
    balance_get_c = await tcp_cmd_client.balance_get(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=2)

    logger.info('BALANCE-GET (Cust=1, Curr=2): %s', balance_get_c)

    assert balance_get_c.amt == '0'

    # 5) assert Balance-Get(Cust=1, Curr=1, EARNING) = 0
    balance_get_d = await tcp_cmd_client.balance_get(
        cust_id='1', balance_type=BalanceType.EARNING,
        curr=1)

    logger.info('BALANCE-GET (Cust=1, Curr=1, EARNING): %s',
                balance_get_d)

    assert balance_get_d.amt == '0'

    #
    try:
        await tcp_cmd_client.save_quit()
    except:
        logger.debug("CAUGHT EXC on SAVE_QUIT. (it's okay)",
                     exc_info=True)

    # wait...
    retcode = await proc.wait()
    logger.info('Terminated with: %s', retcode)


async def tbody_2nd_session(
        oev8_sh_cmd,
        test_config_path,
        tcp_cmd_client
):
    # start process.
    cfg_fn = str(test_config_path.resolve())
    proc = await asyncio.create_subprocess_exec(
        *(oev8_sh_cmd + [cfg_fn]))

    logger.debug('PID(%s) Running?(%s)',
                 proc.pid, proc.returncode is None)

    logger.debug('tcp_cmd_client: %s',
                 tcp_cmd_client)

    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    # 2) assert Balance-Get(Cust=1, Curr=1) == N
    balance_get_a = await tcp_cmd_client.balance_get(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1)

    logger.info('BALANCE-GET (Cust=1, Curr=1): %s', balance_get_a)

    assert balance_get_a.amt == '123'

    # wait...
    proc.kill()
    retcode = await proc.wait()
    logger.info('Terminated with: %s', retcode)


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_recover_from_snapshot(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client_provider,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    '''모두 스냅샷만으로 복구하는지 확인하기.

           1) Balance-Deposit(Cust=1, Curr=1, Amt=N)
           2) assert Balance-Get(Cust=1, Curr=1) == N
           3) assert Balance-Get(Cust=2, Curr=1) == 0
           4) assert Balance-Get(Cust=1, Curr=2) == 0

    - 하지만, Journals에 기록을 남겨놓고 replay만 하지 않는 상황의 테스트.
    '''
    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행 #1.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody_1st_session(oev8_sh_cmd,
                                 test_config_path,
                                 tcp_cmd_client_provider()))

    # snapshot 디렉토리 목록 - 스냅샷 생성되었는지?
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) > 0

    # 실행 #2.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody_2nd_session(oev8_sh_cmd,
                                 test_config_path,
                                 tcp_cmd_client_provider()))
