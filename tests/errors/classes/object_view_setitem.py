# error: 'Mapping[object, object]' object does not support item assignment (Mapping[object, object] is a read-only view of a dict that a value of object holds
# a view of the dict that a value of object holds stores no value: its key and value types are not
# known
def main() -> None:
    x: object = {"a": 1}
    if isinstance(x, dict):
        x["b"] = 2
    print(x)


main()
