# A SystemExit subclass whose code is a str: nothing catches it, so the program writes the code
# to stderr and ends with status 1. Its finally blocks run first.


class Stop(SystemExit):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.msg = msg


def main() -> None:
    try:
        raise Stop("stopped: bad input")
    finally:
        print("cleanup")


try:
    raise Stop("caught")
except SystemExit as e:
    print("caught:", e, repr(e))
main()
