# Native runtime KeyError keys and structured errno payloads are not retained.
# Reading their args reports the boundary instead of parsing a formatted repr.
# pystachy: dynamic-any
try:
    print({"one": 1}["missing"])
except KeyError as error:
    try:
        print(error.args)
    except NotImplementedError as boundary:
        print(str(boundary))
    print(str(error), repr(error))

try:
    with open("/pystachy-path-that-does-not-exist-args-test") as source:
        print(source.read())
except OSError as error:
    try:
        print(error.args)
    except NotImplementedError as boundary:
        print(str(boundary))
