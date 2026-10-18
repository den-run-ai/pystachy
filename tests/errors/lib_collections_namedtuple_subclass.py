# error: lib_collections_namedtuple_subclass.py:6: error: inheritance from a namedtuple() class is not supported
# a class deriving from the class that a namedtuple() call makes (platform's uname_result)
from collections import namedtuple


class Version(namedtuple("Version", "major minor")):
    def __str__(self):
        return f"{self.major}.{self.minor}"


print(Version(3, 13))
