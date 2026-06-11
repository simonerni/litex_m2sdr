#
# This file is part of LiteX-M2SDR.
#
# Copyright (c) 2024-2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

# AD9361 PRBS Generator ----------------------------------------------------------------------------

class AD9361PRBSGenerator(LiteXModule):
    def __init__(self, seed=0x0a54):
        self.ce = Signal(reset=1)
        self.o  = Signal(16)

        # # #

        # PRBS Generation.
        data = Signal(16, reset=seed)
        self.sync += If(self.ce, data.eq(Cat((
            data[1]  ^ data[2]  ^ data[4]  ^ data[5]  ^
            data[6]  ^ data[7]  ^ data[8]  ^ data[9]  ^
            data[10] ^ data[11] ^ data[12] ^ data[13] ^
            data[14] ^ data[15]),
            data[:-1]
            )
        ))
        self.comb += self.o.eq(data)

# AD9361 PRBS Checker ----------------------------------------------------------------------------

class AD9361PRBSChecker(LiteXModule):
    def __init__(self, seed=0x0a54):
        self.ce     = Signal(reset=1)
        self.i      = Signal(12)
        self.synced = Signal()

        # # #

        # Input registration: the input data comes from the PHY RX mux; registering it (and ce)
        # keeps the compare/re-seed cone off the PHY critical path at high DATA_CLK rates
        # (491.52MHz with Oversampling).
        i_r  = Signal(12)
        ce_r = Signal()
        self.sync += [
            ce_r.eq(self.ce),
            If(self.ce, i_r.eq(self.i)),
        ]

        error = Signal()

        # # #

        # PRBS reference.
        prbs = AD9361PRBSGenerator(seed=seed)
        prbs = ResetInserter()(prbs)
        self.submodules += prbs

        # PRBS re-synchronization.
        self.comb += prbs.ce.eq(ce_r)
        self.comb += prbs.reset.eq(error)

        # Error generation (two registered stages: XOR then reduce, to close timing at high
        # DATA_CLK rates; the reference re-seeds two cycles after a mismatch, the checker still
        # self-locks by repeated re-seeding until the compare matches).
        diff  = Signal(12)
        ce_rr = Signal()
        self.sync += [
            diff.eq(i_r ^ prbs.o[:12]),
            ce_rr.eq(ce_r),
            error.eq(ce_rr & (diff != 0)),
        ]


        # Sync generation.
        self.sync_timer = WaitTimer(1024)
        self.comb += self.sync_timer.wait.eq(~error)
        self.comb += self.synced.eq(self.sync_timer.done)
