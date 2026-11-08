/* Native lifetime/ABI checks, including adversarial raw-C calls. */
#include "bridge.h"

#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static void bytes_equal(Comm *ctx, int64_t id, const char *expected, size_t n) {
    int64_t info[2] = {0};
    assert(cc_read_bytes(ctx, id, info, 2) == 0);
    assert(info[1] == (int64_t)n);
    if (n) assert(memcmp((const void *)(uintptr_t)info[0], expected, n) == 0);
}

static void take(Comm *ctx, int64_t id, int status, int64_t tag, int kind) {
    int64_t info[4] = {0};
    assert(cc_peek(ctx, info, 4) == 1);
    assert(info[0] == id && info[1] == tag && info[2] == status && info[3] == kind);
    assert(cc_ack(ctx, id) == 0);
    assert(cc_ack(ctx, id) == CC_UNKNOWN);
    assert(cc_status(ctx, id) == CC_UNKNOWN);
}

static void collectives(void) {
    Comm *ctx = cc_create(4, 1024);
    assert(ctx);
    int64_t src[3], dst[3];
    for (size_t i = 0; i < 3; ++i) {
        src[i] = cc_buffer(ctx, CC_F64, 2);
        dst[i] = cc_buffer(ctx, CC_F64, 2);
        double values[2] = {(double)i + 1.0, (double)i * -2.0};
        assert(cc_write_f64(ctx, src[i], values, 2) == 0);
    }
    int64_t request = cc_submit(ctx, CC_ALLREDUCE_SUM, src, 3, dst, 3, 92);
    assert(request > 0);
    assert(cc_ack(ctx, request) == CC_PENDING);
    assert(cc_status(ctx, request) == 0);
    double values[2];
    assert(cc_read_f64(ctx, dst[0], values, 2) == CC_BUSY);
    assert(cc_write_f64(ctx, src[0], values, 2) == CC_BUSY);
    assert(cc_progress(ctx, 1) == 1 && cc_status(ctx, request) == 1);
    assert(cc_cancel(ctx, request) == 0);
    assert(cc_read_f64(ctx, dst[0], values, 2) == CC_BUSY);
    take(ctx, request, CC_SUCCESS, 92, CC_ALLREDUCE_SUM);
    for (size_t i = 0; i < 3; ++i) {
        assert(cc_read_f64(ctx, dst[i], values, 2) == 0);
        assert(values[0] == 6.0 && values[1] == -6.0);
        assert(cc_release_buffer(ctx, dst[i]) == 0);
        dst[i] = cc_buffer(ctx, CC_F64, 6);
    }
    request = cc_submit(ctx, CC_ALLGATHER, src, 3, dst, 3, -2);
    assert(request > 0 && cc_progress(ctx, 64) == 1);
    take(ctx, request, CC_SUCCESS, -2, CC_ALLGATHER);
    double gathered[6];
    for (size_t i = 0; i < 3; ++i) {
        assert(cc_read_f64(ctx, dst[i], gathered, 6) == 0);
        for (size_t j = 0; j < 3; ++j) {
            assert(gathered[2 * j] == (double)j + 1.0);
            assert(gathered[2 * j + 1] == (double)j * -2.0);
        }
    }
    cc_close(ctx);
}

static void lifetime(void) {
    Comm *ctx = cc_create(2, 10);
    assert(ctx);
    int64_t source = cc_buffer(ctx, CC_U8, 6);
    int64_t dest = cc_buffer(ctx, CC_U8, 4);
    assert(source > 0 && dest > 0);
    char input[6] = {'x', '\0', 'a', '\xff', 'z', 'y'};
    assert(cc_write_bytes(ctx, source, input, 6) == 0);
    int64_t view = cc_view(ctx, source, 1, 4);
    assert(view > 0);
    assert(cc_release_buffer(ctx, source) == 0);
    assert(cc_release_buffer(ctx, source) == CC_UNKNOWN);
    int64_t request = cc_submit(ctx, CC_COPY, &view, 1, &dest, 1, 17);
    assert(request > 0);
    assert(cc_release_buffer(ctx, view) == 0);
    assert(cc_buffer(ctx, CC_U8, 1) == CC_CAPACITY);
    memset(input, 42, sizeof(input)); /* Borrowed input was not retained. */
    assert(cc_progress(ctx, 1) == 1);
    take(ctx, request, CC_SUCCESS, 17, CC_COPY);
    bytes_equal(ctx, dest, "\0a\xffz", 4);
    int64_t replacement = cc_buffer(ctx, CC_U8, 6);
    assert(replacement > view);
    assert(cc_release_buffer(ctx, replacement) == 0);
    assert(cc_release_buffer(ctx, dest) == 0);
    /* Closing user outputs too is safe; the request owns both sides. */
    source = cc_buffer(ctx, CC_U8, 2);
    dest = cc_buffer(ctx, CC_U8, 2);
    request = cc_submit(ctx, CC_COPY, &source, 1, &dest, 1, 0);
    assert(request > 0);
    assert(cc_release_buffer(ctx, source) == 0);
    assert(cc_release_buffer(ctx, dest) == 0);
    assert(cc_progress(ctx, 1) == 1);
    take(ctx, request, CC_SUCCESS, 0, CC_COPY);
    cc_close(ctx);
}

static void cancellation_and_capacity(void) {
    Comm *ctx = cc_create(2, 16);
    assert(ctx);
    int64_t source = cc_buffer(ctx, CC_U8, 2);
    int64_t one = cc_buffer(ctx, CC_U8, 2);
    int64_t two = cc_buffer(ctx, CC_U8, 2);
    int64_t three = cc_buffer(ctx, CC_U8, 2);
    assert(cc_write_bytes(ctx, source, "ok", 2) == 0);
    int64_t first = cc_submit(ctx, CC_COPY, &source, 1, &one, 1, 1);
    int64_t second = cc_submit(ctx, CC_COPY, &source, 1, &two, 1, 2);
    assert(first > 0 && second > first);
    assert(cc_cancel(ctx, second) == 1 && cc_cancel(ctx, second) == 0);
    assert(cc_progress(ctx, 0) == 0 && cc_status(ctx, first) == 0);
    assert(cc_progress(ctx, 1) == 1);
    assert(cc_submit(ctx, CC_COPY, &source, 1, &three, 1, 3) == CC_CAPACITY);
    take(ctx, second, CC_CANCELLED, 2, CC_COPY); /* Completion, not submit order. */
    bytes_equal(ctx, two, "\0\0", 2);
    assert(cc_write_bytes(ctx, source, "no", 2) == CC_BUSY); /* First still leases. */
    take(ctx, first, CC_SUCCESS, 1, CC_COPY);
    bytes_equal(ctx, one, "ok", 2);
    assert(cc_write_bytes(ctx, source, "no", 2) == 0);
    int64_t third = cc_submit(ctx, CC_COPY, &source, 1, &three, 1, 3);
    assert(third > second);
    cc_close(ctx); /* Pending operation is quiesced without reading freed input. */
}

static void validation(void) {
    assert(!cc_create(0, 1) && !cc_create(65, 1));
    assert(!cc_create(1, -1) && !cc_create(1, INT64_MAX));
    assert(cc_progress(NULL, 1) == CC_INVALID);
    cc_close(NULL);
    Comm *ctx = cc_create(4, 1024);
    assert(ctx);
    assert(cc_buffer(ctx, CC_F64, INT64_MAX) == CC_INVALID);
    assert(cc_buffer(ctx, CC_U8, -1) == CC_INVALID);
    assert(cc_buffer(ctx, 3, 0) == CC_DTYPE);
    int64_t src = cc_buffer(ctx, CC_U8, 8);
    int64_t dst = cc_buffer(ctx, CC_U8, 8);
    int64_t view = cc_view(ctx, src, 2, 4);
    assert(view > 0);
    assert(cc_view(ctx, src, INT64_MAX, 1) == CC_INVALID);
    assert(cc_view(ctx, src, 1, INT64_MAX) == CC_INVALID);
    assert(cc_view(ctx, src, -1, 1) == CC_INVALID);
    assert(cc_view(ctx, src, 9, 0) == CC_INVALID);
    int64_t info[5];
    assert(cc_info(ctx, view, info, 5) == 0);
    assert(info[0] == CC_U8 && info[1] == 4 && info[2] == 4 &&
           info[3] == 2 && info[4] == CC_HOST);
    assert(cc_info(ctx, view, info, 4) == CC_INVALID);
    assert(cc_read_bytes(ctx, src, NULL, 2) == CC_INVALID);
    assert(cc_write_bytes(ctx, src, NULL, 8) == CC_INVALID);
    assert(cc_write_bytes(ctx, src, "x", 1) == CC_SHAPE);
    assert(cc_submit(ctx, CC_COPY, &src, 1, &src, 1, 0) == CC_ALIAS);
    int64_t outputs[2] = {dst, dst};
    assert(cc_submit(ctx, CC_BROADCAST, &src, 1, outputs, 2, 0) == CC_ALIAS);
    assert(cc_submit(ctx, CC_ALLREDUCE_SUM, &src, 1, &dst, 1, 0) == CC_DTYPE);
    assert(cc_submit(ctx, 0, &src, 1, &dst, 1, 0) == CC_INVALID);
    assert(cc_submit(ctx, CC_COPY, &src, SIZE_MAX, &dst, 1, 0) == CC_INVALID);
    assert(cc_submit(ctx, CC_COPY, NULL, 1, &dst, 1, 0) == CC_INVALID);
    assert(cc_write_bytes(ctx, src, "abcdefgh", 8) == 0); /* Rejections took no lease. */
    int64_t request = cc_submit(ctx, CC_COPY, &src, 1, &dst, 1, 0);
    assert(request == 1); /* Failed submissions did not advance the namespace. */
    assert(cc_write_bytes(ctx, view, "fail", 4) == CC_BUSY);
    assert(cc_progress(ctx, -1) == CC_INVALID && cc_progress(ctx, 65) == CC_INVALID);
    assert(cc_cancel(ctx, request) == 1);
    assert(cc_write_bytes(ctx, view, "fail", 4) == CC_BUSY);
    take(ctx, request, CC_CANCELLED, 0, CC_COPY);
    assert(cc_write_bytes(ctx, view, "done", 4) == 0);
    bytes_equal(ctx, src, "abdonegh", 8);
    int64_t overlap = cc_view(ctx, src, 1, 7);
    assert(overlap > 0);
    assert(cc_read_bytes(ctx, src, info, 2) == 0);
    assert(cc_write_bytes(ctx, overlap, (const char *)(uintptr_t)info[0], 7) == 0);
    bytes_equal(ctx, src, "aabdoneg", 8);
    cc_close(ctx);

    ctx = cc_create(1, 0);
    assert(ctx);
    src = cc_buffer(ctx, CC_F64, 0);
    dst = cc_buffer(ctx, CC_F64, 0);
    assert(src > 0 && dst > 0);
    assert(cc_write_f64(ctx, src, NULL, 0) == 0);
    request = cc_submit(ctx, CC_ALLREDUCE_SUM, &src, 1, &dst, 1, 0);
    assert(request > 0 && cc_progress(ctx, 1) == 1);
    take(ctx, request, CC_SUCCESS, 0, CC_ALLREDUCE_SUM);
    assert(cc_read_f64(ctx, dst, NULL, 0) == 0);
    for (int i = 2; i < CC_MAX_BUFFERS; ++i) assert(cc_buffer(ctx, CC_U8, 0) > 0);
    assert(cc_buffer(ctx, CC_U8, 0) == CC_CAPACITY);
    cc_close(ctx);
}

int main(void) {
    for (int i = 0; i < 300; ++i) {
        collectives();
        lifetime();
        cancellation_and_capacity();
        validation();
    }
    puts("comm ownership: 300 cycles passed");
    return 0;
}
