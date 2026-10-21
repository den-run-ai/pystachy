import mods.alias_ready_capture_source as source


def args() -> tuple[int]:
    try:
        import mods.alias_ready_capture_source
    except ValueError as e:
        print("retry", e)
    return (6,)


def use() -> int:
    # Retain the callable before args retries the failed source module's initialization.
    return source.Alias(*args())
