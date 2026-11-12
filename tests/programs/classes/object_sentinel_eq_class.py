events: list[bool] = []
sentinel = object()


class C:
    def __eq__(self, other):
        events.append(other is sentinel)
        return True


value = C()
print(sentinel == value, value == sentinel)
print(sentinel != value, value != sentinel)
print(events)
