# error: name 'basestring' is not defined
# A try that reads a name nothing binds is decided at compile time only where its handler does
# not name the NameError (as e), at a module's top level
try:
    string_types = basestring  # noqa: F821
except NameError as e:
    print(e)
    string_types = str
