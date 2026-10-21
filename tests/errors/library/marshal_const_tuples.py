# error: emods/deep_tuples.py:3: error: functions, lambdas, classes and constant tuples nested too deeply
# A constant tuple nests one level deeper in the bytecode CPython's import writes, a code object two:
# 950 lambdas around tuples nested 100 deep pass its 2,000 levels
import emods.deep_tuples

print(emods.deep_tuples.v)
