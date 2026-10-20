# stdout is /dev/full: input() writes the prompt and flushes stdout, ignoring the failure, then
# reads; the kept prompt fails again at exit, which is reported (status 120)
import sys

s = input("name? ")
sys.stderr.write("got " + s + "\n")
