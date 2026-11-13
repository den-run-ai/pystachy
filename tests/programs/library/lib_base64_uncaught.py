# An error that base64 raises and the program does not catch
import base64

print(base64.b64decode(b"aGk="))
print(base64.b32decode(b"NBUQ==="))
