# error: object has no method '_radd'
# lib's complex class has only CPython's methods: _radd is no attribute of a complex number, whose
# call CPython rejects with AttributeError, and an unknown method of a complex number is an error
c = 1j
print(c._radd(2.0))
