# error: inspection of typing final/override marker attributes is not supported
from typing import final


@final
class Box:
    pass


print(hasattr(Box(), "__final__"))
