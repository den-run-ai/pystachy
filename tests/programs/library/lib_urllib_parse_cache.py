# CPython urlsplit's typed LRU contract with string arguments.
from urllib.parse import clear_cache, quote, urlparse, urlsplit

clear_cache()
assert urlsplit.cache_info() == (0, 0, 128, 0)
url = "https://caf\u00e9.example/\u4e2d?q=1#frag"
assert urlsplit(url).netloc == "caf\u00e9.example"
assert urlsplit(url).fragment == "frag"
assert urlsplit(url, allow_fragments=False).path == "/\u4e2d"
assert urlsplit(url, allow_fragments=False).query == "q=1#frag"
assert urlsplit(url, "", True).fragment == "frag"
assert urlsplit.cache_info() == (2, 3, 128, 3)
assert urlsplit.__wrapped__(url, "", True).path == "/\u4e2d"
assert urlsplit.cache_info() == (2, 3, 128, 3)

# urlparse uses the cached full-positional call and retains parameter splitting.
assert urlparse(url).fragment == "frag"
assert urlsplit.cache_info() == (3, 3, 128, 3)
assert urlparse("http://h/p;x?q#f").params == "x"
assert quote("caf\u00e9 /\u4e2d", safe="/") == "caf%C3%A9%20/%E4%B8%AD"

clear_cache()
for i in range(2):
    try:
        urlsplit("http://[broken/")
        assert False
    except ValueError:
        pass
assert urlsplit.cache_info() == (0, 2, 128, 0)

# Capacity and least-recently-used eviction retain the upstream 128-entry bound.
for i in range(129):
    urlsplit("https://example.com/" + str(i))
assert urlsplit.cache_info() == (0, 131, 128, 128)
urlsplit("https://example.com/0")
assert urlsplit.cache_info() == (0, 132, 128, 128)
urlsplit("https://example.com/0")
assert urlsplit.cache_info() == (1, 132, 128, 128)
clear_cache()
assert urlsplit.cache_info() == (0, 0, 128, 0)
assert quote("caf\u00e9 /\u4e2d", safe="/") == "caf%C3%A9%20/%E4%B8%AD"
print("urllib.parse cache checks passed")
