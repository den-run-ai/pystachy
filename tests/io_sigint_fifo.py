# A Ctrl-C (SIGINT) that comes while the program waits in a system call, opening a FIFO that no
# writer opens, ends the wait and raises KeyboardInterrupt there: status 130 in the shell
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/fifo"
r = os.system("mkfifo " + p)
print("waiting")
# a second later the program is waiting in open() (system() ignores SIGINT only while it runs)
r = os.system("(sleep 1; kill -INT " + str(os.getpid()) + "; rm -rf " + d + ") &")
f = open(p)
print("not reached")
