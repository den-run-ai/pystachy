# examples/suggest: corrections for the misspelled words of a generated text, from a generated
# vocabulary, through difflib.get_close_matches(), as CPython finds them; then its errors
import os
import tempfile

import genvocab
import suggest

print(suggest.words("Hello, (world)!  It's  a test-case."), suggest.words(""), suggest.words("--- 42"))
vocab = genvocab.vocabulary(3000)
lines = genvocab.text(vocab, 30)
print(len(vocab), vocab[:5], lines[0])
for line in suggest.check(lines, vocab, 3, 0.75):
    print(line)
print(suggest.check(["kato rimen, sadar", "katto rimn sadra"], ["kato", "rimen", "sadar", "katos", "rimes"], 2, 0.6))
print(suggest.check(["zzzzzz"], vocab, 3, 0.75))
try:
    suggest.check(["kato"], ["kata"], 0, 0.5)
except ValueError as e:
    print("ValueError:", e)

d = tempfile.mkdtemp()
paths = [os.path.join(d, "vocab.txt"), os.path.join(d, "text.txt")]
with open(paths[0], "w") as f:
    for w in vocab:
        f.write(w + "\n")
with open(paths[1], "w") as f:
    for line in lines[:10]:
        f.write(line + "\n")
print(suggest.main(paths), suggest.main(["-n", "1", "-c", "0.9"] + paths), suggest.main([paths[0], paths[0]]))
print(suggest.main(["-c", "2"] + paths), suggest.main([]))
print(suggest.main(["-n", "many"] + paths), suggest.main(["-c", "nope"] + paths), suggest.main(["-n", "0"] + paths))
for path in paths:
    os.remove(path)
os.rmdir(d)
