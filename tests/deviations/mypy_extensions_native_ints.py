# Documented deviation (docs/language/compatibility.md#modules-and-libraries): lib/mypy_extensions.py's
# native integer names are int itself, where the mypy_extensions package's are classes of their
# own whose calls return an int: i64 is int, and its __name__ is 'int'.
from mypy_extensions import i64, u8

print(i64 is int, u8.__name__, type(i64(3)).__name__)
