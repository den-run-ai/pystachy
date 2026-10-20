# A write through a method value returns the number of characters it writes, also where it
# follows, in one expression, a call of a function whose last statement is a write (#120)
import sys

w = sys.stdout.write


def log(s):
    sys.stdout.write(s)


print(log("x\n"), w("é\n"))
