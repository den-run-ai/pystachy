from mpz import mpz

value = mpz(3)
assert value._handle == 3
value._handle = 7
assert str(value) == "7"
value.__init__(11)
assert value._handle == 11
print("user mpz module", value)
