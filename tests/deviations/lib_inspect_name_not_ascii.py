# Documented deviation (lib/compatibility.md#inspect): a parameter's name is tested as an
# identifier over ASCII only, as str.isidentifier() is not supported and the module has no
# tables of the other characters that identifiers hold. A name that only such characters could
# make an identifier raises NotImplementedError, where CPython takes "café" (and prints it)
# and raises ValueError for "x²". A character of ASCII that no identifier holds is still
# CPython's ValueError, whatever the others are.
import inspect

K = inspect.Parameter.POSITIONAL_OR_KEYWORD
try:
    inspect.Parameter("é b", K)
except ValueError as e:
    print("ValueError:", e)
for name in ["café", "x²"]:
    try:
        print(inspect.Parameter(name, K))
    except NotImplementedError as e:
        print("NotImplementedError:", e)
    except ValueError as e:
        print("ValueError:", e)
