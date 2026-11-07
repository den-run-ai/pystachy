/* Deterministic submission benchmark, deliberately no window or rasterizer.
 * Compile MINIUI_BENCH_HASH=0 for timing; =1 for untimed stream verification.
 * Calls/counters always execute. No LTO is used across the adapter and this TU. */
#include <stdint.h>
#include <string.h>
#include "raylib.h"
#ifndef MINIUI_BENCH_HASH
#define MINIUI_BENCH_HASH 0
#endif
static int ready;
static volatile int64_t calls;
static int64_t rects, texts, clips, begins, ends, widths;
static uint32_t digest = 2166136261u;

static void mix(uint32_t value) {
#if MINIUI_BENCH_HASH
    digest = (digest ^ value) * 16777619u;
#else
    (void)value;
#endif
}
static void event(uint32_t tag) { calls++; mix(tag); }
static void color_value(Color c) {
    mix(((uint32_t)c.r << 24) | ((uint32_t)c.g << 16)
        | ((uint32_t)c.b << 8) | c.a);
}
static void rect_value(int x, int y, int w, int h) {
    mix((uint32_t)x); mix((uint32_t)y); mix((uint32_t)w); mix((uint32_t)h);
}
static void text_value(const char *text) {
#if MINIUI_BENCH_HASH
    const unsigned char *p = (const unsigned char *)text;
    while (*p) mix(*p++);
    mix(0);
#else
    (void)text;
#endif
}
void InitWindow(int width, int height, const char *title) {
    ready = 1; event(1); mix((uint32_t)width); mix((uint32_t)height); text_value(title);
}
bool IsWindowReady(void) { return ready != 0; }
void SetExitKey(int key) { (void)key; }
void SetTargetFPS(int fps) { (void)fps; }
void CloseWindow(void) { ready = 0; }
bool WindowShouldClose(void) { return false; }
bool IsWindowFocused(void) { return true; }
int GetMouseX(void) { return 0; }
int GetMouseY(void) { return 0; }
bool IsMouseButtonDown(int button) { (void)button; return false; }
bool IsMouseButtonPressed(int button) { (void)button; return false; }
bool IsMouseButtonReleased(int button) { (void)button; return false; }
bool IsKeyPressed(int key) { (void)key; return false; }
bool IsKeyPressedRepeat(int key) { (void)key; return false; }
bool IsKeyDown(int key) { (void)key; return false; }
int GetCharPressed(void) { return 0; }
float GetFrameTime(void) { return 1.0f / 60.0f; }
void BeginDrawing(void) { event(2); begins++; }
void ClearBackground(Color color) { event(3); color_value(color); }
void EndScissorMode(void) { event(4); }
void EndDrawing(void) { event(5); ends++; }
void BeginScissorMode(int x, int y, int width, int height) {
    event(6); clips++; rect_value(x, y, width, height);
}
void DrawRectangle(int x, int y, int width, int height, Color color) {
    event(7); rects++; rect_value(x, y, width, height); color_value(color);
}
void DrawText(const char *text, int x, int y, int size, Color color) {
    event(8); texts++; text_value(text); mix((uint32_t)x); mix((uint32_t)y);
    mix((uint32_t)size); color_value(color);
}
int MeasureText(const char *text, int size) {
    event(9); widths++; text_value(text); mix((uint32_t)size);
    /* ASCII benchmark text; this models a deterministic width, not raylib fonts. */
    return (int)strlen(text) * size / 2;
}
void miniui_bench_configure(void) { }
void miniui_bench_reset(void) {
    calls = 0; rects = 0; texts = 0; clips = 0; begins = 0; ends = 0; widths = 0;
    digest = 2166136261u;
}
int64_t miniui_bench_calls(void) { return calls; }
int64_t miniui_bench_hash(void) { return MINIUI_BENCH_HASH ? (int64_t)digest : -1; }
int64_t miniui_bench_rects(void) { return rects; }
int64_t miniui_bench_texts(void) { return texts; }
int64_t miniui_bench_clips(void) { return clips; }
int64_t miniui_bench_begins(void) { return begins; }
int64_t miniui_bench_ends(void) { return ends; }
int64_t miniui_bench_widths(void) { return widths; }
int miniui_bench_snapshot(const char *path) { (void)path; return 0; }
