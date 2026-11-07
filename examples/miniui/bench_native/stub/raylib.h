#ifndef MINIUI_BENCH_RAYLIB_H
#define MINIUI_BENCH_RAYLIB_H
#include <stdbool.h>

typedef struct Color { unsigned char r, g, b, a; } Color;
enum {
    KEY_NULL = 0, KEY_BACKSPACE = 259, KEY_DELETE = 261,
    KEY_LEFT = 263, KEY_RIGHT = 262, KEY_HOME = 268, KEY_END = 269,
    KEY_TAB = 258, KEY_LEFT_SHIFT = 340, KEY_RIGHT_SHIFT = 344,
    KEY_ENTER = 257, KEY_SPACE = 32, KEY_ESCAPE = 256,
    MOUSE_BUTTON_LEFT = 0
};
void InitWindow(int width, int height, const char *title);
bool IsWindowReady(void);
void SetExitKey(int key);
void SetTargetFPS(int fps);
void CloseWindow(void);
bool WindowShouldClose(void);
bool IsWindowFocused(void);
int GetMouseX(void);
int GetMouseY(void);
bool IsMouseButtonDown(int button);
bool IsMouseButtonPressed(int button);
bool IsMouseButtonReleased(int button);
bool IsKeyPressed(int key);
bool IsKeyPressedRepeat(int key);
bool IsKeyDown(int key);
int GetCharPressed(void);
float GetFrameTime(void);
void BeginDrawing(void);
void ClearBackground(Color color);
void EndScissorMode(void);
void EndDrawing(void);
void BeginScissorMode(int x, int y, int width, int height);
void DrawRectangle(int x, int y, int width, int height, Color color);
void DrawText(const char *text, int x, int y, int size, Color color);
int MeasureText(const char *text, int size);
#endif
