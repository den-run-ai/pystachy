from mods import alias_ready_capture_state as state
from mods.alias_base import inc
import mods.alias_ready_capture_user

state.attempts += 1
if state.attempts > 1:
    raise ValueError("before alias")
Alias = inc
raise ValueError("after alias")
