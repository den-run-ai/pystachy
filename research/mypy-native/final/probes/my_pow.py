from typing import Final
class IPC:
    BUFFER_SIZE: Final = 2**16
print(IPC.BUFFER_SIZE, IPC().BUFFER_SIZE)
