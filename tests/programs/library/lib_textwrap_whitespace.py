# Default whitespace translation must keep mutable and overridden tables observable.
from textwrap import TextWrapper

w = TextWrapper(expand_tabs=False)
text = "a\tb\nc\x0bd\x0ce\rf g"
print(repr(w._munge_whitespace(text)))
print(repr(w._munge_whitespace(" unchanged ")))
print(repr(w._munge_whitespace("café\n中文\tété")))
w.replace_whitespace = False
print(repr(w._munge_whitespace(text)))
w.replace_whitespace = True

# An alias of the shared default table can change a mapping without replacing the table.
alias = w.unicode_whitespace_trans
alias[ord(' ')] = ord('_')
print(repr(w._munge_whitespace(text)))
alias[ord(' ')] = ord(' ')

# A six-entry override can omit whitespace and map some other character instead.
w.unicode_whitespace_trans = {9: 32, 10: 32, 11: 32, 12: 32, 13: 32, ord('x'): ord('y')}
print(repr(w._munge_whitespace("x\tx x")))
w.unicode_whitespace_trans[ord(' ')] = ord('_')
print(repr(w._munge_whitespace("x\tx x")))
w.unicode_whitespace_trans = {}
print(repr(w._munge_whitespace(text)))

# expandtabs validates its C-int size even when the text has no tabs (or is empty).
for size in [2147483648, -2147483649]:
    overflow = TextWrapper(tabsize=size)
    for text in ["hello", ""]:
        try:
            print(repr(overflow._munge_whitespace(text)))
        except OverflowError as e:
            print(size, repr(text), "OverflowError:", e)
    disabled = TextWrapper(tabsize=size, expand_tabs=False)
    print(size, repr(disabled._munge_whitespace("hello\tthere")))
for size in [2147483647, -2147483648]:
    print(size, repr(TextWrapper(tabsize=size)._munge_whitespace("hello")))
