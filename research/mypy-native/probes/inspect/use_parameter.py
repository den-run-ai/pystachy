import inspect

p = inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=5)
print(p, repr(p), p.name, p.kind, p.default, p.default is inspect.Parameter.empty)
q = inspect.Parameter("y", inspect.Parameter.KEYWORD_ONLY)
print(q, q.default is inspect.Parameter.empty, repr(q.kind))
ps = [p, q, inspect.Parameter("args", inspect.Parameter.VAR_POSITIONAL), inspect.Parameter("s", inspect.Parameter.KEYWORD_ONLY, default="t", annotation="str"),
      inspect.Parameter("n", inspect.Parameter.KEYWORD_ONLY, default=None), inspect.Parameter("f", inspect.Parameter.KEYWORD_ONLY, default=1.5)]
print([str(x) for x in ps])
try:
    inspect.Parameter("class", inspect.Parameter.KEYWORD_ONLY)
except ValueError as e:
    print("ValueError", e)
try:
    inspect.Parameter("a", inspect.Parameter.VAR_KEYWORD, default=1)
except ValueError as e:
    print("ValueError", e)
