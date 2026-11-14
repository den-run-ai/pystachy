# error: Popen.__init__() got an unexpected keyword argument 'text'
# A Popen's pipes carry bytes: it has no text mode (text, universal_newlines, encoding and
# errors), which would make communicate() return another type. run() and check_output() have
# it, and communicate()'s bytes can be decoded.
import subprocess

p = subprocess.Popen(["sh", "-c", "echo x"], stdout=subprocess.PIPE, text=True)
print(p.communicate())
