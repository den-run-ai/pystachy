# Builtin singleton identity survives aliases, calls and allocations, including GC stress.
import sys
from sys import version_info
from mods.version_reader import version


def read_version() -> tuple[int, int, int, str, int]:
    return sys.version_info


saved = read_version()
print(sys.version_info is sys.version_info, saved is version_info, version() is saved)
for i in range(100):
    values = [str(i), str(i + 1)]
    assert read_version() is saved
    assert saved[3] == "final"
print(saved is read_version(), values, saved[:2] == version_info[:2])
