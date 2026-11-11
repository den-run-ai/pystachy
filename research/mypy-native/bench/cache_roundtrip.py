# Upstream mypy 2.4.1's mypy.cache, unmodified: its typed cache helpers over librt.internal,
# written and read back (CPython: the mypyc-compiled wheel and librt's extension).
from librt.internal import ReadBuffer, WriteBuffer
from mypy.cache import (read_bytes_list, read_errors, read_flags, read_int, read_int_list, read_int_opt,
                        read_str, read_str_list, read_str_opt, read_str_opt_list, write_bytes_list,
                        write_errors, write_flags, write_int, write_int_list, write_int_opt, write_str,
                        write_str_list, write_str_opt, write_str_opt_list)

w = WriteBuffer()
write_int(w, 123456789)
write_str(w, "builtins.object")
write_int_opt(w, None)
write_int_opt(w, -42)
write_str_opt(w, "m.f")
write_int_list(w, [0, 1, 200, -100000, 2**40])
write_str_list(w, ["a", "bc", "def"])
write_bytes_list(w, [b"\x00", b"xyz"])
write_str_opt_list(w, ["x", None, "z"])
write_flags(w, [True, False, True, True])
write_errors(w, [("m.py", 3, 4, 3, 9, "error", "Name \"x\" is not defined", "name-defined"),
                 (None, -1, -1, -1, -1, "note", "see above", None)])
data = w.getvalue()
print(len(data), data[:48].hex())
r = ReadBuffer(data)
print(read_int(r), read_str(r), read_int_opt(r), read_int_opt(r), read_str_opt(r))
print(read_int_list(r), read_str_list(r), read_bytes_list(r), read_str_opt_list(r), read_flags(r, 4))
print(read_errors(r))
