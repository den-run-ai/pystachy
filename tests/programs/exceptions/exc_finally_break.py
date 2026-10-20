# A break out of a while True loop runs the finally blocks it leaves first: what they delete is
# unbound after the loop, though the try body assigned it before the break.
def f() -> None:
    while True:
        try:
            y = 1
            break
        finally:
            del y
    print(y)


try:
    f()
except UnboundLocalError as e:
    print("unbound:", e)
while True:
    try:
        int("q")
    except ValueError:
        z = 2
        break
    finally:
        del z
try:
    print(z)
except NameError as e:
    print("unbound:", e)
w = 0
while True:
    try:
        w = 5
        break
    finally:
        pass
print(w)
while True:
    try:
        try:
            v = 1
            break
        finally:
            print("inner")
    finally:
        del v
try:
    print(v)
except NameError as e:
    print("unbound:", e)
while True:
    try:
        x = 1
        break
    finally:
        del x
print(x)
