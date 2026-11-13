# inspect._ParameterKind: an IntEnum of five members numbered from 0, whose str() is the name,
# with a description; Parameter's class attributes and the module's constants are its members
import inspect

K = inspect._ParameterKind
print(list(K), len(K))
for k in K:
    print(k, repr(k), k.name, k.value, k.description, str(k), f"{k}", f"{k!r}", "%s" % k, format(k, "d"), k == k.value,
          k < 3, k >= inspect.Parameter.VAR_POSITIONAL, k + 1, hash(k) == hash(k.value), bool(k))
print(K(3), K["VAR_KEYWORD"], K(inspect.Parameter.POSITIONAL_ONLY), K.KEYWORD_ONLY in K, 4 in K, 5 in K)
try:
    K(5)
except ValueError as e:
    print("ValueError:", e)
print(inspect._POSITIONAL_ONLY, inspect._POSITIONAL_OR_KEYWORD, inspect._VAR_POSITIONAL, inspect._KEYWORD_ONLY,
      inspect._VAR_KEYWORD)
P = inspect.Parameter
print(inspect._POSITIONAL_ONLY is P.POSITIONAL_ONLY, inspect._POSITIONAL_OR_KEYWORD is P.POSITIONAL_OR_KEYWORD,
      inspect._VAR_POSITIONAL is P.VAR_POSITIONAL, inspect._KEYWORD_ONLY is P.KEYWORD_ONLY,
      inspect._VAR_KEYWORD is P.VAR_KEYWORD, P.KEYWORD_ONLY is K.KEYWORD_ONLY, P.KEYWORD_ONLY is P.VAR_KEYWORD)
print(P.POSITIONAL_ONLY < P.POSITIONAL_OR_KEYWORD < P.VAR_POSITIONAL < P.KEYWORD_ONLY < P.VAR_KEYWORD,
      sorted([P.VAR_KEYWORD, P.POSITIONAL_ONLY, P.KEYWORD_ONLY]), max(P.VAR_POSITIONAL, P.POSITIONAL_ONLY))
kind: inspect._ParameterKind = P.POSITIONAL_OR_KEYWORD
p = P("x", kind)
print(p.kind is kind, p.kind.description, p.kind.name, p.kind.value, p.kind in (P.POSITIONAL_ONLY, P.POSITIONAL_OR_KEYWORD),
      p.kind in (P.KEYWORD_ONLY, P.VAR_KEYWORD), P("y", P.VAR_POSITIONAL).kind.description)
names = {P.POSITIONAL_ONLY: "po", P.KEYWORD_ONLY: "ko"}
print(names[P("z", P.KEYWORD_ONLY).kind], P("z", P.VAR_KEYWORD).kind in names)
