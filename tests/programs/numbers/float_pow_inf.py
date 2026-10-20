# 0.0 ** -inf is inf (only a finite negative exponent divides by zero).
b = float("-inf")
print(0.0 ** b, (-0.0) ** b, 2.0 ** b, 0.5 ** b)
print(0.0 ** -1.0)
