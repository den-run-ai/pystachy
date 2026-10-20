# error: object of type 'C' has no len()
class C:
    pass


print(len(C()))
