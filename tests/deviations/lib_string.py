# Documented deviations of lib/string (CPython 3.13's string with marked edits) from CPython.
from string import Template

# Template.flags is lib/re's int: CPython prints re.IGNORECASE.
print(Template.flags)
