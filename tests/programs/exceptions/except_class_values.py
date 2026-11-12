# An except clause can hold its exception classes in values: a local alias, a parameter of a
# class object's type, a field, a call and tuples of them with classes named. CPython evaluates
# a clause's expression only when an exception gets to that clause, and tests its classes in
# turn; one that matches nothing lets the exception go on, and one that raises replaces it
import statistics


class Kinds:
    def __init__(self, kind: type[BaseException]) -> None:
        self.kind = kind


log: list[str] = []


def pick(kind: type[BaseException]) -> type[BaseException]:
    log.append(kind.__name__)
    return kind


def bad() -> type[BaseException]:
    raise RuntimeError("raised by the clause")


def local_alias() -> None:
    StatisticsError = statistics.StatisticsError
    try:
        statistics.fmean([10.0, 20.0], [-1.0, 1.0])
    except StatisticsError as e:
        print("local alias:", type(e).__name__, e)


def parameter(kind: type[BaseException], text: str) -> None:
    try:
        print(int(text))
    except kind:
        print("parameter caught:", kind.__name__)
    except Exception as e:
        print("parameter missed:", kind.__name__, type(e).__name__)


def calls() -> None:
    d: dict[str, int] = {}
    try:
        print(d["k"])
    except pick(ValueError):
        print("value")
    except pick(KeyError) as e:
        print("key:", repr(e))
    except pick(IndexError):
        print("index")
    print("clauses evaluated:", log)


def tuples(kinds: tuple[type[BaseException], type[BaseException]]) -> None:
    Err = OSError
    for text in ("x", "", "1"):
        try:
            if text == "":
                raise FileNotFoundError("missing")
            print("no error:", int(text))
        except (KeyError, Err) as e:
            print("tuple display:", type(e).__name__, e)
        except kinds as e:
            print("tuple value:", type(e).__name__)


def fields() -> None:
    k = Kinds(ZeroDivisionError)
    try:
        print(1 // len(""))
    except k.kind as e:
        print("field:", e)


def unmatched() -> None:
    Err = KeyError
    try:
        try:
            raise ValueError("inner")
        except Err:
            print("wrong clause")
    except ValueError as e:
        print("went on:", e)


def raising_clause() -> None:
    try:
        try:
            raise ValueError("first")
        except bad():
            print("never")
        finally:
            print("finally ran")
    except RuntimeError as e:
        print("replaced:", e)


local_alias()
parameter(ValueError, "x")
parameter(KeyError, "x")
parameter(ValueError, "7")
calls()
tuples((ValueError, TypeError))
fields()
unmatched()
raising_clause()
