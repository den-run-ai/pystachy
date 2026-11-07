# Scalar C API. The GIL remains held, matching this main-thread UI design.
# Python exports below reject non-integers and perform checked conversion.
# Compiled callers use the typed C helpers directly.
cdef extern from "miniui_abi.h":
    int c_init "miniui_init"(int width, int height, const char *title)
    void c_close "miniui_close"()
    int c_open "miniui_open"()
    int c_focused "miniui_focused"()
    int c_mouse_x "miniui_mouse_x"()
    int c_mouse_y "miniui_mouse_y"()
    int c_mouse "miniui_mouse"()
    int c_keys "miniui_keys"()
    int c_character "miniui_character"()
    double c_dt "miniui_dt"()
    void c_begin "miniui_begin"(unsigned int color)
    void c_end "miniui_end"()
    void c_clip "miniui_clip"(int x, int y, int w, int h)
    void c_rect "miniui_rect"(int x, int y, int w, int h, unsigned int color)
    void c_text "miniui_text"(const char *text, int x, int y, int size, unsigned int color)
    int c_width "miniui_width"(const char *text, int size)

cdef inline bytes checked_utf8(str text):
    if "\0" in text:
        raise ValueError("embedded null character")
    return text.encode("utf-8", "surrogatepass")

cdef int _init(int width, int height, str title):
    cdef bytes encoded = checked_utf8(title)
    return c_init(width, height, encoded)

cdef void _close():
    c_close()

cdef int _open():
    return c_open()

cdef int _focused():
    return c_focused()

cdef int _mouse_x():
    return c_mouse_x()

cdef int _mouse_y():
    return c_mouse_y()

cdef int _mouse():
    return c_mouse()

cdef int _keys():
    return c_keys()

cdef int _character():
    return c_character()

cdef double _dt():
    return c_dt()

cdef void _begin(unsigned int color):
    c_begin(color)

cdef void _end():
    c_end()

cdef void _clip(int x, int y, int w, int h):
    c_clip(x, y, w, h)

cdef void _rect(int x, int y, int w, int h, unsigned int color):
    c_rect(x, y, w, h, color)

cdef void _text(str text, int x, int y, int size, unsigned int color):
    cdef bytes encoded = checked_utf8(text)
    c_text(encoded, x, y, size, color)

cdef int _width(str text, int size):
    cdef bytes encoded = checked_utf8(text)
    return c_width(encoded, size)


# A conventional CPython extension must reject values that the FFI twin rejects,
# including floats passed as integers. Cython's automatic int argument converter
# alone truncates floats, so these small C-level checks are intentional.
cdef inline int checked_int(object value):
    if not isinstance(value, int):
        raise TypeError("expected int for C int")
    return value

cdef inline unsigned int checked_uint(object value):
    if not isinstance(value, int):
        raise TypeError("expected int for C unsigned int")
    return value

def py_init(width, height, str title):
    return _init(checked_int(width), checked_int(height), title)

def py_close():
    _close()

def py_open():
    return _open()

def py_focused():
    return _focused()

def py_mouse_x():
    return _mouse_x()

def py_mouse_y():
    return _mouse_y()

def py_mouse():
    return _mouse()

def py_keys():
    return _keys()

def py_character():
    return _character()

def py_dt():
    return _dt()

def py_begin(color):
    _begin(checked_uint(color))

def py_end():
    _end()

def py_clip(x, y, w, h):
    _clip(checked_int(x), checked_int(y), checked_int(w), checked_int(h))

def py_rect(x, y, w, h, color):
    _rect(checked_int(x), checked_int(y), checked_int(w), checked_int(h), checked_uint(color))

def py_text(str text, x, y, size, color):
    _text(text, checked_int(x), checked_int(y), checked_int(size), checked_uint(color))

def py_width(str text, size):
    return _width(text, checked_int(size))

# The C helpers retain the names compiled Window methods use. This public module
# table supplies Python callers with equivalent error-checking extension methods.
globals().update({
    "_init": py_init, "_close": py_close, "_open": py_open,
    "_focused": py_focused, "_mouse_x": py_mouse_x, "_mouse_y": py_mouse_y,
    "_mouse": py_mouse, "_keys": py_keys, "_character": py_character,
    "_dt": py_dt, "_begin": py_begin, "_end": py_end, "_clip": py_clip,
    "_rect": py_rect, "_text": py_text, "_width": py_width,
})
