# sys.stderr writes a surrogate as \udcff (errors="backslashreplace"), and so does sys.exit's message.
import sys

print("a" + chr(0xD800) + "b", file=sys.stderr)
sys.stderr.write("c" + chr(0xDFFF) + "\n")
print("ok")
sys.exit("bad " + chr(0xDC80) + chr(0xDC81) + "x")
