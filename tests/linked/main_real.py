# Run as tests/symlink_main.py, a symbolic link to this file: the modules are found next to this
# file, as CPython finds them in the directory of the script's real path (issue #14).
import linked_mod
print(linked_mod.W)
