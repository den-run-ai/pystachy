# The ported timedelta keeps concrete storage for a reflected numeric operation.
from datetime import timedelta

print(2 * timedelta(days=1))
