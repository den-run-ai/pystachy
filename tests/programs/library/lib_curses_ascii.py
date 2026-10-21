# CPython's own Lib/curses/ascii.py (lib/curses/ascii.py, unmodified; lib/curses/__init__.py is
# Pystachy's: CPython's wraps the C module _curses). Its functions take a str or an int: each
# call compiles them for one, and isinstance(c, str) is decided then.
import curses.ascii
from curses import ascii as ca
from curses.ascii import isalpha, unctrl

for c in ["a", "Z", "5", " ", "\t", "\n", "~", "_", "\x7f", "\x00", "\x1b"]:
    print(repr(c), ca.isalnum(c), isalpha(c), ca.isdigit(c), ca.isspace(c), ca.ispunct(c), ca.iscntrl(c), ca.isprint(c), ca.isgraph(c), ca.isxdigit(c), ca.isupper(c), ca.islower(c), ca.isblank(c), ca.isascii(c), unctrl(c))
for i in [65, 9, 127, 200, 32, 0, 128, 160]:
    print(i, isalpha(i), ca.isspace(i), ca.isctrl(i), ca.ismeta(i), ca.ascii(i), ca.ctrl(i), ca.alt(i), unctrl(i))
print(repr(ca.ctrl("a")), ca.alt("a") == chr(225), ca.ascii("A"), curses.ascii.controlnames[10], ca.NL, ca.DEL, ca.SP, len(ca.controlnames))
