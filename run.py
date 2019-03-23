#!/usr/bin/env python3

# "Judecca" is the innermost circle of Hell [1], according to Dante.
# This makes it even more awful than Malbolge [2].
# Also, Malbolge is probably a bounded-storage machine (i.e., a Turing
# machine with arbitrary storage limits).  However, proving anything
# non-trivial about Judecca feels a lot like a guarantee about psedo-preimages
# on SHA256, since even the shortest Universal Turing Machines look quite
# long [3] [4] in Brainfuck.
# This project is inspired by the restrictions of ohno [5].

# [1] https://en.wikipedia.org/wiki/Inferno_(Dante)#Ninth_Circle_(Treachery)
# [2] https://esolangs.org/wiki/Malbolge
# [3] http://www.iwriteiam.nl/Ha_bf_Turing.html
# [4] http://www.hevanet.com/cristofd/brainfuck/utm.b
# [5] https://github.com/BenWiederhake/ohno/

# Here's how the language works:
# * The "source code" is hashed as SHA256, the output is hashed again, that
#   output is hashed again, etc.  The process continues until a total of
#   2 million (2_000_000) calls to SHA256 have occurred.  The result is stored
#   as the `seed`.  We impose an arbitrary upper bound of 2^60-1 bytes on the
#   length of the source code, although this should be reasonably large.
#   For example, the source code `Hello, world!` (no trailing newline) yields
#   the following seed:
#       bca503b85f045161cd38ea59980e2d87ddbaa85e755da324ac6da9f029668456
# * Execution works much like Brainfuck.
# * Supported instructions are the usual `+` (0x0), `-` (0x1), `<` (0x2),
#   `>` (0x3), `[` (0x4), `]` (0x5), `.` (0x6), and `,` (0x7),
#   as well as a few more:
#   `$` (0x8): In an implementation-defined way, provide an easy breakpoint.
#   `|` (0x9): If inside a loop, it behaves like `]`.  Otherwise, like `[`.
#   `%` (0xA): No-op.  In the future, there will be a breaking change to extend
#              the language to systemf [6] [7].
#   The instructions 0xB through 0xF are currently no-op, and can be
#   represented as `_`.  Future breaking changes may occur.
#   A special note about `]`: If there is no loop that can be closed, it behaves
#   as if there was a matching `[` at index zero.  So if the current cell is 0,
#   continue; otherwise, jump back to position 0.
# * The instructions are read from the "pages".  Execution starts at page 0.
#   A page is computed by:
#       page_pre = SHA256(seed + page_number + source_code)
#       page = SHA256(page_pre + page_number + source_code)
#   The `seed` comes from the initial computation.  Here, `+` is concatenation.
#   The `page_number` is a little-endian integer of whatever length needed to
#   represent it, rounded up to the next multiple of 8 bytes, and at least 8
#   bytes.  So all pages between 0 and 2^64-1 inclusively get encoded
#   "as usual". We impose an arbitrary upper bound of 256^(2^60-8-64)-1 on
#   the number of pages to ensure that SHA256 is defined on the argument space,
#   although it is ridiculously large (far beyond 10^120, the number of
#   remaining computational steps in the observable universe).
#   So this is how you get a page, which is obviously 256 bits long.
#   Interpret each nibble (sequence of 4 bits) as an instruction according to
#   the above table.  So it would interpret this:
#       6D45EBAB781D6037F09DD80FF55958388B118810B506FC1D2E4F5CA058446E4F
#   as this:
#       .[____%[_%,|__%->___-$%_$>$.$+,_-$_]<>-_<_+$][_+-_$_|+__[><%_$%_
#   which is equivalent to:
#       .[[,|->->.+,-]<>-<+][+-|+[><
#   which is probably about as useful as it looks.

# [6] https://github.com/ajyoon/systemf
# [7] https://stackoverflow.com/questions/37032203/make-syscall-in-python

# As Brainfuck is underspecified, here's the filled-in details:
# * The tape is infinite in both directions and initialized to 0.
# * The tape can hold values from 0 to 255, inclusively, and will wrap.
# * You may stack parentheses arbitrarily deep.
# * `,` (read) stores the current input byte on the tape. Good luck with doing
#   anything Unicode-related.
# * If `,` (read) encounters the end of stdin, then it writes 0 to the cell
#   *before* of the current cell, and leaves the current cell untouched.
# * There is no way to change this behavior.
# * As the program tape is infinite by design, the only way to exit is by
#   hitting some limits due to imperfections in the interpreter.
#   This *might* change as soon as syscalls become possible, and the program
#   can call exit.

# Furthermore, this implementation has some "limitations":
# * The entire "source code" must fit into memory.  I strongly recommend
#   against trying to "execute" /dev/sda.
# * Even though parentheses stacks beyond 2^2048 are technically supported,
#   python will probably choke around 2^32 parentheses in total, as it keeps
#   a jump table at hand.
# * During execution, only the first 2^64 pages may be accessed.  I dare you!
# * Moving the read-write head beyond [-2^30, 2^30] probably exhausts your
#   memory.
# * To prevent being harmful, tape and pages are restricted in absolute value
#   by 2^20, unless the environment value "JUDECCA_RUN_NOLIMIT" is set to 1.

# Design rationale:
# * Some kind of initial slow-start is necessary to strongly discourage
#   brute-force search for useful program.  Iterated SHA256 was preferred over
#   PBKDF2 in order to limit the number of dependencies.  Also, the entire
#   process must be deterministic.
# * I want *all* files to be valid programs.  I also want to avoid short,
#   obviously useless executions.
# * I also want to avoid bullshit like running out of memory because randomly,
#   the parenthesis stack exploded.  That's why there is a `|` instruction that
#   drives the stack towards zero.
# * I want this language to be *theoretically possible* to be extremely
#   powerful.  Information theoretically speaking, it is *possible* that all
#   kinds of instruction pages can be generated, with just a long enough
#   "source code".  This is the main improvement over ohno, which has
#   significantly less than 2^1600 programs, most of them crash wey too soon.
#   This may sound large, but just consider the amount of programs that
#   output some 1 KiB-sized text.
#   The computation of `page_pre` can probably be made to compute any function
#   in `page_number`.  This is repeated in the hope of making it more likely.
# * I want this language to be incredibly hard to use for anything reasonable.
#   "Hello, world!", FizzBuzz, cat, Truth Machine, all these are supposed to be
#   unbelievably difficult to "write" – but still probably possible.
# * Because it's Turing complete (I hope), this means there is a quine for it.
#   However, I think finding a quine is probably still hard even if you
#   replaced the hash function by MD5 and the initial iteration count by 1!
#   I wonder how long this quine is.  Megabytes?  Gigabytes?
#   The upper bound of 2^60-1 bytes on the source code is a rough approximation
#   to the upper bound of around 2^61 bytes that can probably be handled by
#   most SHA256 implementations.  Same for the number of pages.
# * Have fun!  AHHH THE PAIN

# TODO:
# * Implement the `%` instruction.
# * Find and eliminate bottlenecks.  Maybe rewrite in Rust or whatever.
# * Support passing arbitrary argv to Judecca.
# * Support more invocation modes like printing the first few pages.


import hashlib
import os
import struct
import sys


PAGE_SIZE = 256 // 4  # digest_size / bits_per_instruction  # FIXME ahh shit.
SEED_HASH_ITERATIONS = 2_000_000
PAGE_NUMBER_FORMAT = '<Q'  # Little endian unsigned 64-bit
RESTRICTION_ENV_VAR = b'JUDECCA_RUN_NOLIMIT'  # Bytes!
RESTRICTION_MAXPAGE = 2**20
RESTRICTION_MAXTAPE = 2**20
DEBUG_JUDECCA = False


def compute_seed(source_code):
    seed = source_code
    for _ in range(SEED_HASH_ITERATIONS):
        seed = hashlib.sha256(seed).digest()
    # E.g. the hexstring bca503b85f…
    return seed


def get_page(source_code, seed, page_number):
    page_num_bytes = struct.pack(PAGE_NUMBER_FORMAT, page_number)

    h = hashlib.sha256(seed)
    h.update(page_num_bytes)
    h.update(source_code)
    page_pre = h.digest()

    h = hashlib.sha256(page_pre)
    h.update(page_num_bytes)
    h.update(source_code)
    page = h.digest()
    
    return page  # E.g., the hexstring 315f5bdb…


def as_instructions(page):
    # Silly, but totally sufficient.
    return page.hex().upper()


# * Supported instructions are the usual `+` (0x0), `-` (0x1), `<` (0x2),
#   `>` (0x3), `[` (0x4), `]` (0x5), `.` (0x6), and `,` (0x7),
#   as well as a few more:
#   `$` (0x8): In an implementation-defined way, provide an easy breakpoint.
#   `|` (0x9): If inside a loop, it behaves like `]`.  Otherwise, like `[`.
#   `%` (0xA): No-op.  In the future, there will be a breaking change to extend
#              the language to systemf [6] [7].


def prettify_instructions(insns, strip=True):
    substitutions = [('0', '+'), ('1', '-'), ('2', '<'), ('3', '>'),
                     ('4', '['), ('5', ']'), ('6', '.'), ('7', ','),
                     ('8', '$'), ('9', '|'), ('A', '%'), ('B', '_'),
                     ('C', '_'), ('D', '_'), ('E', '_'), ('F', '_')]
    for (old, new) in substitutions:
        insns = insns.replace(old, new)
    if strip:
        insns = insns.replace('_', '')
        insns = insns.replace('%', '')
        insns = insns.replace('$', '')
    return insns


class PageCache:
    def __init__(self, source_code, seed, nolimit=False):
        self.source_code = source_code
        self.seed = seed
        self.ip = 0
        self.nolimit = nolimit
        self.latest_page_num = None
        self.latest_instructions = 'INSTRUCTIONS_GO_HERE'

    def get_instructions(self, page_num):
        if self.latest_page_num != page_num:
            if not self.nolimit and page_num > RESTRICTION_MAXPAGE:
                print('Limit exceeded: tried to access page {}'.format(page_num),
                      file=sys.stderr)
                exit(2)
            self.latest_page_num = page_num
            page = get_page(self.source_code, self.seed, page_num)
            self.latest_instructions = as_instructions(page)
        return self.latest_instructions


class JumpTable:
    def __init__(self, page_cache):
        self.page_cache = page_cache
        self.progress_maxpage = -1
        self.progress_open = []
        self.mapping = dict()  # TODO: Can be done more efficiently!

    def get_jump_dest(self, insn_num, is_head_zero):
        insn_page_num = insn_num // PAGE_SIZE

        # Read until instruction is encountered:
        while self.progress_maxpage < insn_page_num:
            # Can't happen during normal execution,
            # but I want to be able to use it standalone, too.
            self.extend()

        # Return if already determined:
        # Note that dest == insn_num can occur in the case of `[]`.
        dest = self.mapping[insn_num]
        is_determined = dest != -1
        jmp_fwd = dest > insn_num or not is_determined
        if jmp_fwd and not is_head_zero:
            return insn_num + 1
        elif jmp_fwd and is_head_zero and is_determined:
            return dest
        elif jmp_fwd and is_head_zero and not is_determined:
            # See below.
            pass
        elif not jmp_fwd and not is_head_zero:
            return dest
        elif not jmp_fwd and is_head_zero:
            return insn_num + 1
        else:
            raise AssertionError('Jump table encountered bullshit.')
        assert jmp_fwd and is_head_zero and not is_determined
        del is_determined

        # Read until determined:
        while dest == -1:
            assert bool(self.progress_open)
            self.extend()
            dest = self.mapping[insn_num]
        return dest

    def extend(self):
        self.progress_maxpage += 1
        insn_page = self.page_cache.get_instructions(self.progress_maxpage)
        frame = self.progress_maxpage * PAGE_SIZE
        for (offset, insn) in enumerate(insn_page):
            if insn == '9':  # '|' (simplify)
                if bool(self.progress_open):
                    insn = '5'  # ']'
                else:
                    insn = '4'  # '['
            if insn == '4':  # '['
                self.progress_open.append(frame + offset + 1)
                self.mapping[frame + offset] = -1
            elif insn == '5' and bool(self.progress_open):  # ']' (matched)
                dest = self.progress_open.pop()
                self.mapping[frame + offset] = dest
                assert self.mapping[dest - 1] == -1
                self.mapping[dest - 1] = frame + offset + 1
            elif insn == '5':  # ']' (unmatched)
                assert not bool(self.progress_open)
                self.mapping[frame + offset] = 0


def judecca_debugging_break():
    pass  # Inspired by `BF_DEBUGGING_BREAK` in systemf.


class IODev:
    def write_byte(self, the_byte):
        '''
        Given a bytestring of length 1, output that byte.
        '''
        raise NotImplementedError()

    def read_byte(self):
        '''
        Returns a bytestring of length 0 or 1.
        A length of 0 indicates end of file.
        '''
        raise NotImplementedError()


class DefaultIODev:
    def write_byte(self, the_byte):
        written = os.write(1, the_byte)
        assert written == 1

    def read_byte(self):
        the_bytes = os.read(0, 1)
        assert len(the_bytes) <= 1
        return the_bytes


class DummyIODev:
    def write_byte(self, the_byte):
        pass

    def read_byte(self):
        return b'?'


class Machine:
    def __init__(self, source_code, seed, nolimit=False, iodev=None):
        self.ip = 0
        self.nolimit = nolimit
        self.tape_before = bytearray(1)
        self.tape_after_rev = bytearray(1)
        # Invariant: Both lists are non-empty.
        self.page_cache = PageCache(source_code, seed, nolimit)
        self.jump_table = JumpTable(self.page_cache)
        if iodev is None:
            if DEBUG_JUDECCA:
                iodev = DummyIODev()
            else:
                iodev = DefaultIODev()
        self.iodev = iodev

    def step(self):
        page_num = self.ip // PAGE_SIZE
        insn_page = self.page_cache.get_instructions(page_num)
        insn = insn_page[self.ip % PAGE_SIZE]
        if insn in '459':  # '[]|'
            is_head_zero = self.tape_after_rev[-1] == 0
            self.ip = self.jump_table.get_jump_dest(self.ip, is_head_zero)
            return
        if insn in 'ABCDEF':  # '%_____'
            pass
        elif insn in '01':  # '+-'
            newval = self.tape_after_rev[-1] + 2 * (insn == '0') - 1
            self.tape_after_rev[-1] = newval & 0xFF
        elif insn in '23':  # '<>'
            if insn == '2':
                mv_from = self.tape_before
                mv_to = self.tape_after_rev
            else:
                mv_from = self.tape_before
                mv_to = self.tape_after_rev
            mv_to.append(mv_from.pop())
            if not bool(mv_from):
                if not self.nolimit and len(mv_from) >= RESTRICTION_MAXTAPE:
                    print('Limit exceeded: tried to extend to {}'.format(len(mv_from) + 1),
                          file=sys.stderr)
                    exit(2)
                mv_from.append(0)
        elif insn == '6':  # '.'
            if DEBUG_JUDECCA:
                print('out', self.tape_after_rev[-1:])
            self.iodev.write_byte(self.tape_after_rev[-1:])
        elif insn == '7':  # ','
            the_bytes = self.iodev.read_byte()
            if DEBUG_JUDECCA:
                print('in', the_bytes)
            if len(the_bytes) == 1:
                self.tape_after_rev[-1] = the_bytes[0]
            elif len(the_bytes) == 0:
                # Recall: Invariant: Both sides of the tape are non-empty.
                self.tape_after_rev[-1] = 0
            else:
                raise AssertionError('Tried to read 1 byte, read {} instead?!'.format(len(the_bytes)))
        elif insn == '8':  # '('
            judecca_debugging_break()
        else:
            raise AssertionError('Illegal instruction encountered?! "{}"'.format(insn))

        self.ip += 1


def run_machine(source_code, nolimit=False):
    seed = compute_seed(source_code)
    m = Machine(source_code, seed, nolimit, iodev=DefaultIODev())
    if DEBUG_JUDECCA:
        # Print the first few "pages" to be nice.
        for i in range(10):
            print(prettify_instructions(m.page_cache.get_instructions(i)))
    while True:
        m.step()


def run_arbitrary(argv, nolimit=False):
    if len(argv) != 2:
        print('Cannot handle multi-arguments (yet?)', file=sys.stderr)
        exit(1)
    with open(argv[1], 'rb') as fp:
        source_code = fp.read()  # Let's hope it's not too large
    run_machine(source_code, nolimit)


if __name__ == '__main__':
    run_arbitrary(sys.argv or [__file__],
                  os.environb.get(RESTRICTION_ENV_VAR) == b'1')
