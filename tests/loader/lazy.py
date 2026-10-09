def load() -> str:
    try:
        import loader.winonly
    except ImportError:
        return "fallback"
    return "ok"
