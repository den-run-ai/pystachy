# error: name 'unicode' is not defined
# A try that reads a name nothing binds is decided at compile time only where its handler does
# not re-raise the NameError (a bare raise), which needs the exception
try:
    unicode  # noqa: F821
except NameError:
    print("Python 3")
    raise
