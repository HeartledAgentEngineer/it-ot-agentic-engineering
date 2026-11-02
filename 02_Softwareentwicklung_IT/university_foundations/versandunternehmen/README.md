# Mail-order company in C (university lab, 2020)

A console program for a small mail-order business: products, customers and orders, kept in **linked lists**, with
saving and loading of binary files. It comes from *Programmieren II* at HAW Hamburg (summer semester 2020).

**Who wrote what:** the lab sheets defined the features and the console output, not the code. The labs were done in a
team of two. This folder holds the later **linked-list version** — a rework beyond the assignment, which only asked
for an array of pointers. The code in [`original/`](original/) is unchanged since 2020 (German identifiers and
comments, Windows-1252).

**Shows:** `struct`s and pointers, `malloc`/`free`, linked lists (append, search, count, delete), binary file I/O
(`fopen`/`fwrite`/`fread`), splitting a program into modules with a shared header.

## Then and now

| 2020 | 2026 (new, in this folder) |
|---|---|
| Tested by typing into the menu | [`tests/test_original.c`](tests/test_original.c): 12 checks that call the original functions directly |
| Built in Visual Studio | [`check.sh`](check.sh): clang with all warnings, then the tests; exit code 0 = green |
| "It works" | [REVIEW-2026.md](REVIEW-2026.md): 11 bugs, each with its evidence (test, compiler warning, run or code reading) |

The tests **pin the 2020 behaviour** — including two bugs — rather than fixing it: a test named `bug_…` passes while
the bug is still there. The point of this folder is the honest before-and-after, not a polished program.

## Run it

```bash
CC=clang bash check.sh     # builds original/, runs the characterization tests
```

Needs clang (or another C11 compiler that knows `scanf_s`, e.g. MSVC or llvm-mingw on Windows).
