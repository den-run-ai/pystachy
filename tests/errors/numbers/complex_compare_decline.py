# error: complex.__eq__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
print(complex(1, 0).__eq__(None))
