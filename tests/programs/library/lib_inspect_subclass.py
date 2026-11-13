# classes of the program that derive from inspect.Parameter and inspect.Signature: their objects
# are parameters and signatures, with the class's name in repr() and the methods it adds
import inspect


class Field(inspect.Parameter):
    def shout(self) -> str:
        return self.name.upper()


class Shape(inspect.Signature):
    def arity(self) -> int:
        return len(self.parameters)


f = Field("a", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=1)
g = Field("k", Field.KEYWORD_ONLY, annotation="str")
print(f, repr(f), f.shout(), g, repr(g), g.kind, isinstance(f, inspect.Parameter), isinstance(f, Field),
      f.default is Field.empty, g.default is inspect.Parameter.empty, type(f).__name__)
p = inspect.Parameter("a", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=1)
print(f == p, p == f, hash(f) == hash(p), f == g, isinstance(p, Field))
s = Shape([f, g], return_annotation=None)
print(s, repr(s), s.arity(), isinstance(s, inspect.Signature), s.parameters["a"] is f, type(s).__name__)
t = inspect.Signature([p, g], return_annotation=None)
print(s == t, t == s, hash(s) == hash(t), repr(t), Shape().arity(), repr(Shape()))
try:
    Shape([g, f])
except ValueError as e:
    print("ValueError:", e)
try:
    Field("1", Field.KEYWORD_ONLY)
except ValueError as e:
    print("ValueError:", e)
params: list[inspect.Parameter] = [f, p, g]
print([repr(x) for x in params], inspect.Signature([f, g]))
