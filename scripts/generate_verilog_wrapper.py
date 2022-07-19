#!/usr/bin/env python3

from migen import *
from migen.fhdl import verilog

from ctucan import CTUCANWishboneWrapper

irq = Signal()
can_rx = Signal()
can_tx = Signal()

wb_wrapper = CTUCANWishboneWrapper(can_rx, can_tx, irq)
verilog_src = verilog.convert(wb_wrapper, wb_wrapper.get_ios(), name="CTUCAN")
print(verilog_src)
