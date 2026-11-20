# error: invalid flag 'Incomplete': missing values 32
# CPython's ValueError where @verify(CONTINUOUS) runs: a flag's single-bit members skip 32
import enum


@enum.verify(enum.CONTINUOUS)
class Incomplete(enum.Flag):
    FIRST = 4
    SECOND = 8
    THIRD = 16
    FORTH = 64


print(list(Incomplete))
