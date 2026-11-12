from typing import Final
class E(Exception):
    CODE: Final = 7
    NAMES: Final = ["a"]
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg: Final = msg
try:
    raise E("boom")
except E as e:
    print(e.CODE, e.NAMES, e.msg)
