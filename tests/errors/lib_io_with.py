# error: lib_io_with.py:5: error: 'with' is supported for files only (with open(...) as f:), not io.StringIO
# lib/io's StringIO in a with statement (lib/README.md): Pystachy's with takes files only
import io

with io.StringIO("text") as f:
    print(f.read())
