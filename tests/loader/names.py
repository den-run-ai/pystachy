def f(__name__: str) -> str:
    # a parameter that hides the module's __name__
    if __name__ == "__main__":
        return "main"
    return "other"


if __name__ == "__main__":
    print("dropped")
