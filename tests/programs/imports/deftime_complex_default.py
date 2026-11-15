# A complex parameter whose default is an int, in an imported module: the default runs when the
# def statement does, and calls that pass a complex number work. The program compiled while
# complex annotations were unsupported, and still does.
print("main: start")
import defmods.complexdefault as cd

print(cd.raw(2 + 1j), cd.raw(complex(0.5, 0)))
