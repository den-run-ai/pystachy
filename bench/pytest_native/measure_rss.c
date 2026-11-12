/* Fork after this small executable has started, so target ru_maxrss does not
 * inherit the Python benchmark controller's pre-exec resident-memory floor.
 * wait4 reports the largest individual process, not simultaneous tree RSS.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double monotonic_seconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        perror("measure_rss: clock_gettime");
        exit(125);
    }
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: measure_rss REPORT COMMAND [ARG ...]\n");
        return 125;
    }
    int fd = open(argv[1], O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) {
        perror("measure_rss: open report");
        return 125;
    }
    double started = monotonic_seconds();
    pid_t child = fork();
    if (child < 0) {
        perror("measure_rss: fork");
        close(fd);
        return 125;
    }
    if (child == 0) {
        close(fd);
        execvp(argv[2], argv + 2);
        perror("measure_rss: execvp");
        _exit(127);
    }
    int status = 0;
    struct rusage usage;
    while (wait4(child, &status, 0, &usage) < 0) {
        if (errno != EINTR) {
            perror("measure_rss: wait4");
            close(fd);
            return 125;
        }
    }
    double elapsed = monotonic_seconds() - started;
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
#ifdef __APPLE__
    long long rss = (long long)usage.ru_maxrss;
#else
    long long rss = (long long)usage.ru_maxrss * 1024;
#endif
    FILE *report = fdopen(fd, "w");
    if (report == NULL) {
        perror("measure_rss: fdopen");
        close(fd);
        return 125;
    }
    int written = fprintf(report,
        "{\"returncode\":%d,\"peak_rss_bytes\":%lld,\"user_seconds\":%.9f,"
        "\"system_seconds\":%.9f,\"target_wall_seconds\":%.9f}\n",
        code, rss, (double)usage.ru_utime.tv_sec + (double)usage.ru_utime.tv_usec / 1000000.0,
        (double)usage.ru_stime.tv_sec + (double)usage.ru_stime.tv_usec / 1000000.0, elapsed);
    int closed = fclose(report);
    if (written < 0 || closed != 0) {
        perror("measure_rss: write report");
        return 125;
    }
    if (code < 0) {
        signal(-code, SIG_DFL);
        kill(getpid(), -code);
        return 128 - code;
    }
    return code;
}
