import logging
import asyncio
from datetime import timedelta
from glob import glob
from pytest import mark, fixture  # type:ignore
from . import is_system_test_disabled
from test.testsup.retries import RetryFail, async_retry
from oev8.bench import Stopwatch
from oev8.typedefs import BalanceType


logger = logging.getLogger('test.system_tests.concurrent_clients_test')


async def tbody_start_proc(
        oev8_sh_cmd,
        test_config_path
):
    # start process.
    cfg_fn = str(test_config_path.resolve())
    proc = await asyncio.create_subprocess_exec(
        *(oev8_sh_cmd + [cfg_fn]))

    logger.debug('PID(%s) Running?(%s)',
                 proc.pid, proc.returncode is None)

    # wait...
    retcode = await proc.wait()
    logger.info('Terminated with: %s', retcode)


async def tbody_sleep(
        lock,
        queue,
        tcp_cmd_client
):
    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    sw = Stopwatch()

    with sw:
        await tcp_cmd_client.ping()

    assert sw.timedelta < timedelta(seconds=1)

    lock.release()  # sleep 직전에 lock 전달.
    await queue.put('SLEEP')

    await tcp_cmd_client.sleep(3)

    logger.debug('SLEPT!')
    await queue.put('SLEPT')


async def tbody_ping(
        lock,
        queue,
        tcp_cmd_client
):
    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    await lock.acquire()  # sleep이 되었으리라 싶은데.
    await asyncio.sleep(1)

    sw = Stopwatch()

    with sw:
        await queue.put('PING')
        logger.debug('PING!')

        await tcp_cmd_client.ping()

        await queue.put('PONG')
        logger.debug('GOT PONG!')

    assert sw.timedelta > timedelta(seconds=1)

    # SHUTDOWN
    try:
        await tcp_cmd_client.shutdown()
    except:
        logger.debug('exception on shutdown, ok. (ignored)')


async def tbody_concurrent_client_1st_sleep(
        oev8_sh_cmd,
        test_config_path,
        tcp_cmd_client_provider
):
    lock = asyncio.Lock()
    await lock.acquire()
    # 일단 ping이 진입하지 못하도록 acquire 상태로 시작.
    # release은 sleep 진입하며 함께.

    queue = asyncio.Queue()

    await asyncio.gather(
        tbody_start_proc(oev8_sh_cmd, test_config_path),
        tbody_sleep(lock, queue, tcp_cmd_client_provider()),
        tbody_ping(lock, queue, tcp_cmd_client_provider()))

    logger.debug('Queue: %s', queue)

    l = []
    while True:
        try:
            l.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break

    assert l == ['SLEEP', 'PING', 'SLEPT', 'PONG']


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_concurrent_clients_1st_sleep(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client_provider,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    '''동시 접속을 어떻게 처리하는지.

           1) 첫번째 클라이언트가 sleep중이고.

           2) 두번째 클라이언트가 ping을 하려고 할 때, 두번째가 첫번째를 기다리게 되어야 한다.
    '''
    # 실행
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody_concurrent_client_1st_sleep(
            oev8_sh_cmd,
            test_config_path,
            tcp_cmd_client_provider))


"""
from multiprocessing import Process
from multiprocessing import Value


def f(name):

    n.value = 3.1415927

    print('hello', name)

if __name__ == '__main__':
    num = Value('d', 0.0)

    p = Process(target=f, args=('bob',))
    p.start()
    p.join()
"""
