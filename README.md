# judecca

> Even worse than Malbolge.  When "[Oh no](https://github.com/BenWiederhake/ohno/)" just doesn't cover it.

"Judecca" is the innermost [circle of Hell](https://en.wikipedia.org/wiki/Inferno_(Dante)#Ninth_Circle_(Treachery)), according to Dante.
This makes it even more awful than [Malbolge](https://esolangs.org/wiki/Malbolge).
Also, Malbolge is probably a bounded-storage machine (i.e., a Turing
machine with arbitrary storage limits).  However, proving anything
non-trivial about Judecca feels a lot like a guarantee about psedo-preimages
on SHA256, since even very short [Universal Turing Machines](http://www.iwriteiam.nl/Ha_bf_Turing.html) look quite
[long in Brainfuck](http://www.hevanet.com/cristofd/brainfuck/utm.b).
At least, long when they have to be the output of a cryptographic hash function.
This project is inspired by the restrictions of [ohno](https://github.com/BenWiederhake/ohno/).

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Performance](#performance)
- [TODOs](#todos)
- [Contribute](#contribute)

## Background

### Execution, and Relation to Brainfuck

Here's how the language works:
* The "source code" is hashed as SHA256, the output is hashed again, that
  output is hashed again, etc.  The process continues until a total of
  2 million (2_000_000) calls to SHA256 have occurred.  The result is stored
  as the `seed`.  We impose an arbitrary upper bound of 2^60-1 bytes on the
  length of the source code, although this should be reasonably large.
  For example, the source code `Hello, world!` (no trailing newline) yields
  the following seed:

      bca503b85f045161cd38ea59980e2d87ddbaa85e755da324ac6da9f029668456

* Execution works much like Brainfuck.
* Supported instructions are the usual `+` (0x0), `-` (0x1), `<` (0x2),
  `>` (0x3), `[` (0x4), `]` (0x5), `.` (0x6), and `,` (0x7),
  as well as a few more:
  - `$` (0x8): In an implementation-defined way, provide an easy breakpoint.
  - `|` (0x9): If inside a loop, it behaves like `]`.  Otherwise, like `[`.
  - `%` (0xA): No-op.  In the future, there will be a breaking change to extend the language to [systemf](https://github.com/ajyoon/systemf), which could even be [done in python](https://stackoverflow.com/questions/37032203/make-syscall-in-python).
  The instructions 0xB through 0xF are currently no-op, and can be
  represented as `_`.  Future breaking changes may occur.
  A special note about `]`: If there is no loop that can be closed, it behaves
  as if there was a matching `[` at index zero.  So if the current cell is 0,
  continue; otherwise, jump back to position 0.
* The instructions are read from the "pages".  Execution starts at page 0.
  A page is computed by:

      page_pre = SHA256(seed + page_number + source_code)
      page = SHA256(page_pre + page_number + source_code)

  The `seed` comes from the initial computation.  Here, `+` is concatenation.
  The `page_number` is a little-endian integer of whatever length needed to
  represent it, rounded up to the next multiple of 8 bytes, and at least 8
  bytes.  So all pages between 0 and 2^64-1 inclusively get encoded
  "as usual". We impose an arbitrary upper bound of 256^(2^60-8-64)-1 on
  the number of pages to ensure that SHA256 is defined on the argument space,
  although it is ridiculously large (far beyond 10^120, the number of
  remaining computational steps in the observable universe).
  So this is how you get a page, which is obviously 256 bits long.
  Interpret each nibble (sequence of 4 bits) as an instruction according to
  the above table.  So it would interpret this:

      6D45EBAB781D6037F09DD80FF55958388B118810B506FC1D2E4F5CA058446E4F

  as this:

      .[____%[_%,|__%->___-$%_$>$.$+,_-$_]<>-_<_+$][_+-_$_|+__[><%_$%_

  which is equivalent to:

      .[[,|->->.+,-]<>-<+][+-|+[><

  which is probably about as useful as it looks.

### Brainfuck parameters

As Brainfuck is underspecified, here's the filled-in details:
* The tape is infinite in both directions and initialized to 0.
* The tape can hold values from 0 to 255, inclusively, and will wrap.
* You may stack parentheses arbitrarily deep.
* `,` (read) stores the current input byte on the tape. Good luck with doing
  anything Unicode-related.
* If `,` (read) encounters the end of stdin, then it writes 0 to the cell
  *before* of the current cell, and leaves the current cell untouched.
* There is no way to change this behavior.
* As the program tape is infinite by design, the only way to exit is by
  hitting some limits due to imperfections in the interpreter.
  This *might* change as soon as syscalls become possible, and the program
  can call exit.

### Design limitations

Furthermore, this implementation has some "limitations":
* The entire "source code" must fit into memory.  I strongly recommend
  against trying to "execute" `/dev/sda`.
* Even though parentheses stacks beyond 2^2048 are technically supported,
  python will probably choke around 2^32 parentheses in total, as it keeps
  a jump table at hand.
* During execution, only the first 2^64 pages may be accessed.  I dare you!
* Moving the read-write head beyond \[-2^30, 2^30\] probably exhausts your
  memory.
* To prevent being harmful, tape and pages are restricted in absolute value
  by 2^20, unless the environment value `JUDECCA_RUN_NOLIMIT` is set to 1.

### Design rationale

Design rationale:
* Some kind of initial slow-start is necessary to strongly discourage
  brute-force search for useful program.  Iterated SHA256 was preferred over
  PBKDF2 in order to limit the number of dependencies.  Also, the entire
  process must be deterministic.
* I want *all* files to be valid programs.  I also want to avoid short,
  obviously useless executions.
* I also want to avoid bullshit like running out of memory because randomly,
  the parenthesis stack exploded.  That's why there is a `|` instruction that
  drives the stack towards zero.
* I want this language to be *theoretically possible* to be extremely
  powerful.  Information theoretically speaking, it is *possible* that all
  kinds of instruction pages can be generated, with just a long enough
  "source code".  This is the main improvement over ohno, which has
  significantly less than 2^1600 programs, most of them crash wey too soon.
  This may sound large, but just consider the amount of programs that
  output some 1 KiB-sized text.
  The computation of `page_pre` can probably be made to compute any function
  in `page_number`.  This is repeated in the hope of making it more likely.
* I want this language to be incredibly hard to use for anything reasonable.
  "Hello, world!", FizzBuzz, cat, Truth Machine, all these are supposed to be
  unbelievably difficult to "write" – but still probably possible.
* Because it's Turing complete (I hope), this means there is a quine for it.
  However, I think finding a quine is probably still hard even if you
  replaced the hash function by MD5 and the initial iteration count by 1!
  I wonder how long this quine is.  Megabytes?  Gigabytes?
  The upper bound of 2^60-1 bytes on the source code is a rough approximation
  to the upper bound of around 2^61 bytes that can probably be handled by
  most SHA256 implementations.  Same for the number of pages.
* Have fun!  AHHH THE PAIN

## Install

There is nothing to install.  It's a stand-alone python program.

## Usage

Just use it!  No dependencies, and it's short enough.
The complexity lies in coming up with a design that works,
not in writing the code.

Just run it on your Judecca program:
`./run.py /path/to/your/program`

### Example programs

Here are some example programs written in Judecca:

- This Readme
- The python program itself
- `/dev/null`
- `/dev/zero`
- `/dev/sda`
- Literally any finite sequence of bytes, including the empty sequence.  Duh!

## Performance

I have little interest in making this performant,
since it doesn't execute any meaningful programs anyway.

## TODOs

* Implement the `%` instruction.
* Find and eliminate bottlenecks.  Maybe rewrite in Rust or whatever.
* Support passing arbitrary argv to Judecca.
* Support more invocation modes like printing the first few pages.  Some kind of interactivity would be nice.
* Maybe tamper with the randomness to prevent "boring" Brainfuck code like `[]`.  Of course, this can't be exhaustive.

## Contribute

Feel free to dive in! [Open an issue](https://github.com/BenWiederhake/judecca/issues/new) or submit PRs.
