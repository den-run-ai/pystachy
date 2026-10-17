import os, subprocess, sys

for code in ["import wr; wr.save('wr_a.txt', 'saved\\n')", "import wr; wr.log('wr_b.txt', 'one\\n'); wr.log('wr_b.txt', 'two\\n')"]:
    subprocess.run([sys.executable, "-W", "ignore", "-c", code], check=True)  # (-W ignore: the GIL warning of 3.15t)
for f in ["wr_a.txt", "wr_b.txt"]:
    print(f, repr(open(f).read()))
    os.remove(f)
