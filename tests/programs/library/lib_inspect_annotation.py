# annotations of a parameter and a signature: a builtin class is written by its name, as
# formatannotation() writes it, and another value by its repr()
import inspect

P = inspect.Parameter
K = P.POSITIONAL_OR_KEYWORD
print(P("x", K, annotation=int), P("x", K, annotation=str, default="s"), P("x", K, annotation="int"),
      P("x", K, annotation=None), P("x", K, annotation=3.5), P("x", K, annotation=(1, "a")), P("x", K, annotation=True))
print(P("x", P.VAR_POSITIONAL, annotation=float), P("x", P.VAR_KEYWORD, annotation=object),
      P("x", P.KEYWORD_ONLY, annotation=bool, default=None), repr(P("x", K, annotation=list, default=0)))
print(inspect.Signature([P("x", K, annotation=int), P("y", P.KEYWORD_ONLY, annotation=dict, default=None)],
                        return_annotation=bool))
print(inspect.Signature(return_annotation="None"), inspect.Signature(return_annotation=None),
      inspect.Signature(return_annotation=tuple), inspect.Signature(return_annotation=0),
      repr(inspect.Signature(return_annotation=str)))
print(inspect.formatannotation(int), inspect.formatannotation("x"), inspect.formatannotation(list, "builtins"),
      inspect.formatannotation(dict, "m"), inspect.formatannotation(None), inspect.formatannotation(1.5),
      inspect.formatannotation(set, None), inspect.formatannotation(bytes), inspect.formatannotation(type))
p = P("x", K, annotation=int)
print(p.annotation is int, p.annotation is str, p.annotation == int, p.annotation is P.empty, p.annotation)
print(P("x", K, annotation=int) == P("x", K, annotation=int), P("x", K, annotation=int) == P("x", K, annotation=str),
      hash(P("x", K, annotation=int)) == hash(P("x", K, annotation=int)))
