# Documented deviations of lib/string (CPython 3.13's string with marked edits) from CPython.
from string import Template, capwords

# Template.flags is lib/re's int: CPython prints re.IGNORECASE.
print(Template.flags)

# capwords() capitalizes ASCII letters alone, as str.capitalize() does: CPython prints
# Élan Vital.
print(capwords("\xe9lan vital"))
