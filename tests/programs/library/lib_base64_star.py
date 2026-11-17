# from base64 import *: the names of __all__
from base64 import *

print(b64encode(b"hi"), b64decode(b"aGk="), standard_b64encode(b"hi"), standard_b64decode("aGk="))
print(urlsafe_b64encode(b"\xfb\xff"), urlsafe_b64decode(b"-_8="))
print(b32encode(b"hi"), b32decode(b"NBUQ===="), b32hexencode(b"hi"), b32hexdecode(b"D1KG===="))
print(b16encode(b"hi"), b16decode(b"6869"))
print(a85encode(b"hi"), a85decode(b"BOq"), b85encode(b"hi"), b85decode(b"Xk~"), z85encode(b"hi"), z85decode(b"xK#"))
print(encodebytes(b"hi"), decodebytes(b"aGk=\n"))
