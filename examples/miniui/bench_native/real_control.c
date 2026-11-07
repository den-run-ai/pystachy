/* Benchmark-only controls; raylib_adapter.c itself is compiled unchanged. */
#include <stdint.h>
#include "raylib.h"

void miniui_bench_configure(void) {
    /* The production adapter sets 60 FPS. Disable both throttles for measurement. */
    SetTargetFPS(0);
    ClearWindowState(FLAG_VSYNC_HINT);
    SetTraceLogLevel(LOG_WARNING);
}
void miniui_bench_reset(void) { }
/* -1 means unavailable, never an implied zero rendering cost. */
int64_t miniui_bench_calls(void) { return -1; }
int64_t miniui_bench_hash(void) { return -1; }
int64_t miniui_bench_rects(void) { return -1; }
int64_t miniui_bench_texts(void) { return -1; }
int64_t miniui_bench_clips(void) { return -1; }
int64_t miniui_bench_begins(void) { return -1; }
int64_t miniui_bench_ends(void) { return -1; }
int64_t miniui_bench_widths(void) { return -1; }
int miniui_bench_snapshot(const char *path) {
    Image image = LoadImageFromScreen();
    if (!image.data) return 0;
    int ok = ExportImage(image, path);
    UnloadImage(image);
    return ok;
}
