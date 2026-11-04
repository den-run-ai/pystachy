# CPython 3.13.16 Lib/test/test_argparse.py, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# All success vectors from TestOptionalsNargsDefault, TestOptionalsActionStoreFalse and
# TestOptionalsActionStoreTrue. Read the declared field instead of comparing NS instances.
# Failure vectors use process exit and are outside this in-process fixture.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
import argparse


def value_option() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-x")
    assert parser.parse_args([]).x is None
    assert parser.parse_args(["-x", "a"]).x == "a"


def disable_option() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-z", action="store_false")
    assert parser.parse_args([]).z is True
    assert parser.parse_args(["-z"]).z is False


def enable_option() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apple", action="store_true")
    assert parser.parse_args([]).apple is False
    assert parser.parse_args(["--apple"]).apple is True


value_option()
disable_option()
enable_option()
