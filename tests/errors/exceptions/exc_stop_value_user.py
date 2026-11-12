# error: reading inherited StopIteration.value on a user exception is not supported
# pystachy: dynamic-any
class Done(StopIteration):
    pass


print(Done(5).value)
