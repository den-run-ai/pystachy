# runtime errors abort with exit code 1, after everything printed so far is flushed
xs = [1, 2, 3]
d = {"a": 1}
print("before", xs[-1], d["a"])
total = 0
for i in range(5):
    total += xs[i]
    print("partial", total)
print("never reached")
