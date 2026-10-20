# CPython _imp differential: one-thread nesting, unwind, aliases, and missing frozen names.
import _imp
from _imp import acquire_lock, lock_held, release_lock
import math


def guarded_work(value: float) -> float:
    acquire_lock()
    try:
        print("nested", lock_held())
        return math.sqrt(value)
    finally:
        release_lock()


print("initial", _imp.lock_held())
print("acquire", _imp.acquire_lock())
print("work", guarded_work(81.0))
print("outer", _imp.lock_held())
print("release", _imp.release_lock())
print("released", lock_held())
try:
    release_lock()
except RuntimeError as error:
    print("unheld", str(error))

acquire_lock()
try:
    acquire_lock()
    try:
        raise ValueError("unwind")
    finally:
        release_lock()
except ValueError as error:
    print(str(error), lock_held())
finally:
    release_lock()
print("after unwind", lock_held())

for name in ["pystachy_missing_frozen_module", "", "missing.module", "missing'quote"]:
    print("missing", name, _imp.is_frozen(name))
    print(_imp.find_frozen(name), _imp.find_frozen(name, withdata=True))
    print(_imp.init_frozen(name))
    try:
        _imp.is_frozen_package(name)
    except ImportError as error:
        print(str(error))
    try:
        _imp.get_frozen_object(name)
    except ImportError as error:
        print(str(error))
