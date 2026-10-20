# error: emods/deep_lambdas.py:5: error: functions, lambdas, classes and constant tuples nested too deeply
# CPython's import of the module fails when it writes its bytecode (the main program is not marshaled)
import emods.deep_lambdas

print(emods.deep_lambdas.V)
