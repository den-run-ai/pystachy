import sys
from typing import Final
if sys.platform == "win32":
    SEP: Final = "\\"
else:
    SEP: Final = "/"
print(SEP)
