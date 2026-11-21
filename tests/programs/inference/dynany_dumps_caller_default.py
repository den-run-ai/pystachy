# Deliberately no dynamic-any directive (see dynany_dumps_caller.py): the dynamic encoder's
# default= callback, which json's JSONValue function has not, is reachable from a module that
# does not opt in once the document is Any values.
import json

import dumpsvalues

print(json.dumps(dumpsvalues.with_point(), default=dumpsvalues.encode))
print(json.dumps(dumpsvalues.point(), default=dumpsvalues.encode, sort_keys=True))
try:
    json.dumps(dumpsvalues.with_point())
except TypeError as e:
    print("TypeError", e)
