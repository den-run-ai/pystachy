# string.Formatter's get_value() returns a positional or a keyword argument: of an int and
# a str here, so int | str.
import string

print(string.Formatter().format("{0} and {x}", 1, x="b"))
