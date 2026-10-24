# error: mpz.__init__() is a method of its objects: calling it through the class is not supported; call it on an object, o.__init__(...)
from mpz import mpz
value = mpz(1)
mpz.__init__(value, 2)
