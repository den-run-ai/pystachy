# error: unsupported type annotation
# (bytes | bytearray is a parameter's annotation, where each call decides the type: a variable holds one)
def main() -> None:
    data: bytes | bytearray = b"abc"
    print(len(data))


main()
