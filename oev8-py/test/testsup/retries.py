import asyncio
import logging


class RetryFail(Exception):
    def __init__(self):
        super().__init__()


async def async_retry(fn, max_retries=10, delay_secs=1):
    logger = logging.getLogger('test.conftest.AsyncRetrier')

    for nth_retry in range(max_retries):
        try:
            await fn()
            return  # SUCCEED
        except:
            logger.warning('Retrying [%s/%s] ...',
                           nth_retry + 1, max_retries,
                           exc_info=True)
            await asyncio.sleep(delay_secs)

    # no more retrying
    logger.warning('Max retry reached [%s].',
                   max_retries)

    raise RetryFail()
