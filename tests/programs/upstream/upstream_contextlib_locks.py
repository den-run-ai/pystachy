# CPython 3.13.16 Lib/test/test_contextlib.py at cbc944f4bc59639a444dd971c737788ba2283a91
# SHA-256 b7b3a0f70a4c760743c99662de3e575711de671ce519780b0883e9a9ec94196c
# All five LockContextTestCase methods, mechanically extracted by tools/cpython_test_methods.py.
# The upstream PSF license is in tests/upstream/CPYTHON-LICENSE.txt.
"""Unit tests for contextlib.py, and other context managers."""
import threading

class LockContextTestCase:

    def boilerPlate(self, lock, locked):
        assert not locked()
        with lock:
            assert locked()
        assert not locked()
        try:
            with lock:
                assert locked()
                1 / 0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError('did not raise')
        assert not locked()

    def testWithLock(self):
        lock = threading.Lock()
        self.boilerPlate(lock, lock.locked)

    def testWithRLock(self):
        lock = threading.RLock()
        self.boilerPlate(lock, lock._is_owned)

    def testWithCondition(self):
        lock = threading.Condition()

        def locked():
            return lock._is_owned()
        self.boilerPlate(lock, locked)

    def testWithSemaphore(self):
        lock = threading.Semaphore()

        def locked():
            if lock.acquire(False):
                lock.release()
                return False
            else:
                return True
        self.boilerPlate(lock, locked)

    def testWithBoundedSemaphore(self):
        lock = threading.BoundedSemaphore()

        def locked():
            if lock.acquire(False):
                lock.release()
                return False
            else:
                return True
        self.boilerPlate(lock, locked)


def _LockContextTestCase__testWithLock():
    t = LockContextTestCase()
    t.testWithLock()
    print('ok LockContextTestCase.testWithLock')


def _LockContextTestCase__testWithRLock():
    t = LockContextTestCase()
    t.testWithRLock()
    print('ok LockContextTestCase.testWithRLock')


def _LockContextTestCase__testWithCondition():
    t = LockContextTestCase()
    t.testWithCondition()
    print('ok LockContextTestCase.testWithCondition')


def _LockContextTestCase__testWithSemaphore():
    t = LockContextTestCase()
    t.testWithSemaphore()
    print('ok LockContextTestCase.testWithSemaphore')


def _LockContextTestCase__testWithBoundedSemaphore():
    t = LockContextTestCase()
    t.testWithBoundedSemaphore()
    print('ok LockContextTestCase.testWithBoundedSemaphore')


_LockContextTestCase__testWithLock()
_LockContextTestCase__testWithRLock()
_LockContextTestCase__testWithCondition()
_LockContextTestCase__testWithSemaphore()
_LockContextTestCase__testWithBoundedSemaphore()
