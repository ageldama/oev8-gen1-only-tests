'''testing only!'''
from abc import ABC, abstractmethod
from typing import NewType, MutableMapping, List
from pytest import fail  # type: ignore


Key = NewType('Key', int)
Val = NewType('Val', str)


class Foo:
    '''???'''
    Map = NewType('Map', MutableMapping[Key, Val])

    my_map: Map

    def __init__(self):
        self.my_map = {}

    def func(self) -> bool:
        '''bar'''
        return 42 in self.my_map

    def func2(self) -> None:
        '''bar'''


class SomeABC(ABC):
    '''some-abc'''

    @abstractmethod
    def fun1(self):
        '''impl this'''
        raise NotImplementedError

    @abstractmethod
    def fun2(self):
        '''impl this'''
        raise NotImplementedError


class SomeABCImpl1(SomeABC):
    '''impl-1'''

    def fun1(self):
        '''impl-1'''

    def fun2(self):
        '''impl-1'''

    @staticmethod
    def fun_for_impl1():
        '''only for impl-1'''
        return 'fun_for_impl1'


class SomeABCImpl2(SomeABC):
    '''impl-2'''

    def fun1(self):
        '''impl-2'''

    def fun2(self):
        '''impl-2'''

    @staticmethod
    def fun_for_impl2():
        '''only for impl-2'''
        return 'fun_for_impl2'


SomeABCList = List[SomeABC]


def test_some_abc_list():
    '''test it'''
    SomeABCImpl1().fun_for_impl1()

    some_abc_list: SomeABCList
    some_abc_list = [SomeABCImpl1(), SomeABCImpl2()]

    result = []
    for i in some_abc_list:
        result.append(i.__class__)
        if isinstance(i, SomeABCImpl1):
            some_abc_impl1: SomeABCImpl1
            some_abc_impl1 = i
            assert some_abc_impl1.fun_for_impl1()
        elif isinstance(i, SomeABCImpl2):
            some_abc_impl2: SomeABCImpl2
            some_abc_impl2 = i
            assert some_abc_impl2.fun_for_impl2()
        else:
            fail()
            print('???', i)
    assert result == [SomeABCImpl1, SomeABCImpl2]
