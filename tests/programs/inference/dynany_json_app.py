# pystachy: dynamic-any
# A JSON-processing application (#777, #779): json.loads() decodes events into Any's containers,
# which typed functions (dict[str, Any], list[dict[str, Any]]) and dynamic ones (Any) then share
# as the same objects: an index's lists hold the records themselves, a change made through any of
# them shows in all, and json.dumps() writes the document they changed, with no copy between.
import json
from typing import Any

TEXT = """
[
  {"id": 1, "user": "ann", "kind": "login", "tags": ["web"], "meta": {"ms": 120}},
  {"id": 2, "user": "bob", "kind": "buy", "tags": [], "meta": {"ms": 340, "items": [3, 4]}},
  {"id": 3, "user": "ann", "kind": "buy", "tags": ["mobile", "promo"], "meta": {"ms": 95.5}},
  {"id": 4, "user": "cy", "kind": "logout", "tags": ["web"], "meta": null},
  {"id": 5, "user": "bob", "kind": "buy", "tags": ["promo"], "meta": {"ms": 210, "items": [7]}}
]
"""


def normalize(rec: dict[str, Any]) -> None:
    # typed code that changes the record in place
    rec["user"] = rec["user"].upper()
    if rec["meta"] is None:
        rec["meta"] = {}
    rec["meta"]["seen"] = True


def index_by(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    # typed code whose lists hold the records themselves
    out: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        out.setdefault(r[key], []).append(r)
    return out


def total_ms(doc: Any) -> float:
    # dynamic code over the same objects
    t = 0.0
    for r in doc:
        m = r["meta"]
        if "ms" in m:
            t += m["ms"]
    return t


def tag(records: Any, name: str) -> int:
    # dynamic code that changes lists the typed index also holds
    n = 0
    for r in records:
        if name not in r["tags"]:
            r["tags"].append(name)
            n += 1
    return n


def promo_users(by_user: dict[str, list[dict[str, Any]]]) -> list[Any]:
    return sorted(u for u, rs in by_user.items() if any("promo" in r["tags"] for r in rs))


def main() -> None:
    events: list[dict[str, Any]] = json.loads(TEXT)
    for e in events:
        normalize(e)
    by_user = index_by(events, "user")
    by_kind = index_by(events, "kind")
    print("users", sorted(by_user), "kinds", sorted(by_kind))
    print("the index holds the records", by_user["ANN"][0] is events[0], by_kind["buy"][1] is events[2])
    print("buys tagged", tag(by_kind["buy"], "paid"), "again", tag(events[1:2], "paid"))
    print("seen through the list", events[1]["tags"], events[4]["tags"])
    print("promo users", promo_users(by_user))
    print("total ms", total_ms(events), "of buys", total_ms(by_kind["buy"]))
    doc: Any = events
    doc[3]["meta"]["note"] = "closed"
    by_user["CY"][0]["meta"]["by"] = ("admin", 7)
    print("one record", json.dumps(events[3], sort_keys=True))
    summary: dict[str, Any] = {"count": len(events), "users": promo_users(by_user), "ms": total_ms(doc)}
    summary["first"] = events[0]
    print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
    again: Any = json.loads(json.dumps(events))
    print("round trip equal", again == events, "distinct", again is not events)
    print(json.dumps(by_kind["login"], ensure_ascii=False))


main()
