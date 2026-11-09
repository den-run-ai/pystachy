#!/bin/sh
# usage: fetch.sh PREFIX < "RUN_ID URL" lines; saves logs/PREFIX-RUN_ID.zip
d=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time/logs
while read -r id url; do
  [ -n "$id" ] || continue
  out="$d/$1-$id.zip"
  [ -s "$out" ] && { echo "$id cached"; continue; }
  curl -sS -L --retry 2 -o "$out" -w "$id %{http_code} %{size_download}\n" "$url"
done
