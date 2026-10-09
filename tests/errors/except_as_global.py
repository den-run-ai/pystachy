# error: except ... as err, of the global 'err', in a function is not supported: the end of the clause deletes the global, as del would
err = ValueError("initial")


def f() -> None:
    global err
    try:
        raise KeyError("k")
    except KeyError as err:
        pass


f()
print(err)
