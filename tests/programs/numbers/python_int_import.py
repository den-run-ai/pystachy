# The importing module deliberately retains the default native-int contract.
# The corresponding wide typed-list display lives in fixed_import_list, exercised by
# python_int_lists.py: programs with dynamic Any keep list items within 64 bits.
from promoting_module import factorial
value = factorial(30)
print(value)
print(value + 1)
print(1 + value)
