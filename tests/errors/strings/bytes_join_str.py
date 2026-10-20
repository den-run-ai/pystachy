# error: sequence item 0: expected a bytes-like object, str found
xs = ["a", "b"]
print(b"-".join(xs))
