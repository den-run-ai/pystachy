# Presence of an optional value is separate from initialization of its local.
def annotated(initialize: bool, take: bool, x: int) -> int:
    value: int | None
    if initialize:
        value = x if take else None
    return 17 if value is None else value


def inferred(initialize: bool, take: bool, x: int) -> int:
    if initialize:
        value = None
        if take:
            value = x
    return 17 if value is None else value


for initialize in [False, True]:
    for take in [False, True]:
        try:
            print("annotated", initialize, take, annotated(initialize, take, 0))
        except UnboundLocalError as error:
            print("annotated", initialize, take, str(error))
        try:
            print("inferred", initialize, take, inferred(initialize, take, 0))
        except UnboundLocalError as error:
            print("inferred", initialize, take, str(error))
