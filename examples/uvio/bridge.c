/* Optional owned-buffer libuv experiment. See README.md for the API contract. */
#include "bridge.h"
#include <uv.h>

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define UVIO_MAX_REQUESTS 64
#define UVIO_MAX_BYTES (1024 * 1024)
#define UVIO_MAX_TIMEOUT 60000

typedef struct uvio_loop uvio_loop;
typedef struct uvio_request uvio_request;

struct uvio_request {
    uvio_loop *owner;
    int index;
    int64_t id;
    uv_tcp_t tcp;
    uv_timer_t timer;
    uv_connect_t connect;
    uv_write_t write;
    uv_shutdown_t shutdown;
    struct sockaddr_in address;
    char *input;
    size_t input_size;
    char *output;
    size_t output_size;
    char scratch[4096];
    int handles;
    int pending;
    int tcp_initialized;
    int timer_initialized;
    int read_eof;
    int sent;
    int terminal;
    int queued;
    int status;
};

struct uvio_loop {
    uv_loop_t loop;
    uv_thread_t thread;
    int capacity;
    size_t byte_limit;
    int64_t next_id;
    uvio_request *requests[UVIO_MAX_REQUESTS];
    uvio_request *events[UVIO_MAX_REQUESTS];
    int head;
    int count;
};

static int owner_thread(uvio_loop *loop) {
    uv_thread_t current = uv_thread_self();
    return uv_thread_equal(&loop->thread, &current);
}

/* One reserved slot owns one terminal event. A full ring cannot overflow. */
static void complete(uvio_request *request) {
    uvio_loop *loop = request->owner;
    if (!request->terminal || request->handles || request->pending || request->queued)
        return;
    request->queued = 1;
    loop->events[(loop->head + loop->count) % loop->capacity] = request;
    loop->count++;
}

static void closed(uv_handle_t *handle) {
    uvio_request *request = handle->data;
    request->handles--;
    complete(request);
}

static void finish(uvio_request *request, int status) {
    if (request->terminal)
        return;
    request->terminal = 1;
    request->status = status;
    if (request->timer_initialized) {
        uv_timer_stop(&request->timer);
        uv_close((uv_handle_t *) &request->timer, closed);
    }
    if (request->tcp_initialized) {
        uv_read_stop((uv_stream_t *) &request->tcp);
        uv_close((uv_handle_t *) &request->tcp, closed);
    }
    complete(request);
}

static void timed_out(uv_timer_t *timer) {
    finish(timer->data, UV_ETIMEDOUT);
}

static void allocate(uv_handle_t *handle, size_t suggested_size, uv_buf_t *buffer) {
    uvio_request *request = handle->data;
    (void) suggested_size;
    *buffer = uv_buf_init(request->scratch, sizeof(request->scratch));
}

static void read_result(uv_stream_t *stream, ssize_t nread, const uv_buf_t *buffer) {
    uvio_request *request = stream->data;
    if (request->terminal)
        return;
    if (nread > 0) {
        size_t remaining = request->owner->byte_limit - request->output_size;
        size_t take = (size_t) nread < remaining ? (size_t) nread : remaining;
        memcpy(request->output + request->output_size, buffer->base, take);
        request->output_size += take;
        if ((size_t) nread > remaining)
            finish(request, UV_ENOBUFS);
    } else if (nread == UV_EOF) {
        uv_read_stop(stream);
        request->read_eof = 1;
        if (request->sent)
            finish(request, 0);
    } else if (nread < 0) {
        finish(request, (int) nread);
    }
}

static void shutdown_done(uv_shutdown_t *shutdown, int status) {
    uvio_request *request = shutdown->data;
    request->pending--;
    if (!request->terminal) {
        if (status < 0)
            finish(request, status);
        else {
            request->sent = 1;
            if (request->read_eof)
                finish(request, 0);
        }
    }
    complete(request);
}

static void shutdown_write(uvio_request *request) {
    int status;
    request->shutdown.data = request;
    request->pending++;
    status = uv_shutdown(&request->shutdown, (uv_stream_t *) &request->tcp, shutdown_done);
    if (status < 0) {
        request->pending--;
        finish(request, status);
    }
}

static void write_done(uv_write_t *write, int status) {
    uvio_request *request = write->data;
    request->pending--;
    if (!request->terminal) {
        if (status < 0)
            finish(request, status);
        else
            shutdown_write(request);
    }
    complete(request);
}

static void connected(uv_connect_t *connect, int status) {
    uvio_request *request = connect->data;
    uv_buf_t buffer;
    request->pending--;
    if (request->terminal) {
        complete(request);
        return;
    }
    if (status < 0) {
        finish(request, status);
        return;
    }
    status = uv_read_start((uv_stream_t *) &request->tcp, allocate, read_result);
    if (status < 0) {
        finish(request, status);
        return;
    }
    if (!request->input_size) {
        shutdown_write(request);
        return;
    }
    buffer = uv_buf_init(request->input, (unsigned int) request->input_size);
    request->write.data = request;
    request->pending++;
    status = uv_write(&request->write, (uv_stream_t *) &request->tcp, &buffer, 1, write_done);
    if (status < 0) {
        request->pending--;
        finish(request, status);
    }
}

static void dispose(uvio_request *request) {
    free(request->input);
    free(request->output);
    free(request);
}

void *uvio_create(int64_t capacity, int64_t byte_limit) {
    uvio_loop *loop;
    if (capacity < 1 || capacity > UVIO_MAX_REQUESTS ||
        byte_limit < 1 || byte_limit > UVIO_MAX_BYTES)
        return NULL;
    loop = calloc(1, sizeof(*loop));
    if (!loop)
        return NULL;
    if (uv_loop_init(&loop->loop) < 0) {
        free(loop);
        return NULL;
    }
    loop->thread = uv_thread_self();
    loop->capacity = (int) capacity;
    loop->byte_limit = (size_t) byte_limit;
    loop->next_id = 1;
    return loop;
}

/* All borrowed inputs are consumed/copied before returning to managed code. */
int64_t uvio_submit(void *opaque, const char *address, int64_t port,
                    const char *input, uint64_t input_size, int64_t timeout_ms) {
    uvio_loop *loop = opaque;
    uvio_request *request;
    struct sockaddr_in parsed;
    int index;
    int status;
    if (!loop || !owner_thread(loop))
        return UV_EPERM;
    if (port < 1 || port > 65535 || timeout_ms < 1 || timeout_ms > UVIO_MAX_TIMEOUT)
        return UV_EINVAL;
    if (input_size > loop->byte_limit)
        return UV_E2BIG;
    status = uv_ip4_addr(address, (int) port, &parsed);
    if (status < 0)
        return status;
    for (index = 0; index < loop->capacity; index++)
        if (!loop->requests[index])
            break;
    if (index == loop->capacity)
        return UV_EBUSY;
    if (loop->next_id == INT64_MAX)
        return UV_EOVERFLOW;
    request = calloc(1, sizeof(*request));
    if (!request)
        return UV_ENOMEM;
    request->input = malloc(input_size ? (size_t) input_size : 1);
    request->output = malloc(loop->byte_limit);
    if (!request->input || !request->output) {
        dispose(request);
        return UV_ENOMEM;
    }
    if (input_size)
        memcpy(request->input, input, (size_t) input_size);
    request->input_size = (size_t) input_size;
    request->owner = loop;
    request->index = index;
    request->id = loop->next_id++;
    request->address = parsed;
    loop->requests[index] = request;
    status = uv_tcp_init(&loop->loop, &request->tcp);
    if (status < 0) {
        finish(request, status);
        return request->id;
    }
    request->tcp_initialized = 1;
    request->handles++;
    request->tcp.data = request;
    status = uv_timer_init(&loop->loop, &request->timer);
    if (status < 0) {
        finish(request, status);
        return request->id;
    }
    request->timer_initialized = 1;
    request->handles++;
    request->timer.data = request;
    uv_update_time(&loop->loop);
    status = uv_timer_start(&request->timer, timed_out, (uint64_t) timeout_ms, 0);
    if (status < 0) {
        finish(request, status);
        return request->id;
    }
    request->connect.data = request;
    request->pending++;
    status = uv_tcp_connect(&request->connect, &request->tcp,
                           (const struct sockaddr *) &request->address, connected);
    if (status < 0) {
        request->pending--;
        finish(request, status);
    }
    return request->id;
}

int uvio_step(void *opaque, int block) {
    uvio_loop *loop = opaque;
    if (!loop || !owner_thread(loop))
        return UV_EPERM;
    if (!loop->count)
        uv_run(&loop->loop, block ? UV_RUN_ONCE : UV_RUN_NOWAIT);
    return loop->count;
}

/* Output points only into native storage, valid until uvio_release/close. */
int uvio_peek(void *opaque, int64_t *info, uint64_t length) {
    uvio_loop *loop = opaque;
    uvio_request *request;
    if (!loop || !owner_thread(loop))
        return UV_EPERM;
    if (length != 4)
        return UV_EINVAL;
    if (!loop->count)
        return 0;
    request = loop->events[loop->head];
    info[0] = request->id;
    info[1] = request->status;
    info[2] = (int64_t) (intptr_t) request->output;
    info[3] = (int64_t) request->output_size;
    return 1;
}

int uvio_release(void *opaque, int64_t id) {
    uvio_loop *loop = opaque;
    uvio_request *request;
    if (!loop || !owner_thread(loop))
        return UV_EPERM;
    if (!loop->count || loop->events[loop->head]->id != id)
        return UV_EINVAL;
    request = loop->events[loop->head];
    loop->requests[request->index] = NULL;
    loop->events[loop->head] = NULL;
    loop->head = (loop->head + 1) % loop->capacity;
    loop->count--;
    dispose(request);
    return 0;
}

int uvio_cancel(void *opaque, int64_t id) {
    uvio_loop *loop = opaque;
    int index;
    if (!loop || !owner_thread(loop))
        return UV_EPERM;
    for (index = 0; index < loop->capacity; index++) {
        uvio_request *request = loop->requests[index];
        if (request && request->id == id) {
            if (request->terminal)
                return 0;
            finish(request, UV_ECANCELED);
            return 1;
        }
    }
    return UV_ENOENT;
}

int uvio_close(void *opaque) {
    uvio_loop *loop = opaque;
    int index;
    int status;
    if (!loop)
        return 0;
    if (!owner_thread(loop))
        return UV_EPERM;
    for (index = 0; index < loop->capacity; index++)
        if (loop->requests[index])
            finish(loop->requests[index], UV_ECANCELED);
    uv_run(&loop->loop, UV_RUN_DEFAULT);
    status = uv_loop_close(&loop->loop);
    if (status < 0)
        return status;
    for (index = 0; index < loop->capacity; index++)
        if (loop->requests[index])
            dispose(loop->requests[index]);
    free(loop);
    return 0;
}

const char *uvio_error_name(int status) {
    return status == 0 ? "OK" : uv_err_name(status);
}

const char *uvio_version(void) {
    return uv_version_string();
}
