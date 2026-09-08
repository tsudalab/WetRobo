#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 INPUT {left|right} OUTPUT" >&2
  exit 2
fi

input=$1
direction=$2
output=$3

case "$direction" in
  left) degrees=-90 ;;
  right) degrees=90 ;;
  *) echo "direction must be left or right" >&2; exit 2 ;;
esac

convert "$input" -rotate "$degrees" "$output"
