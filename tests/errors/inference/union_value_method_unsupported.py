# error: str.translate() is not supported, and a closed union's value
# CPython's str has the method, so a str in the union cannot raise AttributeError for it: the
# call is rejected, as str.translate() of a str alone is.
import json

print(json.loads('"abc"').translate({97: "x"}))
