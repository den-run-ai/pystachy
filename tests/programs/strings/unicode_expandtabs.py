# str.expandtabs() counts a character as one column, whatever its bytes, and starts a line
# again after "\n" and "\r" only, as CPython's does
def show(s: str) -> None:
    for size in [8, 4, 1, 0, -2, 3]:
        print(ascii(s.expandtabs(size)))
    print(ascii(s.expandtabs()), len(s.expandtabs()))


for s in [
    "\u00e9\tb", "\u0436\u0436\t|", "\u5929\t\u5730\t|", "\U0001f600\tx\t|",
    "e\u0301\tb", "a\u200b\tb", "\u00e9\u00e9\u00e9\u00e9\u00e9\u00e9\u00e9\t|", "\u00e9\u00e9\u00e9\u00e9\u00e9\u00e9\u00e9\u00e9\t|",
    "\u00e9\n\u00e9\t|", "\u00e9\r\u00e9\u00e9\t|", "\u00e9\u2028\u00e9\t|", "\u00e9\x0b\u00e9\t|",
    "\u00e9\x85\u00e9\t|", "\t\u00e9\t\t\u0436\t", "\u5929" * 20 + "\t" + "\u0436" * 9 + "\t|",
    "\u00e9\t" * 12, "\U0001f600\U0001f600\t\u5929\n\t\u00e9\t|", "",
]:
    show(s)
f = "\u00e9\tb".expandtabs
print(ascii(f()), ascii(f(2)))
