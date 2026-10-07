print(divmod(17, 5), divmod(-17, 5), divmod(17, -5), divmod(7.5, 2.0), divmod(-7.5, 2), divmod(7, 2.5), divmod(True, 3))
print(pow(2, 10), pow(2.0, 0.5), pow(3, 4, 5), pow(-3, 3, 7), pow(3, 3, -7), pow(10, 0, 1), pow(123456789, 987654321, 1000000007), pow(2, 3, 1))
for i, w in enumerate(["a", "b"], 1):
    print(i, w)
for i, w in enumerate("xyz", start=10):
    print(i, w)
