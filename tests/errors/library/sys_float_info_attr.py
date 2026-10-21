# error: unsupported module attribute sys.float_info.n_fields
# the named attributes only: not those of the struct sequence (n_fields, index(), ...)
import sys

print(sys.float_info.n_fields)
