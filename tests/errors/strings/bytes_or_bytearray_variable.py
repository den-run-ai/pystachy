# error: bytes in a closed union is not supported (use scalar, list/dict or native class/file types)
# (bytes | bytearray is a parameter's annotation, where each call decides the type: a variable holds one)
def main() -> None:
    data: bytes | bytearray = b"abc"
    print(len(data))


main()
