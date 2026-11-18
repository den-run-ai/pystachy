# string.capwords() capitalizes each word as str.capitalize() does: its first character by
# its titlecase mapping and the rest by their lower ones, whatever their script (#120).
from string import capwords

for s in ["\xe9lan vital", "ÉLAN VITAL", "straße ÉCOLE", "ǆungla ΟΔΟΣ", "ﬁn de siècle", "мир труд май", "a\tb  c"]:
    print(repr(capwords(s)), repr(capwords(s, " ")))
