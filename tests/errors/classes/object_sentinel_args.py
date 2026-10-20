# error: object() takes no arguments
# CPython raises TypeError where the call runs; Pystachy rejects it where it compiles it
print(object(1))
