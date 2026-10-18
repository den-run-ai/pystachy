# error: select.select() expects three list[int] arguments and an optional positional timeout
import select
select.select([], [], [], timeout=0)
