# inspect.Parameter: its properties, str() and repr() for each kind, and CPython's errors for a
# name or a kind it does not take, with their messages
import inspect

P = inspect.Parameter
kinds = [P.POSITIONAL_ONLY, P.POSITIONAL_OR_KEYWORD, P.VAR_POSITIONAL, P.KEYWORD_ONLY, P.VAR_KEYWORD]
for kind in kinds:
    p = P("x", kind)
    print(p, repr(p), p.name, p.kind, p.default, p.annotation, p.default is P.empty, p.annotation is P.empty)
    q = P("y", kind, annotation="int")
    print(q, repr(q), q.annotation, q.default is P.empty)
for kind in [P.POSITIONAL_ONLY, P.POSITIONAL_OR_KEYWORD, P.KEYWORD_ONLY]:
    print(P("x", kind, default=1), P("x", kind, default="s", annotation="str"), repr(P("x", kind, default=None)),
          P(name="n", kind=kind, annotation=None, default=2.5))
for kind in [P.VAR_POSITIONAL, P.VAR_KEYWORD]:
    try:
        P("x", kind, default=1)
    except ValueError as e:
        print("ValueError:", e)
    # (None is a default too)
    try:
        P("x", kind, default=None)
    except ValueError as e:
        print("ValueError:", e)

# names: an identifier that is no keyword, but for a positional-only parameter
for name in ["a", "_", "_a1", "A9", "match", "type", "__x__"]:
    print(P(name, P.KEYWORD_ONLY))
for name in ["1a", "a b", "a-b", "a.b", "class", "None", "import", " a", "a$", "$a", ".", ".x", "0"]:
    try:
        print(P(name, P.POSITIONAL_OR_KEYWORD))
    except ValueError as e:
        print("ValueError:", e)
print(P("class", P.POSITIONAL_ONLY), P("None", P.POSITIONAL_ONLY, default=0))
try:
    P("", P.KEYWORD_ONLY)
except IndexError as e:
    print("IndexError:", e)

# a comprehension's implicit argument: positional-only, renamed
i = P(".0", P.POSITIONAL_OR_KEYWORD)
print(i, i.name, i.kind, P(".12", P.POSITIONAL_OR_KEYWORD, default=3))
for kind in [P.POSITIONAL_ONLY, P.KEYWORD_ONLY, P.VAR_KEYWORD]:
    try:
        P(".0", kind)
    except ValueError as e:
        print("ValueError:", e)

# a name that is no str, and no kind
try:
    P(3, P.KEYWORD_ONLY)
except TypeError as e:
    print("TypeError:", e)
try:
    P(None, P.KEYWORD_ONLY)
except TypeError as e:
    print("TypeError:", e)
try:
    P(["a"], P.KEYWORD_ONLY)
except TypeError as e:
    print("TypeError:", e)
try:
    P(P.empty, P.KEYWORD_ONLY)
except ValueError as e:
    print("ValueError:", e)
try:
    P("x", None)
except ValueError as e:
    print("ValueError:", e)
# the kind is looked at first, then the default, then the name
try:
    P(3, None, default=1)
except ValueError as e:
    print("ValueError:", e)
try:
    P(3, P.VAR_KEYWORD, default=1)
except ValueError as e:
    print("ValueError:", e)

p = P("x", P.KEYWORD_ONLY, default=1)
try:
    p.name = "y"
except AttributeError as e:
    print("AttributeError:", e)
print(p.name, isinstance(p, inspect.Parameter), isinstance(p, P))
