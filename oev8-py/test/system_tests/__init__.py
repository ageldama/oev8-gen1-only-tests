from os import environ


def is_system_test_disabled():
    return 'OEV8_SYS_TEST' not in environ
