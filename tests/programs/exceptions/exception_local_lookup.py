# Locally caught container reads keep their values, exception objects and cleanup
# when the miss branches directly to a handler instead of using the unwinder.


def dict_values() -> None:
    numbers = {0: 0, 1: -1, 2: -9223372036854775808}
    for integer_key in [-1, 0, 1, 2, 3]:
        try:
            print("integer", integer_key, numbers[integer_key])
        except KeyError as error:
            print("integer miss", str(error), repr(error))
    floats = {"zero": 0.0, "value": 2.5}
    for float_key in ["zero", "value", "missing", "雪'\n"]:
        try:
            print("float", floats[float_key])
        except LookupError as error:
            print("float miss", repr(error))
    refs: dict[str, list[int] | None] = {"none": None, "empty": [], "value": [7]}
    for reference_key in ["none", "empty", "value", "missing"]:
        try:
            print("reference", reference_key, refs[reference_key])
        except KeyError as error:
            print("reference miss", repr(error))
    flags = {0: False, 1: True}
    for flag_key in [0, 1]:
        try:
            print("boolean", flags[flag_key])
        except KeyError:
            print("unexpected boolean miss")


def list_values() -> None:
    integers = [0, -1, -9223372036854775808]
    floats = [0.0, 2.5, -3.0]
    refs = [["first"], [], ["last"]]
    for index in [-9223372036854775808, -4, -3, -1, 0, 2, 3, 9223372036854775807]:
        try:
            print("list integer", index, integers[index])
        except IndexError as error:
            print("list integer miss", index, repr(error))
        try:
            print("list float", index, floats[index])
        except LookupError as error:
            print("list float miss", index, repr(error))
        try:
            print("list reference", index, refs[index])
        except (KeyError, IndexError) as error:
            print("list reference miss", index, repr(error))
    empty: list[int] = []
    try:
        print(empty[-1])
    except:
        print("empty bare handler")


def cleanup(table: dict[int, int], key: int) -> int:
    try:
        try:
            value = table[key]
        except IndexError:
            print("unexpected handler")
            return -1
        else:
            print("else", value)
            return value
        finally:
            print("inner finally", key)
    except LookupError as error:
        print("outer handler", repr(error))
        saved = error
        try:
            raise
        except KeyError as again:
            print("same reraised object", again is saved, repr(again))
        return -2
    finally:
        print("outer finally", key)


def restore_active_exception(items: list[int]) -> None:
    original = ValueError("active")
    try:
        raise original
    except ValueError:
        try:
            print(items[10])
        except IndexError as missing:
            print("nested", repr(missing))
        try:
            raise
        except ValueError as restored:
            print("restored active object", restored is original)


def cause_and_lifetime(table: dict[str, int]) -> None:
    try:
        print(table["gone"])
    except KeyError as missing:
        # Allocate after retaining the exception; GC stress must retain it too.
        values = [str(index) for index in range(32)]
        try:
            raise ValueError(values[-1]) from missing
        except ValueError as replacement:
            print("cause", replacement.__cause__ is missing, repr(replacement.__cause__))


events: list[str] = []
table: dict["Key", int] = {}
hash_action: list[int] = [0]
eq_action: list[int] = [0]
failure = ValueError("callback")


class Key:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        events.append("hash " + str(self.value))
        action = hash_action[0]
        hash_action[0] = 0
        if action == 1:
            raise failure
        if action == 2:
            table.clear()
            table[self] = 91
        return 7

    def __eq__(self, other: "Key") -> bool:
        events.append("eq " + str(self.value) + " " + str(other.value))
        action = eq_action[0]
        eq_action[0] = 0
        if action == 1:
            raise failure
        if action == 2:
            table.clear()
        if action == 3:
            table[self] = 92
        return self.value == other.value

    def __repr__(self) -> str:
        return "Key(" + str(self.value) + ")"


def callback_read(query: Key) -> None:
    try:
        print("callback value", table[query])
    except KeyError as error:
        print("callback miss", repr(error))
    except ValueError as error:
        print("callback raised", error is failure, repr(error))
    finally:
        print("callback finally", len(table))


def callbacks() -> None:
    for action in [0, 1, 2]:
        table.clear()
        table[Key(1)] = 10
        events.clear()
        hash_action[0] = action
        callback_read(Key(1))
        print("hash events", action, events)
    for action in [0, 1, 2, 3]:
        table.clear()
        table[Key(1)] = 10
        events.clear()
        eq_action[0] = action
        callback_read(Key(1))
        print("equality events", action, events)
    events.clear()
    callback_read(Key(2))
    print("missing events", events)


dict_values()
list_values()
print("cleanup result", cleanup({1: 17}, 1))
print("cleanup result", cleanup({1: 17}, 2))
restore_active_exception([1])
cause_and_lifetime({})
callbacks()
