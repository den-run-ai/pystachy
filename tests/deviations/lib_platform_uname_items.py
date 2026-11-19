# Documented deviation: platform.uname() has CPython's first five items, without the processor
# that CPython 3.13 adds as a sixth from the command uname -p (lib/compatibility.md#platform).
import platform

print(len(platform.uname()), platform.uname()._fields)
