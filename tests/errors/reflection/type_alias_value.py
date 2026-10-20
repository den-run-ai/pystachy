# error: type_alias_value.py:4: error: type alias 'Row' cannot be used as a value (only annotations may name it)
# CPython prints list[str]: the alias object itself is not supported
Row = list[str]
print(Row)
