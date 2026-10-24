# error: a base that defines __init_subclass__ is not supported (CPython calls mpz.__init_subclass__() when it creates class Child)
from mpz import mpz
class Child(mpz):
    pass
print(Child(1))
