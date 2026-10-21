# error: expected dict[int,int], got dict[int,str]
# lib/textwrap's unicode_whitespace_trans maps code points to code points, the type of its default
# (dict.fromkeys() of the whitespace's code points, to ord(' ')): a str value, which CPython's
# str.translate() takes, is a type error (lib/README.md)
import textwrap

table: dict[int, str] = {ord("x"): "yz"}
w = textwrap.TextWrapper(width=10)
w.unicode_whitespace_trans = table
print(w.wrap("axbxc"))
