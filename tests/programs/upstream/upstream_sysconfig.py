# Adapted from CPython 3.13.16 Lib/test/test_sysconfig.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. Source SHA-256:
# 86e99b332030affedf3fcee3185ada4b96ce17681f08122028f66175254b7a04.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest scaffolding becomes annotated functions and plain assertions. CPython's own
# sysconfig records the oracle, while JIT/AOT execute lib/sysconfig.py.
# Complete: TestSysConfig's test_get_path_names, test_get_paths, test_get_default_scheme and
# test_get_config_vars. test_get_path formats each path with a loop over the variables, as
# str.format(**config_vars) is not compiled, and runs without its Windows branch.
# Not claimed: the other methods of the file, which test the schemes of other platforms, of
# virtual environments and of user installations, get_platform(), CPython's Makefile,
# pyconfig.h and extension suffix, the command line of python -m sysconfig, and a
# subprocess's or another site's configuration.
import os
import sysconfig
from sysconfig import (get_paths, get_path, get_path_names, get_config_vars, get_default_scheme,
                       _expand_vars, _INSTALL_SCHEMES)


# TestSysConfig.test_get_path_names
def test_get_path_names() -> None:
    assert get_path_names() == sysconfig._SCHEME_KEYS


# TestSysConfig.test_get_paths
def test_get_paths() -> None:
    scheme = get_paths()
    default_scheme = get_default_scheme()
    wanted = _expand_vars(default_scheme, None)
    wanted_items = sorted(wanted.items())
    scheme_items = sorted(scheme.items())
    assert scheme_items == wanted_items


def format_path(path: str) -> str:
    # path.format(**get_config_vars()), for the variables the path names
    config_vars = get_config_vars()
    for name in config_vars:
        path = path.replace('{' + name + '}', str(config_vars[name]))
    return path


# TestSysConfig.test_get_path
def test_get_path() -> None:
    for scheme in _INSTALL_SCHEMES:
        for name in _INSTALL_SCHEMES[scheme]:
            expected = format_path(_INSTALL_SCHEMES[scheme][name])
            assert os.path.normpath(get_path(name, scheme)) == os.path.normpath(expected)


# TestSysConfig.test_get_default_scheme
def test_get_default_scheme() -> None:
    assert get_default_scheme() in _INSTALL_SCHEMES


# TestSysConfig.test_get_config_vars
def test_get_config_vars() -> None:
    cvars = get_config_vars()
    assert isinstance(cvars, dict)
    assert cvars


test_get_path_names()
test_get_paths()
test_get_path()
test_get_default_scheme()
test_get_config_vars()
print('5 tests passed')
