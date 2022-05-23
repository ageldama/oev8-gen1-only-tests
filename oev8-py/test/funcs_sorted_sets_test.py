"""tests on oev8.funcs.sorted_sets"""
from pytest import fixture  # type:ignore
from sortedcontainers import SortedSet  # type:ignore
from oev8.funcs.sorted_sets import \
    lowest_in_sorted_set, highest_in_sorted_set, \
    lowest_in_sorted_set_wo_zero


@fixture
def sorted_set_fixture():
    return SortedSet([1, -3, 0, 99, 42])


@fixture
def empty_sorted_set_fixture():
    return SortedSet([])


def test_lowest_in_sorted_set(
        sorted_set_fixture: SortedSet,
        empty_sorted_set_fixture: SortedSet
):
    # pylint: disable=redefined-outer-name

    assert lowest_in_sorted_set(
        empty_sorted_set_fixture, None) is None

    got = lowest_in_sorted_set(sorted_set_fixture, None)
    assert got is not None
    assert got == -3


def test_highest_in_sorted_set(
        sorted_set_fixture: SortedSet,
        empty_sorted_set_fixture: SortedSet
):
    # pylint: disable=redefined-outer-name

    assert highest_in_sorted_set(
        empty_sorted_set_fixture, None) is None

    got = highest_in_sorted_set(sorted_set_fixture, None)
    assert got is not None
    assert got == 99


def test_lowest_in_sorted_set_wo_zero(
        empty_sorted_set_fixture: SortedSet
):
    # pylint: disable=redefined-outer-name

    assert lowest_in_sorted_set_wo_zero(
        empty_sorted_set_fixture, None) is None

    got = lowest_in_sorted_set_wo_zero(
        SortedSet([42, 0, 23]), None)
    assert got == 23

    got = lowest_in_sorted_set_wo_zero(
        SortedSet([0]), None)
    assert got is None
