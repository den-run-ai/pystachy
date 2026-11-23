# error: read() returns both bytes and str (each function has one return type) (compiling Codec.read(str, bool) for the call at tests/errors/inference/select_result_static_method.py:11)
# A static method keeps one return type.
class Codec:
    @staticmethod
    def read(text: str, binary: bool = False):
        if binary:
            return text.encode()
        return text


print(Codec.read("a"), Codec.read("b", True))
