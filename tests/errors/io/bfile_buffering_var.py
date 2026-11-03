# error: open() of a binary mode is only supported with a literal int buffering=
import sys

f = open("x.bin", "rb", len(sys.argv))
