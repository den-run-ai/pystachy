# sys.prefix, sys.base_prefix, sys.exec_prefix and sys.base_exec_prefix: one absolute directory
# outside a virtual environment, of which gettext makes its default locale directory
import os
import sys
from sys import base_prefix

print(sys.prefix == sys.base_prefix == sys.exec_prefix == sys.base_exec_prefix)
print(sys.prefix.startswith("/"), base_prefix == sys.base_prefix, type(sys.exec_prefix).__name__)
localedir = os.path.join(sys.base_prefix, "share", "locale")
print(localedir.endswith("/share/locale"), localedir.startswith(sys.base_prefix), len(sys.prefix) > 0)
