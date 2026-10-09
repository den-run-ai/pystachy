# error: syntax_debug_type_param.py:6: error: cannot assign to __debug__
# a type parameter is assigned when the def runs
def g(x):
    def h[T](y: T) -> T:
        return y
    def k[__debug__]():
        pass


print("ran")
