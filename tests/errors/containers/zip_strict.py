# error: zip(strict=...) is not supported
xs = [1]
for a, b in zip(xs, xs, strict=True):
    print(a)
