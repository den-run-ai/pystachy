/* Optional scalar-only raylib backend. Original project code; no raygui source. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "raylib.h"

static int live;
static int clipping;
static char *window_title;

static Color color(unsigned int rgba) {
    Color result = {(unsigned char)(rgba >> 24), (unsigned char)(rgba >> 16),
                    (unsigned char)(rgba >> 8), (unsigned char)rgba};
    return result;
}

int miniui_init(int width, int height, const char *title) {
    if (live || width < 40 || height < 40 || width > 32768 || height > 32768 || !title)
        return 0;
    /* InitWindow may retain its title. Never retain the FFI's temporary string. */
    window_title = malloc(strlen(title) + 1);
    if (!window_title) return 0;
    strcpy(window_title, title);
    InitWindow(width, height, window_title);
    if (!IsWindowReady()) {
        free(window_title);
        window_title = NULL;
        return 0;
    }
    live = 1;
    SetExitKey(KEY_NULL);  /* Escape belongs to the UI; the titlebar closes. */
    SetTargetFPS(60);
    return 1;
}

void miniui_close(void) {
    if (!live) return;
    CloseWindow();
    live = 0;
    free(window_title);
    window_title = NULL;
}

int miniui_open(void) { return live && !WindowShouldClose(); }
int miniui_focused(void) { return live && IsWindowFocused(); }
int miniui_mouse_x(void) { return GetMouseX(); }
int miniui_mouse_y(void) { return GetMouseY(); }
int miniui_mouse(void) {
    return (IsMouseButtonDown(MOUSE_BUTTON_LEFT) ? 1 : 0)
         | (IsMouseButtonPressed(MOUSE_BUTTON_LEFT) ? 2 : 0)
         | (IsMouseButtonReleased(MOUSE_BUTTON_LEFT) ? 4 : 0);
}

static int edit_key(int key) { return IsKeyPressed(key) || IsKeyPressedRepeat(key); }
int miniui_keys(void) {
    return (edit_key(KEY_BACKSPACE) ? 1 : 0)
         | (edit_key(KEY_DELETE) ? 2 : 0)
         | (edit_key(KEY_LEFT) ? 4 : 0)
         | (edit_key(KEY_RIGHT) ? 8 : 0)
         | (edit_key(KEY_HOME) ? 16 : 0)
         | (edit_key(KEY_END) ? 32 : 0)
         | (IsKeyPressed(KEY_TAB) ? 64 : 0)
         | ((IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_RIGHT_SHIFT)) ? 128 : 0)
         | (IsKeyPressed(KEY_ENTER) ? 256 : 0)
         | (IsKeyPressed(KEY_SPACE) ? 512 : 0)
         | (IsKeyPressed(KEY_ESCAPE) ? 1024 : 0);
}

int miniui_character(void) { return GetCharPressed(); }
double miniui_dt(void) { return (double)GetFrameTime(); }
void miniui_begin(unsigned int rgba) { BeginDrawing(); ClearBackground(color(rgba)); }
void miniui_end(void) {
    if (clipping) EndScissorMode();
    clipping = 0;
    EndDrawing();
}
void miniui_clip(int x, int y, int w, int h) {
    /* BeginScissorMode flushes the old batch before replacing the clip. */
    BeginScissorMode(x, y, w, h);
    clipping = 1;
}
void miniui_rect(int x, int y, int w, int h, unsigned int rgba) {
    DrawRectangle(x, y, w, h, color(rgba));
}
void miniui_text(const char *text, int x, int y, int size, unsigned int rgba) {
    DrawText(text, x, y, size, color(rgba));
}
int miniui_width(const char *text, int size) { return MeasureText(text, size); }
