# error: expected list[Parameter] | None, got tuple[Parameter,Parameter]
# A signature takes its parameters as a list or None, where CPython takes any iterable
import inspect

a = inspect.Parameter("a", inspect.Parameter.POSITIONAL_OR_KEYWORD)
b = inspect.Parameter("b", inspect.Parameter.KEYWORD_ONLY)
print(inspect.Signature((a, b)))
