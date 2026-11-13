# error: a bytes value cannot become an Any value
# A default is an Any value of the module, which is compiled with dynamic Any: bytes are not
# among them yet (docs/dynamic-any.md)
import inspect

print(inspect.Parameter("data", inspect.Parameter.KEYWORD_ONLY, default=b"ab"))
