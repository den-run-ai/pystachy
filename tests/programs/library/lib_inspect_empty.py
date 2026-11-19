# Parameter.empty, Signature.empty and inspect._empty are one marker: "is" tells it from every
# default and annotation, None included, and its repr() is that of CPython's class
import inspect

P = inspect.Parameter
print(P.empty is inspect.Signature.empty, P.empty is inspect._empty, inspect.Signature.empty is inspect._empty)
print(P.empty, repr(P.empty), str(inspect.Signature.empty), f"{inspect._empty}", [P.empty], (P.empty, 1))
print(bool(P.empty), P.empty == P.empty, P.empty != inspect._empty, P.empty is None, P.empty is not None)

bare = P("x", P.KEYWORD_ONLY)
none = P("x", P.KEYWORD_ONLY, default=None, annotation=None)
zero = P("x", P.KEYWORD_ONLY, default=0, annotation="")
false = P("x", P.KEYWORD_ONLY, default=False, annotation=False)
given = P("x", P.KEYWORD_ONLY, default=P.empty, annotation=inspect.Signature.empty)
for p in [bare, none, zero, false, given]:
    print(p, p.default is P.empty, p.default is not P.empty, p.default is inspect._empty, p.default == P.empty,
          p.default != P.empty, p.default is None, p.annotation is P.empty, p.annotation is inspect.Signature.empty)
print(bare == given, hash(bare) == hash(given), bare == none)


def has_default(p: inspect.Parameter) -> bool:
    return p.default is not inspect.Parameter.empty


def describe(p: inspect.Parameter) -> str:
    default = p.default
    if default is inspect.Parameter.empty:
        return p.name + ": required"
    return p.name + ": optional, " + repr(default)


print([has_default(p) for p in [bare, none, zero, false, given]], describe(bare), describe(none), describe(zero))
s = inspect.Signature([bare], return_annotation=None)
t = inspect.Signature([bare], return_annotation=inspect.Signature.empty)
print(s, s.return_annotation is inspect.Signature.empty, s.return_annotation is None, t,
      t.return_annotation is inspect.Signature.empty, t.return_annotation is P.empty, t == inspect.Signature([given]))
