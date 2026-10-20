# After a write statement, a write through a method value returns the number of characters it
# writes: in an assignment, a list and an argument (#120)
import sys

w = sys.stdout.write
sys.stdout.write("a\n")
n = w("é\n")
xs: list[int] = [w("日本\n")]
print(n, xs)
sys.stdout.write("b\n")
print(w("ü\n"))
