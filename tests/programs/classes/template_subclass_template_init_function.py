# A subclass of a class template whose own __init__ is a class template, given a module's function
# (threading's Timer, #962): the function's type, which the declarations know, picks its
# specialization, made before any code is compiled as the others are.
class Action:
    def __init__(self, action):
        self.action = action

    def fire(self):
        return self.action()


class Timer(Action):
    def __init__(self, interval, action):
        super().__init__(action)
        self.interval = interval


def ring():
    return "ring"


def beep():
    return "beep"


t = Timer(0.5, ring)
u = Timer(2, beep)
print(t.interval, t.fire(), u.interval, u.fire())
for x in [Action(ring), t]:
    print(x.fire(), isinstance(x, Timer))
