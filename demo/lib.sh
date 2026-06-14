#!/usr/bin/env bash
# Shared helpers for mltrack asciinema demos.
#
# Recordings run against an ISOLATED database under a temp HOME so they never
# touch (or expose) the user's real ~/.mltrack inventory. Re-record any demo with:
#   rm -f demo/<name>.cast && asciinema rec -i 2 -c "bash demo/<name>.sh" demo/<name>.cast
#   agg --cols 110 --rows 32 demo/<name>.cast demo/<name>.gif

export HOME="/tmp/mltrack-demo-home"
mkdir -p "$HOME/.mltrack"
export PATH="/usr/local/bin:$PATH"
export COLUMNS=110
export LINES=32
export TERM=xterm-256color
export FORCE_COLOR=1

C_PROMPT='\033[1;36m'   # cyan
C_CMD='\033[1m'         # bold
C_SAY='\033[1;33m'      # yellow
C_RST='\033[0m'

# A spoken-aside comment line.
say() {
  printf "${C_SAY}# %s${C_RST}\n" "$1"
  sleep 1.1
}

# Print a prompt + command, pause, then run it.
run() {
  printf "${C_PROMPT}\xe2\x9d\xaf${C_RST} ${C_CMD}%s${C_RST}\n" "$1"
  sleep 0.7
  eval "$1"
  echo
  sleep 1.6
}

# Opening title line.
banner() {
  printf "\n${C_PROMPT}%s${C_RST}\n\n" "$1"
  sleep 0.9
}
