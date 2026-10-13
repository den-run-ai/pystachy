# Documented deviations of lib/io's StringIO (Pystachy's own) from CPython's.
import io

# Positions and sizes count a str's bytes past ASCII, as len() and slicing do in Pystachy; CPython
# counts characters, and prints hél 3, then 5 5, then 'éll'.
s = io.StringIO("héllo")
print(s.read(3), s.tell())
print(s.seek(0, 2), len("héllo"))
s.seek(1)
print(repr(s.read(3)))

# A for loop reads the lines left when it starts (iterator classes are not supported), so a
# readline() in its body finds none left; CPython reads each line as the loop asks for it, and
# prints 1 '2\n' and 3 '4\n'.
s = io.StringIO("1\n2\n3\n4\n")
for line in s:
    print(line.strip(), repr(s.readline()))
