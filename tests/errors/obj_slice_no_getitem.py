# error: 'C' object is not subscriptable
class C:
    pass


print(C()[1:2])
