# error: 'mpz' object has no attribute '_handle'
from mpz import mpz
value = mpz(1)
value._handle = 0
