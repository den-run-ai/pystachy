# error: name 'unicode' is not defined
# A name that nothing binds is a compile-time error, also where CPython's NameError would be caught.
try:
    print(unicode("x"))
except NameError as e:
    print("NameError:", e)
