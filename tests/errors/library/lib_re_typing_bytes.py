# error: lib_re_typing_bytes.py:6: error: unsupported type annotation
import re
from typing import Pattern


def read(pattern: Pattern[bytes]) -> int:
    return pattern.groups


print(read(re.compile("a")))
