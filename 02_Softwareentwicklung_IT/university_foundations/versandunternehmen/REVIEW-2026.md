# Review 2026 of my 2020 student code

In 2020 this program "worked" when I typed into it by hand. Reading it again six years later — with compiler
warnings switched on and with tests — shows what it really does. Every finding names its evidence:

- **test** — pinned by a check in [`tests/test_original.c`](tests/test_original.c) (run by `check.sh`)
- **clang** — reported by `clang -Wall -Wextra` on the untouched code
- **run** — observed by running the program
- **reading** — found by reading the code; not executed, because it would hang or crash

The code in [`original/`](original/) is not changed. Line numbers refer to it.

## Bugs

| # | Where | What happens | Evidence |
|---|---|---|---|
| B1 | `functionsProdukt.c:137`, `funktionsKunden.c:47` | The lookup loops `do { … } while (pAct->pNext)` but never moves `pAct` forward. If the first element does not match and there is a second one, it loops forever — e.g. entering a new product number once two products exist. | reading |
| B2 | `functionsProdukt.c:319`, `funktionsKunden.c:146` | `while (fread(…));` — the `;` ends the loop. All records are read into one buffer, and only **one** element is added to the list. | clang `-Wempty-body`, test `bug_B2` |
| B3 | `functionsProdukt.c:225` | Search by name: `break;` stands before the check of the last element, so the last product is never found by name. | test `bug_B3` |
| B4 | `functionsProdukt.c:314`, `funktionsKunden.c:141` | The "open file" functions build the list but never `return` it — the caller gets an undefined value. | clang `-Wreturn-type` |
| B5 | `functionsBestellungen.c:52` | Listing a customer's orders moves to the next order only when the current one matches: an order of another customer ends in an endless loop. The last order is never visited, and an empty order list dereferences `NULL`. | reading |
| B6 | `functionsProdukt.c:294` + `:279`, `funktionsKunden.c:121` + `:106` | The write function closes the file, then the caller closes it again — closing a file twice is undefined behaviour. | reading |
| B7 | `functionsProdukt.c:197` | Missing braces after `else`: `pAct = NULL;` always runs, so the search shows only the first hit, although the comment promises all hits. | clang `-Wmisleading-indentation` |
| B8 | `versand_Header.h:38` | The order struct points to `struct bestellung`, a type that does not exist (the struct is called `Bestelllung`). It compiled in Visual Studio in 2020; current clang rejects it by default. | clang `-Wincompatible-pointer-types` |
| B9 | `functionsBestellungen.c:4`, `:28` | A new order's `pNext` is never set, so walking the order list reads garbage. When stock is too low, `pE = NULL; free(pE);` frees nothing — the memory leaks. | reading |
| B10 | `Versandunternehmen.c:127`, `functions.c:28`, every `scanf` | `rewind(stdin)` is not defined for keyboard input, and no `scanf` return value is checked. With piped input the program loses the rest of the input and repeats the menu endlessly (346,379 times in 10 s). | run |
| B11 | `funktionsKunden.c:36–37` | `scanf("%s", …)` without a width: a name longer than 29 characters overwrites memory. | reading |

## Gaps against the assignment

- Menu 8 / 9, option `c` (save and load orders) is empty (`Versandunternehmen.c:142`, `:168`) — the lab sheet asked
  for it.
- `fwrite` stores whole structs including their pointer fields (`functionsProdukt.c:291`); the file format depends on
  compiler and platform.
- No `malloc` result is checked; prices are compared with `==` on `double`.

## What I would do today

1. **Tests first.** Every bug above would have shown up with three or four small tests — the ones in this folder took
   less time than finding the bugs by hand.
2. **Separate logic from input.** The list functions should not call `scanf` themselves; then they can be tested
   without a keyboard (that is exactly what the tests here had to work around).
3. **Warnings as errors** (`-Wall -Wextra -Werror`). Four of the eleven bugs are reported by the compiler.
4. **One generic list** instead of three copies for products, customers and orders — B1 and B2 exist twice because
   the code was copied.
5. **A text format** (CSV) instead of raw structs, with a version line.

This is the lesson of the whole portfolio in small: the code was not the hard part; making it *verifiable* was.
