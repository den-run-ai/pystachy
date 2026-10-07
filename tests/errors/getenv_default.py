# error: os.getenv(name) needs a default here, os.getenv(name, default): the result would be str or None
import os
print(os.getenv("HOME"))
