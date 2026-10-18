from pyobj import import_module, of_str

json = import_module("json")
f = json.attr("dumps")
f.close()
f.close()  # (closing twice is allowed)
for k in range(3):
    try:
        if k == 0:
            print(f.call([of_str("x")]))
        elif k == 1:
            print(f.attr("x"))
        else:
            print(len(f))
    except ValueError as e:
        print("ValueError", e)
print("after")
