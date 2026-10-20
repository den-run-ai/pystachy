# examples/latency: the report of 3,000 generated requests, which genlog makes and latency reads
# as the lines of a log, as CPython prints it; then a log with lines that are no request, an
# endpoint with one request, one with timeouts alone and one whose responses are empty
import genlog
import latency

lines = genlog.lines(3000)
print(lines[0])
print(lines[-1])
endpoints: dict[str, latency.Endpoint] = {}
skipped = latency.parse(lines, endpoints)
latency.report(endpoints, skipped)
print(genlog.timestamp(0), genlog.timestamp(3599999), genlog.timestamp(86399999 - 8 * 3600000))

odd = [
    "2026-10-13T08:00:00.001 GET /a 200 12.5 100",
    "2026-10-13T08:00:00.002 GET /a 200 7.25 300",
    "garbage",
    "",
    "2026-10-13T08:00:00.003 GET /a 200 x 300",
    "2026-10-13T08:00:00.004 GET /one 201 3.0 0",
    "2026-10-13T08:00:00.005 POST /slow 504 - 0",
    "2026-10-13T08:00:00.006 POST /slow 504 - 0",
    "2026-10-13T08:00:00.007 GET /a 503 0.5 120",
    "2026-10-13T08:00:00.008 GET /a 200 9.0 300 extra",
    "2026-10-13T08:00:00.009 GET /empty 204 2.5 0",
    "2026-10-13T08:00:00.010 GET /empty 204 3.5 0",
]
endpoints = {}
skipped = latency.parse(odd, endpoints)
latency.report(endpoints, skipped)
one: dict[str, latency.Endpoint] = {}
latency.report(one, latency.parse(odd[:1], one))
