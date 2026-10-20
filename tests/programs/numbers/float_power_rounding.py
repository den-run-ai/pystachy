# Runtime inputs exercise LLVM's pow -> multiply, reciprocal and exp2 rewrites
# (#656). Literal-only inputs can be folded by the compiler and miss AOT drift.
import math

x = float(input())
print('square', repr(x ** 2), repr(pow(x, 2.0)), repr(math.pow(x, 2.0)))
x = float(input())
print('reciprocal', repr(x ** -1.0), repr(pow(x, -1.0)), repr(math.pow(x, -1.0)))
y = float(input())
print('base two', repr(2.0 ** y), repr(pow(2.0, y)), repr(math.pow(2.0, y)))

# Each exponent is constant at its call site, even with the values read at run time.
# Signed zero and exceptional values must still keep Python's power semantics.
for s in ['-0.0', '0.0', '-inf', 'inf', 'nan']:
    x = float(s)
    print(s, repr(x ** 2), repr(math.pow(x, 2.0)))
    try:
        print('operator reciprocal', repr(x ** -1.0))
    except ZeroDivisionError as e:
        print('ZeroDivisionError:', e)
    try:
        print('math reciprocal', repr(math.pow(x, -1.0)))
    except ValueError as e:
        print('ValueError:', e)

