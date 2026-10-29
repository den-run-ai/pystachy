# pystachy: dynamic-any
"""Observed-Any 32-key controls with the same inputs as json_decode.py.

These retained controls are not a replay of #969's unavailable historical input.
Every iteration observes a decoded field and length; the final full result is printed
for comparison with CPython. Constants are duplicated to avoid importing an executable
benchmark or changing either benchmark's compiler import graph.
"""
import json
import sys
import time
from typing import Any

NUMERIC = (
    '{"k0":1000'
    ',"k1":1001'
    ',"k2":1002'
    ',"k3":1003'
    ',"k4":1004'
    ',"k5":1005'
    ',"k6":1006'
    ',"k7":1007'
    ',"k8":1008'
    ',"k9":1009'
    ',"k10":1010'
    ',"k11":1011'
    ',"k12":1012'
    ',"k13":1013'
    ',"k14":1014'
    ',"k15":1015'
    ',"k16":1016'
    ',"k17":1017'
    ',"k18":1018'
    ',"k19":1019'
    ',"k20":1020'
    ',"k21":1021'
    ',"k22":1022'
    ',"k23":1023'
    ',"k24":1024'
    ',"k25":1025'
    ',"k26":1026'
    ',"k27":1027'
    ',"k28":1028'
    ',"k29":1029'
    ',"k30":1030'
    ',"k31":1031}'
)

STRINGS = (
    '{"k0":"value-00"'
    ',"k1":"value-01"'
    ',"k2":"value-02"'
    ',"k3":"value-03"'
    ',"k4":"value-04"'
    ',"k5":"value-05"'
    ',"k6":"value-06"'
    ',"k7":"value-07"'
    ',"k8":"value-08"'
    ',"k9":"value-09"'
    ',"k10":"value-10"'
    ',"k11":"value-11"'
    ',"k12":"value-12"'
    ',"k13":"value-13"'
    ',"k14":"value-14"'
    ',"k15":"value-15"'
    ',"k16":"value-16"'
    ',"k17":"value-17"'
    ',"k18":"value-18"'
    ',"k19":"value-19"'
    ',"k20":"value-20"'
    ',"k21":"value-21"'
    ',"k22":"value-22"'
    ',"k23":"value-23"'
    ',"k24":"value-24"'
    ',"k25":"value-25"'
    ',"k26":"value-26"'
    ',"k27":"value-27"'
    ',"k28":"value-28"'
    ',"k29":"value-29"'
    ',"k30":"value-30"'
    ',"k31":"value-31"}'
)

MIXED = (
    '{"k0":1000'
    ',"k1":1001.25'
    ',"k2":"value-02"'
    ',"k3":true'
    ',"k4":false'
    ',"k5":null'
    ',"k6":[1006,"value-06"]'
    ',"k7":{"inner":1007}'
    ',"k8":1000'
    ',"k9":1001.25'
    ',"k10":"value-02"'
    ',"k11":true'
    ',"k12":false'
    ',"k13":null'
    ',"k14":[1006,"value-06"]'
    ',"k15":{"inner":1007}'
    ',"k16":1000'
    ',"k17":1001.25'
    ',"k18":"value-02"'
    ',"k19":true'
    ',"k20":false'
    ',"k21":null'
    ',"k22":[1006,"value-06"]'
    ',"k23":{"inner":1007}'
    ',"k24":1000'
    ',"k25":1001.25'
    ',"k26":"value-02"'
    ',"k27":true'
    ',"k28":false'
    ',"k29":null'
    ',"k30":[1006,"value-06"]'
    ',"k31":{"inner":1007}}'
)

case = sys.argv[1] if len(sys.argv) > 1 else "numeric"
loops = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
if loops < 1:
    raise ValueError("loop count must be positive")
if case == "numeric":
    text = NUMERIC
    expected = 1063
elif case == "strings":
    text = STRINGS
    expected = 40
elif case == "mixed":
    text = MIXED
    expected = 1039
else:
    raise ValueError("case must be numeric, strings or mixed")

checksum = 0
started = time.perf_counter()
if case == "numeric":
    for _ in range(loops):
        value: Any = json.loads(text)
        checksum += len(value) + value["k31"]
elif case == "strings":
    for _ in range(loops):
        value: Any = json.loads(text)
        checksum += len(value) + len(value["k31"])
else:
    for _ in range(loops):
        value: Any = json.loads(text)
        checksum += len(value) + value["k31"]["inner"]
elapsed = time.perf_counter() - started
assert checksum == loops * expected
print("json_decode_any32", case, loops, checksum)
print(value)
print("seconds", elapsed, file=sys.stderr)
