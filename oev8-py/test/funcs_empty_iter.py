"""tests on oev8.funcs.empty_iter"""
import uuid
import glob
from pytest import raises  # type:ignore
from oev8.funcs import empty_iter


def one_genfn():
    yield 1


def test_empty_iter():
    assert empty_iter('')

    assert empty_iter([])

    assert not empty_iter('foobar')

    assert not empty_iter([1])

    assert not empty_iter(one_genfn())

    with raises(TypeError):
        assert empty_iter(None)


def test_empty_iter_on_not_existing_dir(tmp_path):
    pn = tmp_path / str(uuid.uuid4())
    assert not pn.exists()
    assert empty_iter(glob.iglob(str(pn)))
