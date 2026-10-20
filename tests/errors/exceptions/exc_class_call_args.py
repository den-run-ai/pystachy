# error: exc_class_call_args.py:6: error: a call of an exception class held as a value is supported with one argument at most
# CPython makes ValueError('a', 'b'); a class object takes one argument here (none, or one)


def make(c: type[Exception]) -> Exception:
    return c("a", "b")


print(repr(make(ValueError)))
