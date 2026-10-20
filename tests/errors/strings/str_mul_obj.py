# error: can't multiply sequence by non-int of type 'C'
class C:
    pass


print("a" * C())
