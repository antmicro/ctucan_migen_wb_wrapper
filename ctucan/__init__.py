#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2022 Antmicro
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os

from migen import *
from migen.fhdl import verilog

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr_eventmanager import *
from ctucan.utils import collect_sources, convert_to_verilog

__all__ = ["CTUCAN", "CTUCANWishboneWrapper"]

CORE_VARIANTS = ["vhdl", "verilog", "external"]


def all_ones(signal_width):
    return 2**(signal_width) - 1


class DummyEventManager(Module):

    def __init__(self):
        self.irq = Signal()


class CTUCANWishboneWrapper(Module):

    def __init__(self, can_rx, can_tx, irq):

        # IOs
        self.bus = wishbone.Interface(data_width=32, adr_width=14)
        self.timestamp = Signal(64, reset=all_ones(64))
        self.can_rx = can_rx
        self.can_tx = can_tx
        self.irq = irq

        # parameters

        # The CTU CAN IP-core uses byte addressing, while the Wishbone bus uses
        # word addressing. As a consequence, the two least significant bits
        # of the core's address line are unused to make the two addressing
        # patterns conformant.

        ALIGNMENT_BITS = 2
        self.size = 2**(self.bus.adr_width + ALIGNMENT_BITS)

        bus_rd = Signal()
        bus_wr = Signal()
        bus_cs = Signal()
        bus_adr = Signal(self.bus.adr_width + ALIGNMENT_BITS)

        self.comb += [
            bus_cs.eq(self.bus.cyc & self.bus.stb),
            bus_rd.eq(bus_cs & ~self.bus.we & ~self.bus.ack),
            bus_wr.eq(bus_cs & self.bus.we),
            bus_adr.eq(Cat(0, 0, self.bus.adr)),
        ]

        self.sync += [
            self.bus.ack.eq(0),
            If(bus_cs & ~self.bus.ack, self.bus.ack.eq(1)),
        ]

        # CAN controller instance
        self.specials += Instance(
            "can_top_level",
            i_clk_sys=ClockSignal("sys"),
            i_res_n=~ResetSignal("sys"),
            i_data_in=self.bus.dat_w,
            i_adress=bus_adr,
            i_scs=bus_cs,
            i_srd=bus_rd,
            i_swr=bus_wr,
            i_sbe=self.bus.sel,
            i_can_rx=can_rx,
            i_timestamp=self.timestamp,
            o_data_out=self.bus.dat_r,
            o_int=irq,
            o_can_tx=can_tx,
        )

    def get_ios(self):
        return {
            self.bus.adr,
            self.bus.dat_w,
            self.bus.dat_r,
            self.bus.sel,
            self.bus.cyc,
            self.bus.stb,
            self.bus.ack,
            self.bus.we,
            self.can_rx,
            self.can_tx,
            self.irq
        }


class CTUCAN(Module):

    def __init__(self, platform, pads, variant="vhdl"):
        if variant not in CORE_VARIANTS:
            raise Exception("Unsupported core variant")

        self.platform = platform
        self.variant = variant

        self.submodules.ev = DummyEventManager()
        self.submodules.wbwrapper = CTUCANWishboneWrapper(
            pads.rx, pads.tx, self.ev.irq
        )

    def add_sources(self, copy=False):
        cdir = os.path.dirname(__file__)
        sources_path = os.path.join(cdir, "vhdl")
        top_module = "can_top_level"
        library = "ctu_can_fd_rtl"

        vhdl_sources = collect_sources(sources_path, ".vhd")
        if self.variant == "vhdl":
            for f in vhdl_sources:
                self.platform.add_source(f, library=library, copy=copy)

        elif self.variant == "verilog":
            gen_dir = os.path.join(cdir, "generated")
            if not os.path.exists(gen_dir):
                os.mkdir(gen_dir)
            output_file = os.path.join(gen_dir, f"{top_module}.v")
            convert_to_verilog(
                vhdl_sources,
                output_file,
                top_module=top_module,
                library=library
            )
            self.platform.add_source(output_file, copy=copy)

    def do_finalize(self):
        self.add_sources()
