# error: StoreError() with more than one argument is not supported
class StoreError(OSError):
    pass


raise StoreError(2, "no such file")
