# examples/mailmerge: generated records rendered in-process with string.Template's substitute() and
# safe_substitute(), and without it (--split), and the template's checks, as CPython renders them
from string import Template

import gendata
import mailmerge

with open("examples/mailmerge/notice.txt") as f:
    t = Template(f.read())
names = gendata.FIELDS
records = [mailmerge.parse(names, "\t".join(gendata.record(i)) + "\n", i + 2) for i in range(150)]
print(names, len(records), records[0])
print(repr(mailmerge.check(t, names, False)), t.get_identifiers())
texts, fields = mailmerge.split(t)
print(len(texts), fields)
total = 0
for i in range(len(records)):
    msg = mailmerge.render(t, records[i], i + 1, len(records), False)
    if msg != mailmerge.render_split(texts, fields, records[i], i + 1, len(records)):
        print("split differs:", i)
    if msg != mailmerge.render(t, records[i], i + 1, len(records), True):
        print("safe differs:", i)
    total += len(msg)
print(total)
print(mailmerge.render(t, records[149], 150, 150, False))

# what check() finds in a template: an invalid placeholder, with its line and column, or a field
# that the data does not have, which --safe leaves as it is
bad = Template("To: $name\nSubject: $plan at 5$ a month\n\n$$ ${seq}")
print(bad.is_valid(), repr(mailmerge.check(bad, names, False)), repr(mailmerge.check(bad, names, True)))
odd = Template("Dear $name, your ${nickname} is $$${amount} ($seq/$count)")
print(repr(mailmerge.check(odd, names, False)), repr(mailmerge.check(odd, names, True)))
print(mailmerge.render(odd, records[0], 1, 150, True))
try:
    mailmerge.render(odd, records[0], 1, 150, False)
except KeyError as e:
    print("KeyError", e)
print(mailmerge.split(odd))
try:
    mailmerge.parse(["a", "b"], "3\n", 3)
except ValueError as e:
    print("ValueError", e)
print(mailmerge.escape_from(mailmerge.render(Template("From $a\nFrom $b"), {"a": "x", "b": "y"}, 1, 1, False)))
print(repr(mailmerge.escape_from("From: me\nFrom you\n From x\nFromage")), repr(mailmerge.escape_from("")))
