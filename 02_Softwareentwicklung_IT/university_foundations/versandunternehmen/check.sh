#!/usr/bin/env bash
# Check command: compile the untouched 2020 code with all warnings, then run the characterization tests.
# CC defaults to clang. Exit code 0 = build ok and all checks green.
set -euo pipefail
cd "$(dirname "$0")"
CC="${CC:-clang}"
mkdir -p build

# 1) Build the original program as it was (warnings are shown, not hidden; REVIEW-2026.md explains them).
#    Current clang turns the wrong pointer type (struct bestellung, REVIEW B8) into an error by default.
"$CC" -std=c11 -Wall -Wextra -Wno-error=incompatible-pointer-types -o build/versand original/*.c

# 2) Link the original modules (without its main) against the new tests and run them.
"$CC" -std=c11 -w -Wno-error=incompatible-pointer-types -Ioriginal -o build/test_original \
  tests/test_original.c original/functions.c original/functionsProdukt.c \
  original/funktionsKunden.c original/functionsBestellungen.c
(cd build && ./test_original)
