import builtins


class MonthError(ValueError, builtins.IndexError):
    def __init__(self, month: int):
        self.month = month

    def __str__(self):
        return "bad month %d" % self.month


class Child(MonthError):
    pass


class Reverse(IndexError, ValueError):
    pass


def classify(cls: type[BaseException], target: type[BaseException]) -> bool:
    return issubclass(cls, target)


def reraised(e: MonthError):
    try:
        raise e
    except (TypeError, LookupError) as caught:
        print(type(caught).__name__, str(caught), repr(caught))
        raise


for obj in [MonthError(0), Child(13)]:
    for cls in [MonthError, ValueError, IndexError, LookupError, Exception, KeyError]:
        print(classify(type(obj), cls), isinstance(obj, cls))
    try:
        reraised(obj)
    except ValueError as error:
        print(type(error).__name__, isinstance(error, (IndexError, RuntimeError)))
    except IndexError:
        print("wrong precedence")


try:
    raise Reverse("month", 13)
except LookupError as caught:
    print(repr(caught), str(caught), isinstance(caught, ValueError))
    try:
        raise
    except (TypeError, ValueError):
        print("caught by the other branch")


def through_value(e: ValueError) -> bool:
    return isinstance(e, IndexError)


def through_index(e: IndexError) -> bool:
    return isinstance(e, ValueError)


def through_lookup(e: LookupError) -> bool:
    return isinstance(e, ValueError)


for bad in [True, False]:
    try:
        if bad:
            raise Child(13)
        raise ValueError(13)
    except ValueError as v:
        print(through_value(v))
    try:
        if bad:
            raise Child(13)
        raise IndexError(13)
    except IndexError as i:
        print(through_index(i), through_lookup(i))
