# a width the allocator cannot serve is MemoryError, also within 9 bytes of 2**63
print(len("ab".ljust(5)))
print(len("".ljust(9223372036854775807)))
