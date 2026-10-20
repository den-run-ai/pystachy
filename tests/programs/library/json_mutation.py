import json


def main() -> None:
    doc = json.loads('{"items":[1,true,null],"meta":{}}')
    if isinstance(doc, dict):
        items = doc["items"]
        if isinstance(items, list):
            items.append("added")
            items[0] = 2.5
            doc["alias"] = items
            alias = doc["alias"]
            if isinstance(alias, list):
                alias.append(False)
                print(alias is items, len(items))
            print(json.dumps(doc))
            items.append(items)
            try:
                json.dumps(doc)
            except ValueError as exc:
                print(str(exc))
            items.pop()
        meta = doc["meta"]
        if isinstance(meta, dict):
            meta["name"] = "record"
            meta["count"] = 7
            meta["count"] = None
            doc["self"] = doc
            try:
                json.dumps(doc)
            except ValueError as exc:
                print(str(exc))
            del doc["self"]
        print(json.dumps(doc, sort_keys=True, separators=(",", ":")))

    # Repeated aliases are not cycles: active ancestors, rather than every visited
    # container, determine whether serialization would recurse forever.
    other = json.loads('[{"x":1}, []]')
    if isinstance(other, list):
        shared = other[0]
        other.append(shared)
        print(json.dumps(other))
        if isinstance(shared, dict):
            shared["x"] = "changed"
        print(json.dumps(other))


main()
