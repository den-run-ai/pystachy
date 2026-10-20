# error: none_format_spec_type.py:4: error: unsupported operand type(s) for +: 'int' and 'str'
# The computed spec of a field of None is compiled, as for any value (none_format_spec.py): CPython
# raises this TypeError as it evaluates the spec
print(f'{None:{1 + "a"}}')
