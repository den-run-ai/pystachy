# isinstance() of values that are no exceptions against exception classes, and type() of class
# objects: a function given a message or a warning tests which it got, as warnings.warn() does


class AppWarning(UserWarning):
    pass


def describe(message, category=None):
    if isinstance(message, Warning):
        kind = type(message).__name__
    else:
        kind = "text"
    print(kind, str(message), type(category).__name__)


describe("plain")
describe(UserWarning("w"))
describe(ValueError("v"))
describe(AppWarning("a"), DeprecationWarning)
describe("t", AppWarning)
print(isinstance("s", Warning), isinstance(5, KeyError), isinstance([1], (ValueError, OSError)))
print(isinstance(None, Exception), isinstance(KeyError, Exception), isinstance(AppWarning, Warning))
print(isinstance(KeyError, type), isinstance(AppWarning, type), isinstance("s", type))
for c in [KeyError, AppWarning, UserWarning]:
    print(type(c).__name__, type(c).__qualname__, type(c).__module__)


def category_name(category: type[Warning] | None = None) -> str:
    return type(category).__name__ + " " + type(category).__module__


print(category_name(), category_name(DeprecationWarning), category_name(AppWarning))
