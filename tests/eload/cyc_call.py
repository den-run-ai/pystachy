def later() -> str:
    import eload.cyc_user
    return eload.cyc_user.NAME


print(later())
raise ImportError("cyc_call unavailable")
