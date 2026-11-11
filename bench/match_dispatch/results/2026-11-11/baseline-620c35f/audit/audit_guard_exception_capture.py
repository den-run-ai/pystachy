def f()->None:
    n=100
    try:
        match 3:
            case n if 1//0:pass
    except ZeroDivisionError:
        print(n)
f()
