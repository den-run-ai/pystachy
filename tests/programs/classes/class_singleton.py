# a module-level class rebound to its instance, as enum's _not_given is (class C: ... directly
# followed by C = C()): from then on the name is the instance, while the class keeps its name
import mods.sentinels as sentinels
from mods.sentinels import MISSING, Plain, auto, is_missing


def early():
    # (defined before the class statement: unbound before it runs, the instance after the rebinding)
    return _not_given


try:
    early()
except NameError as e:
    print(e)


class _not_given:
    limit = 3

    def __repr__(self) -> str:
        return('<not given>')

    def me(self) -> bool:
        return self is _not_given
_not_given = _not_given()


class Counter:
    calls: int = 0

    def __call__(self) -> int:
        self.calls += 1
        return self.calls
Counter = Counter()


class Token(object):
    def __repr__(self) -> str:
        return "<token " + type(self).__name__ + ">"
Token = Token()


def check(names: object = _not_given) -> str:
    if names is _not_given:
        return "not given"
    return "given"


print(_not_given)
print(repr(_not_given), str(_not_given), f"{_not_given!r} {_not_given}")
print(type(_not_given).__name__, type(_not_given).__qualname__, type(_not_given).__module__)
print(_not_given.__class__.__name__, _not_given.__repr__.__qualname__)
print(check(), check(None), check(_not_given))
print(_not_given.me(), early() is _not_given, _not_given.limit)
print(_not_given is _not_given, _not_given == _not_given, _not_given != _not_given)
print(isinstance(_not_given, object), type(_not_given) == type(Counter), type(_not_given) == type(_not_given))
print(Counter(), Counter(), Counter.calls, type(Counter).__name__)
print({_not_given: 1}[_not_given], len({_not_given, _not_given}))
print(Token, type(Token).__qualname__)

a = auto()
b = auto(MISSING)
print(a.value, a.given(), b.given(), a.value is sentinels._auto_null)
print(MISSING, bool(MISSING), not MISSING, is_missing(MISSING), is_missing(a))
print(type(MISSING).__name__, type(MISSING).__qualname__, type(MISSING).__module__)
print(type(sentinels._auto_null).__module__, type(sentinels._auto_null).__name__)
print(MISSING.__bool__.__qualname__, MISSING.__bool__())
print(repr(Plain).startswith("<mods.sentinels.Plain object at 0x"), type(Plain).__qualname__)
