# error: StoreError() with more than three arguments is not supported
class StoreError(OSError):
    pass


raise StoreError(2, "no such file", "a", None)
