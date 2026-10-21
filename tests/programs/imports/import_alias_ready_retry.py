for attempt in range(2):
    try:
        import mods.alias_ready_retry
    except ValueError as e:
        print("ValueError", e)
print(mods.alias_ready_retry.call())
