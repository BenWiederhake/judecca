#!/usr/bin/env python3

import hashlib
import os
import struct
import sys


PAGE_SIZE = 256 // 4  # digest_size / bits_per_instruction
SEED_HASH_ITERATIONS = 2_000_000
PAGE_NUMBER_FORMAT = '<Q'  # Little endian unsigned 64-bit
RESTRICTION_ENV_VAR = b'JUDECCA_RUN_NOLIMIT'
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
        elif insn == '8':  # '$'
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
