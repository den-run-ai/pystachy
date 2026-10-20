# examples/urlstats: the requests of a generated access log counted by path, query parameter and
# canonical URL, as CPython counts them with its urllib.parse
import genlog
import urlstats

lines = [genlog.line(i) for i in range(400)]
print(lines[0])
stats = urlstats.Stats()
canon: list[str] = []
for line in lines + ["", "garbage", '1.2.3.4 - - [x] "GET /a b" 400 0']:
    target = urlstats.request_target(line)
    if target:
        canon.append(urlstats.add(stats, target))
    else:
        stats.skipped += 1
for row in urlstats.report(stats, 5):
    print(row)
print(len(canon), canon[:4])
for target in ["/search?b=2&a=caf%c3%a9", "/search?a=caf%C3%A9&b=2", "/search?a=caf%E9&b=2", "/x%20y/?q=a+b&q=%2B",
               "/?", "/p?a&b=&c=1", "http://example.com/p%2Fq?z=1&a=%zz", "/%E6%9D%B1?k=%F0%9F%8E%81"]:
    print(repr(target), repr(urlstats.add(stats, target)))
print(stats.requests, stats.skipped, stats.undecodable, sorted(stats.params), stats.values["a"])
print(genlog.encode("caf\xe9 cr\xe8me"), genlog.lower_hex("%C3%A9x%2F"), genlog.target(), genlog.rand(1000))
