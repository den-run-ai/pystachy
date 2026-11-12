# error: a class body may only contain fields, methods, a docstring, pass and ..., not a match statement
# (as for an if statement there: its subject and captures would otherwise become class attributes)
MODE = 1


class Settings:
    match MODE:
        case 1:
            level = "low"
        case _:
            level = "high"


print(Settings.level)
