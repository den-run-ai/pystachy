# error: expected bool, got int
# The cached string API requires a boolean allow_fragments argument.
from urllib.parse import urlsplit

print(urlsplit("http://example.com/#f", allow_fragments=0))
