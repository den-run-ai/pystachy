# A write statement drops what f.write() returns, but a write within its argument, through a
# method value, returns the number of characters it writes (#120)
import sys
import tempfile

w = sys.stdout.write
sys.stdout.write(str(w("é\n")) + "\n")
d = tempfile.mkdtemp()
f = open(d + "/t.txt", "w", encoding="utf-8")
fw = f.write
f.write(str(fw("日本語")))
f.close()
print(open(d + "/t.txt", encoding="utf-8").read())
