# Handler validation examines the whole flat tuple before matching. isinstance keeps its
# separate short-circuit and recursive tuple rules. NoneType's class comes from type(None)
# through the same optional exception path as a real exception class.
log: list[str] = []


def pick(kind: type[BaseException]) -> type[BaseException]:
    log.append(kind.__name__)
    return kind


def single(value: BaseException | None) -> None:
    kind = type(value)
    try:
        try:
            raise ValueError("original")
        except kind:
            print("single matched")
        finally:
            print("single finally")
    except TypeError as error:
        print("invalid single:", error)
    except ValueError:
        print("single missed")


def display(value: BaseException | None, matching_first: bool) -> None:
    kind = type(value)
    first = ValueError if matching_first else kind
    second = kind if matching_first else ValueError
    try:
        try:
            raise ValueError("original")
        except (pick(first), pick(second)):
            print("display matched")
    except TypeError as error:
        print("invalid display:", error)
    print("evaluated:", log)
    log.clear()


def held(kinds: tuple[type[BaseException], type[BaseException]]) -> None:
    try:
        try:
            raise ValueError("original")
        except kinds:
            print("held matched")
    except TypeError as error:
        print("invalid held:", error)


def lazy(value: BaseException | None) -> None:
    kind = type(value)
    try:
        print("no exception")
    except pick(kind):
        print("unreachable")
    try:
        raise ValueError("handled earlier")
    except ValueError:
        print("earlier handler")
    except pick(kind):
        print("unreachable")
    print("not evaluated:", log)
    nested = ((ValueError, kind), KeyError)
    print("isinstance:", isinstance(ValueError(), nested))
    held((ValueError, kind))


single(None)
single(ValueError())
single(KeyError())
display(None, True)
display(None, False)
display(ValueError(), True)
lazy(None)
