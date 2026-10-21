# error: lib_binascii_str_data.py:4: error: expected bytes, got str
# binascii's b2a_*() and the other functions taking binary data take bytes, which no str is
import binascii
print(binascii.hexlify("abc"))
