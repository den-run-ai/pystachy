# == and hash() of inspect.Parameter and inspect.Signature: a parameter's four fields; a
# signature's parameters, in order but for the keyword-only ones, and its return annotation
import inspect

P = inspect.Parameter
PK, KO = P.POSITIONAL_OR_KEYWORD, P.KEYWORD_ONLY

a1 = P("a", PK, default=1)
a2 = P("a", PK, default=1)
print(a1 == a2, a1 != a2, a1 is a2, hash(a1) == hash(a2), a1 == a1, hash(a1) == hash(a1))
print(a1 == P("b", PK, default=1), a1 == P("a", KO, default=1), a1 == P("a", PK, default=2), a1 == P("a", PK),
      a1 == P("a", PK, default=1, annotation="int"), a1 == P("a", PK, default=1.0), a1 == P("a", PK, default=True),
      a1 == P("a", PK, default="1"), a1 != P("a", PK, default=2))
print(P("a", PK) == P("a", PK), P("a", PK, default=None) == P("a", PK), P("a", PK, default=None) == P("a", PK, default=None),
      P("a", PK, annotation="x") == P("a", PK, annotation="x"), P("a", PK, annotation="x") == P("a", PK, annotation="y"))
print(P("t", PK, default=(1, "x")) == P("t", PK, default=(1, "x")), P("t", PK, default=(1, "x")) == P("t", PK, default=(1, "y")),
      P("l", PK, default=[1, 2]) == P("l", PK, default=[1, 2]), P("l", PK, default=[1, 2]) == P("l", PK, default=[1]))
print(hash(P("a", PK, default=1.0)) == hash(a1), hash(P("a", PK, default=None)) == hash(P("a", PK, default=None)),
      hash(P("t", PK, default=(1, "x"))) == hash(P("t", PK, default=(1, "x"))), hash(P("a", PK)) == hash(P("a", PK)))
print(a1 == 1, a1 == "a", a1 == None, a1 != None, a1 == inspect.Signature([a1]))
print(a1 in [a2], [a1].index(a2), [a1, P("b", PK)].count(a2), P("zz", PK) in [a1, a2])
d = {a1: "first"}
d[a2] = "second"
print(len(d), d[P("a", PK, default=1)], P("a", PK, default=2) in d, len({a1, a2, P("b", KO)}))
try:
    hash(P("u", PK, default=[1]))
except TypeError as e:
    print("TypeError:", e)

k1 = P("k", KO)
k2 = P("j", KO, default=0)
s1 = inspect.Signature([a1, k1, k2])
s2 = inspect.Signature([a2, k2, P("k", KO)])
s3 = inspect.Signature([a2, k1])
print(s1 == s2, s1 != s2, hash(s1) == hash(s2), s1 == s3, s1 != s3, s1 == s1, s1 is s2, str(s1) == str(s2))
print(inspect.Signature() == inspect.Signature(), inspect.Signature() == inspect.Signature([]),
      hash(inspect.Signature()) == hash(inspect.Signature(None)), inspect.Signature() == inspect.Signature([a1]))
print(inspect.Signature([a1], return_annotation="x") == inspect.Signature([a2], return_annotation="x"),
      hash(inspect.Signature([a1], return_annotation="x")) == hash(inspect.Signature([a2], return_annotation="x")),
      inspect.Signature([a1], return_annotation="x") == inspect.Signature([a1]),
      inspect.Signature([a1], return_annotation="x") == inspect.Signature([a1], return_annotation="y"),
      inspect.Signature([a1, P("b", PK, default=2)]) == inspect.Signature([P("b", PK, default=2), a1]))
print(len({s1: 1, s2: 2}), s1 in [s2], s3 in [s1, s2], s1 == a1, s1 == None, s1 == "(a=1, *, k, j=0)")
