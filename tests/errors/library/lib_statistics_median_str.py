# error: unsupported operand type(s) for /: 'str' and 'int'
# lib/statistics's median() of strs (lib/README.md): CPython returns the middle str of an odd number
# of them, and raises TypeError for an even number, whose two middle ones it divides
import statistics

print(statistics.median(["b", "a", "c"]))
