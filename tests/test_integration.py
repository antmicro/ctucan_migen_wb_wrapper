#!/usr/bin/env python3

import os
import pytest
import tempfile

from migen import *
from migen.fhdl import verilog

from litex.soc.integration.builder import Builder, builder_argdict
from litex_boards.targets.digilent_arty import BaseSoC
from litex_boards.platforms import digilent_arty
from litex.build.generic_platform import Subsignal, Pins, IOStandard

from common import get_test_output_dir
from ctucan import CTUCAN, CTUCANWishboneWrapper


def can_io():
    return [(
        "can",
        0,
        Subsignal("rx", Pins("ck_io:ck_io0")),
        Subsignal("tx", Pins("ck_io:ck_io1")),
        IOStandard("LVCMOS33"),
    )]


@pytest.mark.parametrize("ctucan_variant", ["vhdl", "verilog"])
def test_litex(ctucan_variant):

    # create base SoC
    soc = BaseSoC(sys_clk_freq=int(100e6), integrated_rom_size=0x20000)

    # add ctucan ip-core
    soc.platform.add_extension(can_io())
    can_pads = soc.platform.request("can")
    soc.submodules.can = CTUCAN(soc.platform, can_pads, ctucan_variant)
    soc.add_memory_region("can", None, soc.can.wbwrapper.size, type=[])
    soc.add_wb_slave(soc.bus.regions["can"].origin, soc.can.wbwrapper.bus)
    soc.add_interrupt("can")

    # generate output
    output_dir = get_test_output_dir(__file__)
    builder = Builder(
        soc, output_dir, compile_gateware=False, compile_software=False
    )
    builder.build()


def test_migen():
    can_rx = Signal()
    can_tx = Signal()
    irq = Signal()
    ctucan_wb_wrapper = CTUCANWishboneWrapper(can_rx, can_tx, irq)
    verilog.convert(
        ctucan_wb_wrapper, ctucan_wb_wrapper.get_ios(), name="ctucan"
    )
