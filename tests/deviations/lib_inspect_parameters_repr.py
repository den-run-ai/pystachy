# Documented deviation (lib/compatibility.md#inspect): a signature's parameters are a read-only
# view of a dict, which keeps their order, where CPython's is a view of an OrderedDict: it
# prints OrderedDict({'a': <Parameter "a">}) and mappingproxy(OrderedDict({'a': <Parameter "a">})).
import inspect

sig = inspect.Signature([inspect.Parameter("a", inspect.Parameter.POSITIONAL_OR_KEYWORD)])
print(sig.parameters)
print(repr(sig.parameters), list(sig.parameters), len(sig.parameters))
