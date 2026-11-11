def f(x:tuple[int,int])->str:
    match x:
        case (): return 'none'
        case _: return 'some'
print(f((1,2)))
