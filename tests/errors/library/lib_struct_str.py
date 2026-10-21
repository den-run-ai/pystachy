# error: lib_struct_str.py:3: error: argument for 's' must be a bytes object
import struct
print(struct.pack("<3s", "abc"))
