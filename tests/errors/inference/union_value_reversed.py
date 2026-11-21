# error: reversed() of a closed union value
import json

for x in reversed(json.loads("[1, 2]")):
    print(x)
