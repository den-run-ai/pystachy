# Runtime-length Match.groups() results compile without changing the library body.
import re

m = re.match("(a)(b)", "ab")
print(m.groups() if m is not None else None)
