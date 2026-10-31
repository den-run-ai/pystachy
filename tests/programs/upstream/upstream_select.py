# Adapted from CPython 3.13.16 Lib/test/test_select.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91 (SHA-256
# 74199f34bac4e209bf2785603be056e549b8089956fdc73165fcb491d5b5887c): class SelectTestCase's
# test_error_conditions, test_errno and test_returned_list_identity.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertRaises(E, f, ...) is a try statement
# that prints the error, and assertIsNot(a, b) asserts a is not b. test_errno opens a new file in a
# tempfile.mkdtemp() directory (__file__ and binary mode are not supported), and checks the error's
# number in its message: an OSError's errno attribute is not readable here (str(e) is).
# EXCLUDED upstream cases:
# - test_error_conditions' four TypeErrors (select.select(1, 2, 3), lists of objects without a
#   fileno() or whose fileno() returns a str, a str timeout): compile-time errors here, as
#   tests/errors/library/lib_select_objects.py and tests/errors/library/lib_select_optional.py show for such calls
# - test_select (subprocess and a pipe object in the list), test_select_mutated (objects whose
#   fileno() mutates the list) and test_disallow_instantiation (select.poll): objects in the lists,
#   subprocess and poll are not supported (docs/select.md)
import errno
import os
import select
import tempfile


def test_error_conditions() -> None:
    try:
        select.select([], [], [], -1)
        print("no error")
    except ValueError as e:
        print("ValueError", e)


def test_errno() -> None:
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "test_errno.txt")
    with open(path, "w") as fp:
        fd = fp.fileno()
        fp.close()
        try:
            select.select([fd], [], [], 0)
        except OSError as err:
            assert str(err).startswith(f"[Errno {errno.EBADF}] "), str(err)
            print("OSError EBADF")
        else:
            assert False, "exception not raised"
    os.remove(path)
    os.rmdir(folder)


def test_returned_list_identity() -> None:
    # See issue #8329
    r, w, x = select.select([], [], [], 1)
    assert r is not w
    assert r is not x
    assert w is not x
    print(r, w, x)


test_error_conditions()
test_errno()
test_returned_list_identity()
