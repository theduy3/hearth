Vendored from https://github.com/itopinion/zectrix-note4-epd-demo
(`components/zectrix_epd`, MIT, Copyright 2026 Zectrix Lab).

The Note4C fork replaces monochrome/grayscale initialization with the native
BWRY command sequence documented by the four-color reference at commit
8907e59300fde3b77a385dba9f3070b0de17b4c8, in
https://github.com/LazyYoun/youn-ink-fourcolor-firmware .
The replacement has exact packed-frame validation, bounded BUSY waits, and
power removal on every failure; host tests exercise the actual driver.
