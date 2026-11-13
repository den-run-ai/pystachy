# error: 'inspect.Signature' object has no method 'bind'
# Signature.bind() and BoundArguments take a call's arguments as they run, which a compiled
# call's fixed argument types do not give
import inspect

sig = inspect.Signature([inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD)])
print(sig.bind(1))
