# CPython's own Lib/this.py (lib/this.py, unmodified): importing it prints the Zen of Python,
# decoded with a dict whose types come from its first use
import this
print(len(this.s), this.d["n"], this.c, this.i)
