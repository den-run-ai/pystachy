# error: keyword argument 'strict' of os.path.realpath() is not supported
import os.path

print(os.path.realpath(".", strict=True) != "")
