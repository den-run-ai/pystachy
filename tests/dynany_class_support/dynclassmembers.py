# Classes of a module that does not opt in to dynamic Any, whose class objects an opted-in
# program holds as Any values: none of these methods is called by a typed call.


class Codec:
    name = "codec"
    version = 2

    @staticmethod
    def shout(text: str, times: int = 1) -> str:
        return (text + "!") * times

    @classmethod
    def describe(cls) -> str:
        return cls.name + " v" + str(cls.version) + " of " + cls.__name__

    @staticmethod
    def helper_chain(n: int) -> int:
        return double(n) + 1


class Loud(Codec):
    name = "loud"

    @staticmethod
    def shout(text: str, times: int = 1) -> str:
        return text.upper() * times


def double(n: int) -> int:
    return 2 * n
