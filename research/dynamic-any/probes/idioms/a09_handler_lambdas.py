# pystachy: dynamic-any
# the same registry written with lambdas and no annotation
HANDLERS = {"int": lambda x: x * 2, "str": lambda x: x.upper(), "list": lambda x: len(x)}
values = [3, "abc", [1, 2, 3], 4]
for v in values:
    print(HANDLERS[type(v).__name__](v))
