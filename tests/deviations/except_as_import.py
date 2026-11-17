# Documented deviation (#1514): module code's except clause names json, which an import bound, as
# its exception's name. After that handler ran, json still names the module, where CPython unbinds
# it, so json.dumps raises NameError there and CPython prints "NameError name 'json' is not
# defined".
import json

try:
    raise ValueError("x")
except ValueError as json:
    pass
try:
    print(json.dumps([1]))
except NameError as err:
    print("NameError", err)
