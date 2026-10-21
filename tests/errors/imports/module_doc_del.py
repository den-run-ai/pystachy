# error: deleting the module's __doc__ is not supported (CPython's code then reads builtins.__doc__)
"""A docstring."""
del __doc__
print(__doc__)
