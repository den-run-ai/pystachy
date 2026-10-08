# Documented deviation: int() of a string whose value needs more than 64 bits raises
# OverflowError where CPython would return a big int.
print(int("9223372036854775807"), int("-9223372036854775808"))
print(int("9223372036854775808"))
