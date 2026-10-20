# error: a slice as a dict key is not supported
d = {1: 2}
d[0:1] = [3]
