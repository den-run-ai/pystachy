# A module global that only None is ever assigned to reads as None.
hook = None


def run() -> str:
    if hook is None:
        return "no hook"
    return "hook"


print(run(), hook)
