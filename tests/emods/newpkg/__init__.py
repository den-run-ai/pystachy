class Failed(Exception):
    def __new__(cls, msg: str) -> "Failed":
        print("new called")
        return super().__new__(cls, msg)


class Retry(Failed):
    "inherits Failed.__new__"
