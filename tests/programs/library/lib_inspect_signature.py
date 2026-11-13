# inspect.Signature: the order of its parameters' kinds, defaults and names, as CPython checks
# them, with its messages; str(), repr() and format() with its separators, and the parameters as
# a read-only mapping in their order
import inspect

P = inspect.Parameter
PO, PK, VP, KO, VK = P.POSITIONAL_ONLY, P.POSITIONAL_OR_KEYWORD, P.VAR_POSITIONAL, P.KEYWORD_ONLY, P.VAR_KEYWORD


def sig(ps: list[inspect.Parameter]) -> str:
    try:
        return str(inspect.Signature(ps))
    except ValueError as e:
        return "ValueError: " + str(e)


a = P("a", PO)
b = P("b", PK)
c = P("c", PK, default=0)
args = P("args", VP)
k = P("k", KO)
kd = P("kd", KO, default="x")
kw = P("kw", VK)
everything = [a, b, c, args, k, kd, kw]
print(sig([]), sig([a]), sig([a, b]), sig([b]), sig(everything))
print(sig([args]), sig([k]), sig([kw]), sig([a, k]), sig([b, kd, k]), sig([args, kw]), sig([a, kw]), sig([a, args]))
print(sig([c, args, P("d", KO)]), sig([P("x", PO, default=1), c]), sig([kd, k, kw]))
for wrong in [[b, a], [k, b], [kw, k], [args, a], [kw, args], [k, args], [c, b], [P("x", PO, default=1), b],
              [b, P("b", KO)], [args, P("args", VK)], [a, P("a", PO)], [kw, a, a]]:
    print(sig(wrong))
# (a list is not changed, and one parameter may be in many signatures)
print(len(everything), sig(everything) == sig(everything))

s = inspect.Signature(everything, return_annotation="int")
print(s, repr(s), str(s) == s.format(), s.format(max_width=None) == str(s))
print(s.format(max_width=20))
print(s.format(max_width=200), s.format(max_width=len(str(s))) == str(s))
print(inspect.Signature([a]).format(max_width=1))
print(repr(inspect.Signature().format(max_width=0)), repr(inspect.Signature().format(max_width=2)))
print(inspect.Signature(), repr(inspect.Signature()), inspect.Signature(None), inspect.Signature(parameters=[k]),
      inspect.Signature(parameters=None, return_annotation=1), inspect.Signature([], return_annotation=None))
print(s.return_annotation, inspect.Signature().return_annotation,
      inspect.Signature().return_annotation is inspect.Signature.empty, s.return_annotation is inspect.Signature.empty,
      isinstance(s, inspect.Signature))

m = s.parameters
print(len(m), list(m), "a" in m, "z" in m, m["kd"], m.get("zz"), m.get("kw"), m["a"] is a, m is s.parameters)
print([name for name in m], [str(p) for p in m.values()], [(n, p.kind.name) for n, p in m.items()], list(m.keys()))
try:
    m["nope"]
except KeyError as e:
    print("KeyError:", e)
# without the checks: a later parameter takes an earlier one's name
u = inspect.Signature([b, P("b", KO), a], __validate_parameters__=False)
print(u, len(u.parameters), u.parameters["b"].kind)
