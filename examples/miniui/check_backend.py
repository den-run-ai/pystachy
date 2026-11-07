#!/usr/bin/env python3
"""Compile the real adapter against a fake raylib; no window or GPU is involved.

The ordinary run uses the repository's actual ctypes FFI twin. --compiler also
checks native JIT, AOT and program-only GC stress. This is NOT a real-raylib test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HEADER = r"""
#include <stdbool.h>
typedef struct Color { unsigned char r, g, b, a; } Color;
enum { KEY_NULL=0, KEY_SPACE=32, KEY_ESCAPE=256, KEY_ENTER=257, KEY_TAB=258,
 KEY_BACKSPACE=259, KEY_DELETE=261, KEY_RIGHT=262, KEY_LEFT=263, KEY_HOME=268,
 KEY_END=269, KEY_LEFT_SHIFT=340, KEY_RIGHT_SHIFT=344, MOUSE_BUTTON_LEFT=0 };
void InitWindow(int, int, const char *);
bool IsWindowReady(void);
void CloseWindow(void);
void SetExitKey(int);
void SetTargetFPS(int);
bool WindowShouldClose(void);
bool IsWindowFocused(void);
int GetMouseX(void);
int GetMouseY(void);
bool IsMouseButtonDown(int);
bool IsMouseButtonPressed(int);
bool IsMouseButtonReleased(int);
bool IsKeyPressed(int);
bool IsKeyPressedRepeat(int);
bool IsKeyDown(int);
int GetCharPressed(void);
float GetFrameTime(void);
void BeginDrawing(void);
void ClearBackground(Color);
void EndDrawing(void);
void BeginScissorMode(int, int, int, int);
void EndScissorMode(void);
void DrawRectangle(int, int, int, int, Color);
void DrawText(const char *, int, int, int, Color);
int MeasureText(const char *, int);
"""

MOCK = r"""
#include "raylib.h"
#include <string.h>
static int ready, mx, my, mouse, keys, focus=1, character, counts[6];
static const char *retained_title;
static unsigned int rgba;
void mock_events(int x, int y, int m, int k, int f) {
    mx=x; my=y; mouse=m; keys=k; focus=f; character=0;
}
int mock_stats(int i) { return counts[i]; }
unsigned int mock_color(void) { return rgba; }
void InitWindow(int w, int h, const char *title) {
    ready=w>0 && h>0; retained_title=title;
}
bool IsWindowReady(void) { return ready; }
void CloseWindow(void) { ready=0; retained_title=0; }
void SetExitKey(int key) { (void)key; }
void SetTargetFPS(int fps) { (void)fps; }
bool WindowShouldClose(void) { return false; }
bool IsWindowFocused(void) { return focus; }
int GetMouseX(void) { return mx; }
int GetMouseY(void) { return my; }
bool IsMouseButtonDown(int b) { (void)b; return (mouse&1)!=0; }
bool IsMouseButtonPressed(int b) { (void)b; return (mouse&2)!=0; }
bool IsMouseButtonReleased(int b) { (void)b; return (mouse&4)!=0; }
static int mask(int key) {
    switch(key) {
        case KEY_BACKSPACE: return 1; case KEY_DELETE: return 2;
        case KEY_LEFT: return 4; case KEY_RIGHT: return 8;
        case KEY_HOME: return 16; case KEY_END: return 32;
        case KEY_TAB: return 64; case KEY_ENTER: return 256;
        case KEY_SPACE: return 512; case KEY_ESCAPE: return 1024;
        default: return 0;
    }
}
bool IsKeyPressed(int key) { return (keys&mask(key))!=0; }
bool IsKeyPressedRepeat(int key) { (void)key; return false; }
bool IsKeyDown(int key) { (void)key; return (keys&128)!=0; }
int GetCharPressed(void) {
    character++; return character==1 ? 233 : character==2 ? 128578 : 0;
}
float GetFrameTime(void) { return 0.03125f; }
void BeginDrawing(void) { counts[0]++; }
void ClearBackground(Color c) { (void)c; }
void EndDrawing(void) { counts[1]++; }
void BeginScissorMode(int x, int y, int w, int h) {
    (void)x; (void)y; counts[4]++; if(w<0 || h<0) counts[5]++;
}
void EndScissorMode(void) {}
void DrawRectangle(int x, int y, int w, int h, Color c) {
    (void)x; (void)y; (void)w; (void)h; counts[2]++;
    rgba=((unsigned int)c.r<<24)|((unsigned int)c.g<<16)|((unsigned int)c.b<<8)|c.a;
}
void DrawText(const char *s, int x, int y, int size, Color c) {
    (void)s; (void)x; (void)y; (void)size; (void)c; counts[3]++;
}
int MeasureText(const char *text, int size) { return (int)strlen(text)*(size/2); }
int miniui_init(int, int, const char *);
void miniui_close(void);
int mock_title_copy(void) {
    char title[]="owned title";
    if(!miniui_init(100, 100, title)) return 0;
    title[0]='X';
    int ok=strcmp(retained_title,"owned title")==0;
    miniui_close(); return ok;
}
"""


def run(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{command!r} failed ({result.returncode})\n"
                           f"{result.stdout}{result.stderr}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parent.parent
    compiler = args.compiler.resolve() if args.compiler else None
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
    env["PYTHONPATH"] = str(root / "tools/rt_cpython")
    with tempfile.TemporaryDirectory(prefix="miniui-backend-") as directory:
        work = Path(directory)
        (work / "build/miniui").mkdir(parents=True)
        (work / "raylib.h").write_text(HEADER)
        (work / "mock.c").write_text(MOCK)
        run([os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-dynamiclib" if sys.platform == "darwin" else "-shared",
             "-I", str(work), str(here / "raylib_adapter.c"), str(work / "mock.c"),
             "-o", str(work / "build/miniui/libminiui.so")], work, env)
        probe = str(here / "backend_probe.py")
        expected = run([sys.executable, probe], work, env)
        print("CPython FFI twin:", expected.strip())
        if compiler:
            actual = run([str(compiler), "run", probe], work, env)
            if actual != expected:
                raise AssertionError(f"JIT output mismatch: {actual!r} != {expected!r}")
            print("JIT: matches")
            for stress in (False, True):
                native_env = dict(env)
                if stress:
                    native_env["PYSTACHY_GC_STRESS_PROGRAM"] = "1"
                exe = str(work / ("probe-stress" if stress else "probe"))
                run([str(compiler), "build", probe, "-o", exe], work, native_env)
                actual = run([exe], work, native_env)
                if actual != expected:
                    raise AssertionError(f"AOT output mismatch: {actual!r} != {expected!r}")
                print("AOT GC stress: matches" if stress else "AOT: matches")
        else:
            print("Native JIT/AOT not run; pass --compiler /path/to/pystachy.")
        print("Mock only: real raylib/window/font/rendering validation is separate.")


if __name__ == "__main__":
    main()
