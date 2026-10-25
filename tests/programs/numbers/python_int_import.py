# The importing module deliberately retains the default native-int contract.
from promoting_module import factorial
value = factorial(30)
print(value)
print(value + 1)
print(1 + value)
print([value, value + 2])
