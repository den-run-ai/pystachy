# error: copy.copy() of an exception object is not supported
# CPython copies an exception through BaseException.__reduce__ (printing x)
import copy


class AppError(Exception):
    pass


print(copy.copy(AppError("x")))
