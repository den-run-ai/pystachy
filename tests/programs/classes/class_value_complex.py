# complex is a builtin class whose numbers are objects of lib's class (lib/_pystachy_complex.py),
# as range's are: type(1j) is its class object, the one that the name complex gives as a value
k = type(1j)
print(k, k.__name__, k.__module__)
print(k is complex, k == complex, k is int, k != complex)
c: type = complex
print(isinstance(2j, c), isinstance(2, c), isinstance(2j, k))
print(issubclass(k, c), issubclass(k, object), issubclass(k, int))
reg = {complex: "c", int: "i"}
print(reg[type(3j)], reg[type(3)])
ks: list[type] = [int, complex, str]
print([x.__name__ for x in ks], type(1j) in ks, ks.index(type(5j)))
print(hash(k) == hash(complex), {type(1j), complex, int} == {complex, int})
