import logging
from unittest.mock import Mock, AsyncMock
from pytest import mark, raises  # type:ignore
from oev8.bench import CSVLoggingStopwatch


logger = logging.getLogger('test.logging_stopwatch_test')


def test_logging_stopwatch_with_stmt():
    lsw = CSVLoggingStopwatch(logger, 'test_logging_stopwatch_with_stmt')

    with lsw:
        pass


def test_logging_stopwatch_with_stmt_error():
    lsw = CSVLoggingStopwatch(logger, 'test_logging_stopwatch_with_stmt')

    with raises(Exception):
        with lsw:
            raise Exception()


def test_null_logging_stopwatch(null_logging_stopwatch):
    f = Mock()

    with null_logging_stopwatch:
        f()

    f.assert_called_once()


@mark.asyncio
async def test_null_logging_stopwatch_async(null_logging_stopwatch):
    f = AsyncMock()

    async with null_logging_stopwatch:
        await f()

    f.assert_awaited_once()



def test_null_logging_stopwatch_error(null_logging_stopwatch):
    with raises(Exception):
        with null_logging_stopwatch:
            raise Exception()

    null_logging_stopwatch.__exit__.assert_called_once()


@mark.asyncio
async def test_null_logging_stopwatch_async_error(null_logging_stopwatch):
    with raises(Exception):
        async with null_logging_stopwatch:
            raise Exception()

    null_logging_stopwatch.__aexit__.assert_awaited_once()
