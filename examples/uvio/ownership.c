/* Standalone bridge lifetime probe, also runnable with ASan/UBSan/LSan. */
#include "bridge.h"
#include <uv.h>
#include <assert.h>
#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int descriptor_count(void) {
    DIR *directory = opendir("/proc/self/fd");
    struct dirent *entry;
    int count = 0;
    assert(directory);
    while ((entry = readdir(directory)) != NULL)
        if (entry->d_name[0] != '.')
            count++;
    assert(closedir(directory) == 0);
    return count;
}

static void wrong_thread(void *loop) {
    assert(uvio_step(loop, 0) == UV_EPERM);
    assert(uvio_cancel(loop, 1) == UV_EPERM);
    assert(uvio_close(loop) == UV_EPERM);
}

int main(int argc, char **argv) {
    int64_t info[4];
    int port;
    int before;
    int iteration;
    int64_t previous = 0;
    uv_thread_t other;
    void *loop;
    assert(argc == 2);
    port = atoi(argv[1]);
    /* libuv initializes a process-global signal pipe once. Warm it up first. */
    loop = uvio_create(2, 65536);
    assert(loop && uvio_close(loop) == 0);
    before = descriptor_count();
    loop = uvio_create(2, 65536);
    assert(loop);
    assert(uv_thread_create(&other, wrong_thread, loop) == 0);
    assert(uv_thread_join(&other) == 0);
    for (iteration = 0; iteration < 32; iteration++) {
        size_t i;
        char *input = malloc(32769);
        int64_t id;
        assert(input);
        input[0] = 'E';
        for (i = 1; i < 32769; i++)
            input[i] = (char) (i % 251);
        id = uvio_submit(loop, "127.0.0.1", port, input, 32769, 3000);
        /* If submit retained this borrowed input, ASan or exact parity fails. */
        memset(input, 0, 32769);
        free(input);
        assert(id > previous);
        previous = id;
        while (uvio_step(loop, 1) == 0) {}
        assert(uvio_peek(loop, info, 3) == UV_EINVAL);
        assert(uvio_peek(loop, info, 4) == 1);
        assert(info[0] == id && info[1] == 0 && info[3] == 32768);
        for (i = 0; i < 32768; i++)
            assert(((unsigned char *) (intptr_t) info[2])[i] == (i + 1) % 251);
        assert(uvio_release(loop, id + 1) == UV_EINVAL);
        assert(uvio_release(loop, id) == 0);
        assert(uvio_cancel(loop, id) == UV_ENOENT);
    }
    assert(uvio_close(loop) == 0);
    for (iteration = 0; iteration < 64; iteration++) {
        int64_t id;
        loop = uvio_create(2, 64);
        assert(loop);
        id = uvio_submit(loop, "127.0.0.1", port, "wait", 4, 60000);
        assert(id > 0);
        assert(uvio_step(loop, 0) >= 0);
        assert(uvio_cancel(loop, id) == 1);
        assert(uvio_cancel(loop, id) == 0);
        assert(uvio_submit(loop, "127.0.0.1", port, "Eclose", 6, 60000) > 0);
        assert(uvio_close(loop) == 0);
    }
    assert(descriptor_count() == before);
    puts("owned-input copy, owner-thread guard, cancellation and descriptor cleanup passed");
    return 0;
}
