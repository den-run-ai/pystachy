# Raising UnicodeDecodeError with its five arguments, and catching UnicodeEncodeError
def check(data: bytes) -> str:
    try:
        data.decode()
    except UnicodeDecodeError:
        raise UnicodeDecodeError("utf-8", data, 2, 3, "invalid utf-8")
    return "ok"


try:
    check(b"x=\xff")
except UnicodeDecodeError as e:
    print("UnicodeDecodeError", e)


def enc(s: str) -> bytes:
    try:
        return s.encode()
    except UnicodeEncodeError:
        raise TypeError("Source must be str or bytes")


print(enc("abc"))
