# error: 'S' object has no attribute 'value': StopIteration's attribute value is not supported
class S(StopIteration):
    pass


print(S(5).value)
