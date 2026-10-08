# input() without a prompt writes nothing to sys.stdout, so it still reads after
# sys.stdout.close(); with a prompt, writing it raises
import sys

print("before close")
sys.stdout.close()
s = input()
sys.stderr.write("got " + s + "\n")
t = input("prompt? ")
sys.stderr.write("not reached\n")
