print("backfail start")


def later() -> str:
    import loader.backuser
    return loader.backuser.NAME


raise ImportError("backfail unavailable")
