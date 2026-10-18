# StringIO read sizes and positions count code points.
import io

s = io.StringIO("héllo")
print(s.read(3), s.tell())
print(s.seek(0, 2), len("héllo"))
s.seek(1)
print(repr(s.read(3)))
