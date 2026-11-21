# error: is formatting with a format string computed at run time, which is not supported
# value % x, where value may be a str and x is no number: CPython formats with value.
import json

print(json.loads("7") % "x")
