events: list[str] = []


class Probe:
    def __getitem__(self, key: slice) -> list[int]:
        events.append('get')
        print(key.start, key.stop, key.step)
        return [1]

    def __setitem__(self, key: slice, value: list[int]) -> None:
        events.append('set')
        print(key.start, key.stop, key.step, value)

    def __delitem__(self, key: slice) -> None:
        events.append('del')
        print(key.start, key.stop, key.step)


def receiver() -> Probe:
    events.append('receiver')
    return Probe()


def bound(label: str, value: int) -> int:
    events.append(label)
    return value


def value() -> list[int]:
    events.append('value')
    return [7, 8]


def key() -> slice:
    events.append('key')
    return slice(1, 3)


print(receiver()[bound('start', 1):bound('stop', 3):bound('step', 0)])
print(events)
events.clear()
receiver()[bound('start', 1):bound('stop', 3)] = value()
print(events)
events.clear()
receiver()[bound('start', 1):bound('stop', 3)] += value()
print(events)
events.clear()
del receiver()[bound('start', 1):bound('stop', 3)]
print(events)
events.clear()
xs = [1, 2, 3, 4]
xs[key()] = value()
print(xs, events)
events.clear()
xs[key()] += value()
print(xs, events)
events.clear()
del xs[key()]
print(xs, events)
