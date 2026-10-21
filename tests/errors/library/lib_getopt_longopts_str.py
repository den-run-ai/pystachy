# error: lib_getopt_longopts_str.py:4: error: expected list[str], got str
# lib/getopt's longopts is annotated list[str] (lib/README.md); CPython also takes a single str
import getopt
print(getopt.getopt(["--alpha"], "", "alpha"))
