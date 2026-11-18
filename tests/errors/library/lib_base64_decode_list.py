# error: unsupported call memoryview(list[int])
import base64

print(base64.b85decode([97, 98]))
