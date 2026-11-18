# Parameter.replace() and Signature.replace(): a copy with the fields a call names, which the
# constructor checks as it does a new object's
import inspect

P = inspect.Parameter
p = P("a", P.POSITIONAL_OR_KEYWORD, default=1, annotation="int")
print(p.replace(), p.replace(name="b"), p.replace(kind=P.KEYWORD_ONLY).kind, p.replace(default=2),
      p.replace(annotation=P.empty), p.replace(default=P.empty), p.replace(default=None), p.replace(annotation=None),
      p.replace(name="c", kind=P.POSITIONAL_ONLY, default="d", annotation="str"))
print(p.replace() == p, p.replace() is p, p.replace(default=2) == p, p, p.replace(name=".3").name)
for bad in ["1x", "class", "a b"]:
    try:
        p.replace(name=bad)
    except ValueError as e:
        print("ValueError:", e)
try:
    p.replace(name=5)
except TypeError as e:
    print("TypeError:", e)
try:
    p.replace(name=None)
except TypeError as e:
    print("TypeError:", e)
try:
    p.replace(kind=P.VAR_POSITIONAL)
except ValueError as e:
    print("ValueError:", e)
print(p.replace(kind=P.VAR_KEYWORD, default=P.empty))
try:
    p.replace(kind=None)
except ValueError as e:
    print("ValueError:", e)

q = P("k", P.KEYWORD_ONLY)
sig = inspect.Signature([p, q], return_annotation="bool")
print(sig, sig.replace(), sig.replace(parameters=[q]), sig.replace(return_annotation=inspect.Signature.empty),
      sig.replace(parameters=None), sig.replace(parameters=[]), sig.replace(return_annotation=None),
      sig.replace(parameters=[q, P("z", P.VAR_KEYWORD)], return_annotation=0))
print(sig.replace() == sig, sig.replace() is sig, sig.replace(parameters=[q]) == sig, sig,
      sig.replace().parameters["a"] is p)
try:
    sig.replace(parameters=[q, p])
except ValueError as e:
    print("ValueError:", e)
try:
    sig.replace(parameters=[q, q])
except ValueError as e:
    print("ValueError:", e)
