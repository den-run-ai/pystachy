# int()'s invalid-literal message shows at most 200 characters of the string's repr (%.200R);
# float()'s shows all of it
print(len(str(float("1" * 250))) > 0)
print(int("\u00e9" * 150 + "x" * 150))
