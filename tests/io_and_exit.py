import sys
import os

path = "/tmp/ouro_io_test_" + str(os.getpid()) + ".txt"
f = open(path, "w")
for i in range(3):
    f.write(f"line {i}\n")
f.close()
text = open(path).read()
print(repr(text), len(text.split("\n")))
g = open(path)
print(repr(g.readline()), repr(g.readline()))
g.close()
os.system("rm -f " + path)
print(os.path.exists(path), sys.argv[1:])
name = input("name? ")
age = int(input())
rest = input()
print(f"hello {name}, next year {age + 1}; {rest.upper()}")
sys.stdout.write("written directly\n")
print("to stderr", file=sys.stderr)
sys.exit(3)
