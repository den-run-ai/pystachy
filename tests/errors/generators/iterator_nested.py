# error: zip() cannot be nested in enumerate() here
for k, ab in enumerate(zip([1, 2], [3, 4])):
    print(k, ab)
