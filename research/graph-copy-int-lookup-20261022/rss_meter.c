#define _GNU_SOURCE
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
int main(int argc,char **argv) {
  if(argc<2)return 2;
  pid_t pid=fork(); if(pid<0)return 3;
  if(!pid){execvp(argv[1],argv+1);perror("execvp");_exit(127);}
  int status;struct rusage ru;
  while(wait4(pid,&status,0,&ru)<0){if(errno!=EINTR)return 4;}
  fprintf(stderr,"\nWATCH_RSS_KIB %ld CPU_S %.9f\n",ru.ru_maxrss,
    ru.ru_utime.tv_sec+ru.ru_stime.tv_sec+(ru.ru_utime.tv_usec+ru.ru_stime.tv_usec)/1e6);
  if(WIFEXITED(status))return WEXITSTATUS(status);
  return 128+WTERMSIG(status);
}
