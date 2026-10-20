# error: lib_struct_dynamic.py:6: error: struct.unpack() of a format not known as the program compiles is not supported: the format decides the types of the values (a literal, a module's constant or a Struct's format is known)
import struct


def f(fmt: str, b: bytes) -> None:
    print(struct.unpack(fmt, b))


f("<H", b"ab")
