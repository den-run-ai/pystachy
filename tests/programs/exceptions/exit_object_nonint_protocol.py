# __index__ and __int__ do not turn an ordinary object's exit message into a status.
import sys


class Code:
    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 0

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 0

    def __str__(self) -> str:
        return "ordinary object message"


print("message", flush=True)
sys.exit(Code())
