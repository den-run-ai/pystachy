/* Scalar ABI of raylib_adapter.c, reused unchanged by both implementations. */
#ifndef MINIUI_BENCH_ABI_H
#define MINIUI_BENCH_ABI_H
int miniui_init(int width, int height, const char *title);
void miniui_close(void);
int miniui_open(void);
int miniui_focused(void);
int miniui_mouse_x(void);
int miniui_mouse_y(void);
int miniui_mouse(void);
int miniui_keys(void);
int miniui_character(void);
double miniui_dt(void);
void miniui_begin(unsigned int color);
void miniui_end(void);
void miniui_clip(int x, int y, int w, int h);
void miniui_rect(int x, int y, int w, int h, unsigned int color);
void miniui_text(const char *text, int x, int y, int size, unsigned int color);
int miniui_width(const char *text, int size);
#endif
