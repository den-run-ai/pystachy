/* Run one command and report its wall time, CPU time, peak RSS and status.
 *
 * A child's peak RSS starts from the image that forked it, so a benchmark
 * driver holding hundreds of megabytes cannot measure a small program
 * itself. This launcher stays about a megabyte.
 *
 * usage: timerun REPORT COMMAND [ARGS...]
 * REPORT receives one line: wall_s user_s system_s max_rss_kb exit_status
 */
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double seconds(struct timeval value) { return value.tv_sec + value.tv_usec / 1e6; }

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: timerun REPORT COMMAND [ARGS...]\n");
    return 2;
  }
  struct timespec start, end;
  clock_gettime(CLOCK_MONOTONIC, &start);
  pid_t child = fork();
  if (child < 0) {
    perror("fork");
    return 2;
  }
  if (child == 0) {
    execvp(argv[2], argv + 2);
    perror(argv[2]);
    _exit(127);
  }
  int status = 0;
  struct rusage usage;
  if (wait4(child, &status, 0, &usage) < 0) {
    perror("wait4");
    return 2;
  }
  clock_gettime(CLOCK_MONOTONIC, &end);
  double wall = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
  int code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
  FILE *report = fopen(argv[1], "w");
  if (!report) {
    perror(argv[1]);
    return 2;
  }
  fprintf(report, "%.6f %.6f %.6f %ld %d\n", wall, seconds(usage.ru_utime), seconds(usage.ru_stime),
          usage.ru_maxrss, code);
  fclose(report);
  return 0;
}
