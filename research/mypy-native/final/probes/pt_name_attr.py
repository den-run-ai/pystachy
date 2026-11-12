from typing import Final
class NotSetType:
    pass
NOTSET: Final = NotSetType()
class Pytester:
    CLOSE_STDIN: Final = NOTSET
class Testdir:
    CLOSE_STDIN: Final = Pytester.CLOSE_STDIN
print(Pytester.CLOSE_STDIN is NOTSET, Testdir.CLOSE_STDIN is NOTSET)
