#!/usr/bin/env python3
"""Pack Android boot image, header v0. Verified byte-identical round-trip
against reference 6.16.7_boot.img (up to logical end; trailing zero pad optional).

Usage:
  pack_bootimg.py --kernel K --ramdisk R --cmdline "..." --output boot.img
Optional addr overrides via env not needed; defaults match reference image:
  kernel_addr=0x8000 ramdisk_addr=0x1000000 second_addr=0xf00000 tags_addr=0x100
"""
import argparse, hashlib, struct, sys

def align(n, page):
    return (n + page - 1) // page * page

def pack(kernel_path, ramdisk_path, cmdline, out_path,
         page_size=4096, kernel_addr=0x00008000, ramdisk_addr=0x01000000,
         second_addr=0x00f00000, tags_addr=0x00000100, pad_to=0):
    kernel = open(kernel_path, 'rb').read()
    ramdisk = open(ramdisk_path, 'rb').read()
    second = b''
    dt = b''

    hdr = bytearray(1632)
    hdr[0:8] = b'ANDROID!'
    struct.pack_into('<10I', hdr, 8,
                     len(kernel), kernel_addr,
                     len(ramdisk), ramdisk_addr,
                     0, second_addr,
                     tags_addr, page_size,
                     0, 0)  # dt_size, unused
    # name[16] stays zero
    cb = cmdline.encode()
    if len(cb) > 512:
        sys.exit('cmdline too long for v0 header (512)')
    hdr[64:64 + len(cb)] = cb
    # id[8] stays zero to match reference image byte-for-byte
    # extra_cmdline[1024] stays zero

    out = bytearray()
    out += hdr
    out += b'\0' * (align(len(out), page_size) - len(out))
    out += kernel
    out += b'\0' * (align(len(out), page_size) - len(out))
    out += ramdisk
    out += b'\0' * (align(len(out), page_size) - len(out))
    if pad_to and len(out) < pad_to:
        out += b'\0' * (pad_to - len(out))
    open(out_path, 'wb').write(out)
    print(f'wrote {out_path}: {len(out)} bytes (kernel {len(kernel)}, ramdisk {len(ramdisk)})')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--kernel', required=True)
    ap.add_argument('--ramdisk', required=True)
    ap.add_argument('--cmdline', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--pad-to', type=int, default=0)
    a = ap.parse_args()
    pack(a.kernel, a.ramdisk, a.cmdline, a.output, pad_to=a.pad_to)
