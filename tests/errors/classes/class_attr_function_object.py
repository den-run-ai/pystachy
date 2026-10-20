# error: class attribute 'encode' of 'Codec' holds a function (encode = ...): reading it through an object is not supported (CPython binds the object to the function's first parameter, as for a method); read it through the class (Codec.encode), or define encode with def
def enc(s, errors="strict"):
    return (s, len(s))


class Codec:
    encode = enc


c = Codec()
print(c.encode("abc"))
