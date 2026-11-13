# An exception class may name a second exception base that defines nothing itself, a class of
# the program or a plain builtin one: the first base gives the object its layout, methods and
# text, and both decide what catches it and what isinstance() and issubclass() tell.
class Signal(ArithmeticError):
    def describe(self) -> str:
        return "signal " + str(self)


class Rounded(Signal):
    pass


class Inexact(Signal):
    pass


class Overflow(Inexact, Rounded):
    pass


class Underflow(Overflow):
    def __str__(self) -> str:
        return "underflow"


class DivisionByZero(Signal, ZeroDivisionError):
    def __init__(self, text: str, places: int = 0) -> None:
        super().__init__(text)
        self.places = places


class Conversion(Signal, TypeError):
    pass


class Marker(Exception):
    """Defines nothing."""


class Tagged(ValueError, Marker):
    pass


def raised(n: int) -> None:
    if n == 0:
        raise Overflow("too large")
    if n == 1:
        raise Underflow("too small")
    if n == 2:
        raise DivisionByZero("by zero", 3)
    if n == 3:
        raise Conversion("no float")
    raise Tagged("tagged")


def caught_by(n: int) -> str:
    out: list[str] = []
    for kind in range(9):
        try:
            try:
                raised(n)
            except Rounded as e:
                if kind != 0:
                    raise
                out.append("Rounded")
            except ZeroDivisionError as e:
                if kind != 1:
                    raise
                out.append("ZeroDivisionError")
            except TypeError as e:
                if kind != 2:
                    raise
                out.append("TypeError")
            except Marker as e:
                if kind != 3:
                    raise
                out.append("Marker")
        except Inexact:
            out.append("Inexact" if kind == 4 else "")
        except Signal as e:
            out.append("Signal:" + e.describe() if kind == 5 else "")
        except ArithmeticError:
            out.append("ArithmeticError" if kind == 6 else "")
        except ValueError as e:
            out.append("ValueError:" + str(e) if kind == 7 else "")
        except Exception:
            out.append("Exception" if kind == 8 else "")
    return " ".join([name for name in out if name != ""])


def subclass(cls: type[BaseException], target: type[BaseException]) -> bool:
    return issubclass(cls, target)


def as_signal(e: Signal) -> str:
    return type(e).__name__ + ":" + e.describe() + ":" + str(isinstance(e, ZeroDivisionError)) + str(isinstance(e, Rounded))


def crossed(e: Inexact) -> str:
    # An Inexact may be an Overflow, which is a Rounded too: its class decides.
    if isinstance(e, Rounded):
        return "rounded " + e.describe()
    return str(isinstance(e, (Marker, Rounded))) + str(isinstance(e, ZeroDivisionError))


for n in range(5):
    print(n, caught_by(n))
print(crossed(Overflow("o")), crossed(Inexact("i")), crossed(Underflow("u")))
for error in [Overflow("o"), Underflow("u"), DivisionByZero("d", 2)]:
    print(as_signal(error), isinstance(error, (Rounded, ZeroDivisionError)), repr(error))
zero = DivisionByZero("d", 5)
print(zero.places, isinstance(zero, ArithmeticError), isinstance(zero, Inexact))
for cls in [Overflow, Underflow, DivisionByZero, Conversion, Tagged]:
    print(cls.__name__, [subclass(cls, target) for target in [Signal, Rounded, Inexact, ZeroDivisionError, TypeError, Marker, ValueError, ArithmeticError]])
try:
    raise DivisionByZero("uncaught kind")
except (KeyError, ZeroDivisionError) as e:
    print("tuple", type(e).__name__, e)
