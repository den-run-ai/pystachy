# error: f-string: reusing the string's quote inside a replacement field (PEP 701) is not supported; use the other quote
import sys
print(f"{sys.stdout.write("abc")}")
