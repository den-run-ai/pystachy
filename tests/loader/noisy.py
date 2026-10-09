def msg() -> str:
    print("msg built")
    return "noisy fails"


raise ImportError(msg())
