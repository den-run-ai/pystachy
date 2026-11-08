#include "bridge.h"

#include <float.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(double) == 8 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "comm requires IEEE binary64 doubles");
_Static_assert(sizeof(uintptr_t) <= sizeof(int64_t), "pointer must fit descriptor");

typedef struct {
    unsigned char *data;
    size_t size;
    unsigned refs, readers, writers;
} Backing;

typedef struct {
    int64_t id, dtype, count;
    size_t offset;
    unsigned refs;
    Backing *backing;
} Buffer;

typedef struct {
    int64_t id, tag, kind;
    int terminal, status;
    size_t nsrc, ndst;
    Buffer *src[CC_MAX_RANKS], *dst[CC_MAX_RANKS];
} Request;

struct Comm {
    int capacity;
    size_t byte_limit, bytes;
    int64_t next_buffer, next_request;
    Buffer *buffers[CC_MAX_BUFFERS];
    Request requests[CC_MAX_REQUESTS];
    int64_t completed[CC_MAX_REQUESTS];
    size_t ncompleted;
};

static size_t width(int64_t dtype) { return dtype == CC_F64 ? 8 : 1; }

static Buffer *buffer_find(Comm *ctx, int64_t id) {
    if (ctx && id > 0)
        for (size_t i = 0; i < CC_MAX_BUFFERS; ++i)
            if (ctx->buffers[i] && ctx->buffers[i]->id == id)
                return ctx->buffers[i];
    return NULL;
}

static Request *request_find(Comm *ctx, int64_t id) {
    if (ctx && id > 0)
        for (int i = 0; i < ctx->capacity; ++i)
            if (ctx->requests[i].id == id) return &ctx->requests[i];
    return NULL;
}

static void buffer_drop(Comm *ctx, Buffer *buffer) {
    if (--buffer->refs == 0) {
        Backing *backing = buffer->backing;
        if (--backing->refs == 0) {
            ctx->bytes -= backing->size;
            free(backing->data);
            free(backing);
        }
        free(buffer);
    }
}

static void request_drop(Comm *ctx, Request *request) {
    for (size_t i = 0; i < request->nsrc; ++i) {
        --request->src[i]->backing->readers;
        buffer_drop(ctx, request->src[i]);
    }
    for (size_t i = 0; i < request->ndst; ++i) {
        --request->dst[i]->backing->writers;
        buffer_drop(ctx, request->dst[i]);
    }
    memset(request, 0, sizeof(*request));
}

static int buffer_slot(Comm *ctx) {
    for (int i = 0; i < CC_MAX_BUFFERS; ++i)
        if (!ctx->buffers[i]) return i;
    return CC_CAPACITY;
}

static int writable(const Buffer *buffer) {
    return !buffer->backing->readers && !buffer->backing->writers;
}

static unsigned char *data_at(const Buffer *buffer) {
    return buffer->backing->data + buffer->offset;
}

Comm *cc_create(int64_t capacity, int64_t byte_limit) {
    if (capacity < 1 || capacity > CC_MAX_REQUESTS ||
        byte_limit < 0 || byte_limit > 64 * 1024 * 1024) return NULL;
    Comm *ctx = calloc(1, sizeof(*ctx));
    if (!ctx) return NULL;
    ctx->capacity = (int)capacity;
    ctx->byte_limit = (size_t)byte_limit;
    ctx->next_buffer = ctx->next_request = 1;
    return ctx;
}

void cc_close(Comm *ctx) {
    if (!ctx) return;
    for (int i = 0; i < ctx->capacity; ++i)
        if (ctx->requests[i].id) request_drop(ctx, &ctx->requests[i]);
    for (size_t i = 0; i < CC_MAX_BUFFERS; ++i)
        if (ctx->buffers[i]) buffer_drop(ctx, ctx->buffers[i]);
    free(ctx);
}

const char *cc_error(int code) {
    switch (code) {
        case CC_INVALID: return "invalid argument";
        case CC_UNKNOWN: return "unknown or closed handle";
        case CC_CAPACITY: return "capacity exhausted";
        case CC_NOMEM: return "allocation failed";
        case CC_BUSY: return "buffer is leased";
        case CC_DTYPE: return "unsupported or mismatched dtype";
        case CC_SHAPE: return "buffer shape mismatch";
        case CC_ALIAS: return "input/output or output/output backing alias";
        case CC_EXHAUSTED: return "handle namespace exhausted";
        case CC_PENDING: return "request is still pending";
        case CC_SUCCESS: return "success";
        case CC_CANCELLED: return "cancelled";
        default: return "unknown status";
    }
}

int64_t cc_buffer(Comm *ctx, int64_t dtype, int64_t count) {
    if (!ctx || count < 0) return CC_INVALID;
    if (dtype != CC_U8 && dtype != CC_F64) return CC_DTYPE;
    size_t itemsize = width(dtype);
    if ((uint64_t)count > SIZE_MAX / itemsize) return CC_INVALID;
    size_t bytes = (size_t)count * itemsize;
    if (bytes > ctx->byte_limit - ctx->bytes) return CC_CAPACITY;
    int slot = buffer_slot(ctx);
    if (slot < 0) return slot;
    if (ctx->next_buffer == INT64_MAX) return CC_EXHAUSTED;
    Buffer *buffer = calloc(1, sizeof(*buffer));
    Backing *backing = calloc(1, sizeof(*backing));
    unsigned char *data = calloc(bytes ? bytes : 1, 1);
    if (!buffer || !backing || !data) {
        free(buffer);
        free(backing);
        free(data);
        return CC_NOMEM;
    }
    backing->data = data;
    backing->size = bytes;
    backing->refs = 1;
    buffer->id = ctx->next_buffer++;
    buffer->dtype = dtype;
    buffer->count = count;
    buffer->refs = 1;
    buffer->backing = backing;
    ctx->buffers[slot] = buffer;
    ctx->bytes += bytes;
    return buffer->id;
}

int64_t cc_view(Comm *ctx, int64_t id, int64_t offset, int64_t count) {
    Buffer *source = buffer_find(ctx, id);
    if (!source) return CC_UNKNOWN;
    if (offset < 0 || count < 0 || offset > source->count ||
        count > source->count - offset) return CC_INVALID;
    int slot = buffer_slot(ctx);
    if (slot < 0) return slot;
    if (ctx->next_buffer == INT64_MAX) return CC_EXHAUSTED;
    Buffer *buffer = calloc(1, sizeof(*buffer));
    if (!buffer) return CC_NOMEM;
    buffer->id = ctx->next_buffer++;
    buffer->dtype = source->dtype;
    buffer->count = count;
    buffer->offset = source->offset + (size_t)offset * width(source->dtype);
    buffer->refs = 1;
    buffer->backing = source->backing;
    ++buffer->backing->refs;
    ctx->buffers[slot] = buffer;
    return buffer->id;
}

int cc_release_buffer(Comm *ctx, int64_t id) {
    if (!ctx || id <= 0) return CC_UNKNOWN;
    for (size_t i = 0; i < CC_MAX_BUFFERS; ++i) {
        Buffer *buffer = ctx->buffers[i];
        if (buffer && buffer->id == id) {
            ctx->buffers[i] = NULL;
            buffer_drop(ctx, buffer);
            return 0;
        }
    }
    return CC_UNKNOWN;
}

int cc_info(Comm *ctx, int64_t id, int64_t *out, size_t n) {
    Buffer *buffer = buffer_find(ctx, id);
    if (!buffer) return CC_UNKNOWN;
    if (!out || n != 5) return CC_INVALID;
    out[0] = buffer->dtype;
    out[1] = buffer->count;
    out[2] = buffer->count * (int64_t)width(buffer->dtype);
    out[3] = (int64_t)buffer->offset;
    out[4] = CC_HOST;
    return 0;
}

int cc_write_bytes(Comm *ctx, int64_t id, const char *data, size_t n) {
    Buffer *buffer = buffer_find(ctx, id);
    if (!buffer) return CC_UNKNOWN;
    if (buffer->dtype != CC_U8) return CC_DTYPE;
    if (n != (size_t)buffer->count) return CC_SHAPE;
    if (n && !data) return CC_INVALID;
    if (!writable(buffer)) return CC_BUSY;
    if (n) memmove(data_at(buffer), data, n);
    return 0;
}

int cc_read_bytes(Comm *ctx, int64_t id, int64_t *out, size_t n) {
    Buffer *buffer = buffer_find(ctx, id);
    if (!buffer) return CC_UNKNOWN;
    if (buffer->dtype != CC_U8) return CC_DTYPE;
    if (!out || n != 2) return CC_INVALID;
    if (buffer->backing->writers) return CC_BUSY;
    uintptr_t address = (uintptr_t)data_at(buffer);
    if (address > INT64_MAX) return CC_INVALID;
    out[0] = (int64_t)address;
    out[1] = buffer->count;
    return 0;
}

int cc_write_f64(Comm *ctx, int64_t id, const double *data, size_t n) {
    Buffer *buffer = buffer_find(ctx, id);
    if (!buffer) return CC_UNKNOWN;
    if (buffer->dtype != CC_F64) return CC_DTYPE;
    if (n != (size_t)buffer->count) return CC_SHAPE;
    if (n && !data) return CC_INVALID;
    if (!writable(buffer)) return CC_BUSY;
    if (n) memmove(data_at(buffer), data, n * sizeof(double));
    return 0;
}

int cc_read_f64(Comm *ctx, int64_t id, double *data, size_t n) {
    Buffer *buffer = buffer_find(ctx, id);
    if (!buffer) return CC_UNKNOWN;
    if (buffer->dtype != CC_F64) return CC_DTYPE;
    if (n != (size_t)buffer->count) return CC_SHAPE;
    if (n && !data) return CC_INVALID;
    if (buffer->backing->writers) return CC_BUSY;
    if (n) memmove(data, data_at(buffer), n * sizeof(double));
    return 0;
}

int64_t cc_submit(Comm *ctx, int64_t kind,
                  const int64_t *sources, size_t nsrc,
                  const int64_t *destinations, size_t ndst, int64_t tag) {
    if (!ctx || !sources || !destinations || !nsrc || !ndst ||
        nsrc > CC_MAX_RANKS || ndst > CC_MAX_RANKS) return CC_INVALID;
    if ((kind == CC_COPY && (nsrc != 1 || ndst != 1)) ||
        (kind == CC_BROADCAST && nsrc != 1) ||
        ((kind == CC_ALLGATHER || kind == CC_ALLREDUCE_SUM) && nsrc != ndst) ||
        kind < CC_COPY || kind > CC_ALLREDUCE_SUM) return CC_INVALID;
    Request *slot = NULL;
    for (int i = 0; i < ctx->capacity; ++i)
        if (!ctx->requests[i].id) { slot = &ctx->requests[i]; break; }
    if (!slot) return CC_CAPACITY;
    if (ctx->next_request == INT64_MAX) return CC_EXHAUSTED;

    /* Resolve and validate everything in a temporary descriptor. No lease,
     * reference, ID or queue state changes until every check succeeds. */
    Request request = {0};
    request.nsrc = nsrc;
    request.ndst = ndst;
    request.kind = kind;
    request.tag = tag;
    for (size_t i = 0; i < nsrc; ++i) {
        Buffer *buffer = buffer_find(ctx, sources[i]);
        if (!buffer) return CC_UNKNOWN;
        if (buffer->backing->writers) return CC_BUSY;
        if (kind == CC_ALLREDUCE_SUM && buffer->dtype != CC_F64) return CC_DTYPE;
        if (i && buffer->dtype != request.src[0]->dtype) return CC_DTYPE;
        if (i && buffer->count != request.src[0]->count) return CC_SHAPE;
        request.src[i] = buffer;
    }
    int64_t count = request.src[0]->count;
    if (kind == CC_ALLGATHER) {
        if (count > INT64_MAX / (int64_t)nsrc) return CC_INVALID;
        count *= (int64_t)nsrc;
    }
    for (size_t i = 0; i < ndst; ++i) {
        Buffer *buffer = buffer_find(ctx, destinations[i]);
        if (!buffer) return CC_UNKNOWN;
        if (!writable(buffer)) return CC_BUSY;
        if (buffer->dtype != request.src[0]->dtype) return CC_DTYPE;
        if (buffer->count != count) return CC_SHAPE;
        for (size_t j = 0; j < nsrc; ++j)
            if (buffer->backing == request.src[j]->backing) return CC_ALIAS;
        for (size_t j = 0; j < i; ++j)
            if (buffer->backing == request.dst[j]->backing) return CC_ALIAS;
        request.dst[i] = buffer;
    }
    request.id = ctx->next_request++;
    for (size_t i = 0; i < nsrc; ++i) {
        ++request.src[i]->refs;
        ++request.src[i]->backing->readers;
    }
    for (size_t i = 0; i < ndst; ++i) {
        ++request.dst[i]->refs;
        ++request.dst[i]->backing->writers;
    }
    *slot = request;
    return request.id;
}

static void execute(Request *request) {
    Buffer *first = request->src[0];
    size_t nbytes = (size_t)first->count * width(first->dtype);
    if (request->kind == CC_ALLREDUCE_SUM) {
        double *output = (double *)data_at(request->dst[0]);
        for (int64_t item = 0; item < first->count; ++item) {
            double sum = 0.0;
            for (size_t rank = 0; rank < request->nsrc; ++rank)
                sum += ((const double *)data_at(request->src[rank]))[item];
            output[item] = sum;
        }
        for (size_t rank = 1; rank < request->ndst; ++rank)
            if (nbytes) memcpy(data_at(request->dst[rank]), output, nbytes);
    } else {
        for (size_t rank = 0; rank < request->ndst; ++rank) {
            unsigned char *output = data_at(request->dst[rank]);
            size_t ninputs = request->kind == CC_ALLGATHER ? request->nsrc : 1;
            for (size_t input = 0; input < ninputs; ++input)
                if (nbytes) memcpy(output + input * nbytes,
                                   data_at(request->src[input]), nbytes);
        }
    }
}

static void complete(Comm *ctx, Request *request, int status) {
    request->terminal = 1;
    request->status = status;
    ctx->completed[ctx->ncompleted++] = request->id;
}

int cc_progress(Comm *ctx, int64_t max_work) {
    if (!ctx || max_work < 0 || max_work > CC_MAX_REQUESTS) return CC_INVALID;
    int done = 0;
    while (done < max_work) {
        Request *next = NULL;
        for (int i = 0; i < ctx->capacity; ++i) {
            Request *request = &ctx->requests[i];
            if (request->id && !request->terminal && (!next || request->id < next->id))
                next = request;
        }
        if (!next) break;
        execute(next);
        complete(ctx, next, CC_SUCCESS);
        ++done;
    }
    return done;
}

int cc_cancel(Comm *ctx, int64_t id) {
    Request *request = request_find(ctx, id);
    if (!request) return CC_UNKNOWN;
    if (request->terminal) return 0;
    complete(ctx, request, CC_CANCELLED);
    return 1;
}

int cc_status(Comm *ctx, int64_t id) {
    Request *request = request_find(ctx, id);
    return request ? request->terminal : CC_UNKNOWN;
}

int cc_peek(Comm *ctx, int64_t *out, size_t n) {
    if (!ctx || !out || n != 4) return CC_INVALID;
    if (!ctx->ncompleted) return 0;
    Request *request = request_find(ctx, ctx->completed[0]);
    out[0] = request->id;
    out[1] = request->tag;
    out[2] = request->status;
    out[3] = request->kind;
    return 1;
}

int cc_ack(Comm *ctx, int64_t id) {
    Request *request = request_find(ctx, id);
    if (!request) return CC_UNKNOWN;
    if (!request->terminal) return CC_PENDING;
    for (size_t i = 0; i < ctx->ncompleted; ++i) {
        if (ctx->completed[i] == id) {
            for (size_t j = i + 1; j < ctx->ncompleted; ++j)
                ctx->completed[j - 1] = ctx->completed[j];
            --ctx->ncompleted;
            request_drop(ctx, request);
            return 0;
        }
    }
    return CC_UNKNOWN; /* Internal invariant: every terminal is queued once. */
}
