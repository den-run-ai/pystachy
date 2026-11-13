# error: emods/sentinel_store.py:4: error: expected int, got object
# CPython prints False: f's default keeps the first object(), which S no longer names
import emods.sentinel_store

emods.sentinel_store.S = object()
print(emods.sentinel_store.f())
