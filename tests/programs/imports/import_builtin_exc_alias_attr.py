# _thread.error is the builtin RuntimeError (from builtins import RuntimeError as error), not a
# class or an import of that name in the code that reads it.
import _thread


class RuntimeError(Exception):
    pass


def local() -> None:
    from re import error as RuntimeError
    try:
        raise _thread.error("in a function")
    except RuntimeError:
        print("re's error")
    except Exception as e:
        print("builtin", type(e).__name__, e)


try:
    raise _thread.error("at module level")
except RuntimeError:
    print("the program's class")
except Exception as e:
    print("builtin", type(e).__name__, e)
local()
