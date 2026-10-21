try:
    import mods.alias_ready_capture_source
except ValueError as e:
    print("initial", e)
import mods.alias_ready_capture_user

print(mods.alias_ready_capture_user.use())
