# error: a85encode() takes 1 positional argument but 2 were given
import base64

print(base64.a85encode(b"x", True))
