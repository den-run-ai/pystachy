# A class attribute bound to a function (name = f), as CPython's encodings modules bind their
# codec functions (encode = codecs.latin_1_encode): read and called through its class and a
# subclass, as a value, with keyword arguments, and a builtin function, which CPython does not
# bind to an object either, read through an object too.
def enc(s, errors="strict"):
    return (s, len(s))


def dec(s: str, errors: str = "strict") -> tuple[str, int]:
    return (s.upper(), len(s) if errors == "strict" else -1)


class Codec:
    encode = enc
    decode = dec

    def name(self) -> str:
        return "codec"


class Sub(Codec):
    pass


class Sized:
    size = len


print(Codec.encode("abc"))
print(Codec.decode("xy", errors="ignore"), Codec.decode("pq"))
print(Sub.encode("hello", "replace"), Sub.decode(s="z"))
f = Codec.encode
g = Sub.decode
print(f("value"), g("w"))
print(Codec().name(), Sub().name())
print(Sized.size([1, 2, 3]), Sized().size("abcd"))
