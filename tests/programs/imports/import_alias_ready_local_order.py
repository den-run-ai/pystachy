try:
    import mods.alias_ready_local_failure
except ValueError:
    pass
import mods.alias_chain


def failed_first() -> None:
    try:
        from mods.alias_ready_local_failure import Alias as chosen
    except ValueError:
        pass
    try:
        print("early", chosen(1))
    except UnboundLocalError as e:
        print("UnboundLocalError", e)
    from mods.alias_base import inc as chosen
    print("later", chosen(2))


def bound_first() -> None:
    from mods.alias_base import inc as chosen
    try:
        from mods.alias_ready_local_failure import Alias as chosen
    except ValueError:
        pass
    print("retained", chosen(3))


def closure_after_imports() -> int:
    from mods.alias_chain import again as chosen
    try:
        from mods.alias_mid import plus_one as chosen
    except ValueError:
        pass

    def closure() -> int:
        return chosen(4)

    return closure()


failed_first()
failed_first()
bound_first()
print("closure", closure_after_imports())
