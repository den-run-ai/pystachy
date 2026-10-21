# sys.stdout, when it is not a terminal, keeps up to 8 KiB of text pending as CPython does, so
# a command run by os.system (which does not flush stdout first) can print before it.
import os
import sys

print("x" * 5000)
r = os.system("echo first-system")
print("y" * 3000)
r = os.system("echo second-system")
sys.stdout.write("z" * 200)
r = os.system("echo third-system")
print("w" * 9000)
r = os.system("echo fourth-system")
print("short", flush=True)
r = os.system("echo fifth-system")
sys.stdout.write("end\n")
