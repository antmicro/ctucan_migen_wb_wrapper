import os
import tempfile

import cocotb
import cocotb_test
import cocotb_test.simulator
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from migen import *
from migen.fhdl import verilog
from ctucan import CTUCANWishboneWrapper
from ctucan.utils import collect_sources, convert_to_verilog

import cocotb_ctucan as cc
from common import get_test_output_dir


def bit_is_set(reg, bit):
    return True if (reg & (1 << bit)) > 0 else False


@cocotb.coroutine
async def reset(dut, reset_cycles):
    dut.sys_rst.setimmediatevalue(0)

    await ClockCycles(dut.sys_clk, num_cycles=reset_cycles)
    dut.sys_rst.value = 1
    await ClockCycles(dut.sys_clk, num_cycles=reset_cycles)
    dut.sys_rst.value = 0

    await RisingEdge(dut.sys_clk)


@cocotb.coroutine
async def ctucan_configure_timings(dut, wbs):
    BTR_VAL = 0x08233FEF  # CAN 2.0 125000 kbit/s
    BTR_FD_VAL = 0x0808A387  # CAN FD  500000 kbit/s
    TRV_DELAY_VAL = 0x01000000

    await cc.write_reg_32(dut, wbs, cc.BTR_OFFSET, BTR_VAL)
    await cc.write_reg_32(dut, wbs, cc.BTR_FD_OFFSET, BTR_FD_VAL)
    await cc.write_reg_32(dut, wbs, cc.TRV_DELAY_OFFSET, TRV_DELAY_VAL)


@cocotb.coroutine
async def ctucan_configure_irqs(dut, wbs):
    await cc.irq_mask_all(dut, wbs)

    await cc.irq_enable(dut, wbs, cc.INT_STAT_RXI_BIT)
    await cc.irq_enable(dut, wbs, cc.INT_STAT_TXI_BIT)
    await cc.irq_enable(dut, wbs, cc.INT_STAT_FCSI_BIT)

    await cc.irq_unmask(dut, wbs, cc.INT_STAT_RXI_BIT)
    await cc.irq_unmask(dut, wbs, cc.INT_STAT_TXI_BIT)
    await cc.irq_unmask(dut, wbs, cc.INT_STAT_FCSI_BIT)


@cocotb.coroutine
async def ctucan_check_irq(dut, wbs):
    stat_val = await cc.read_reg_16(dut, wbs, cc.INT_STAT_OFFSET)
    irq_nums = list()

    log_irq = lambda dut, name: dut._log.info(f'Active interrupt: {name}')

    if bit_is_set(stat_val, cc.INT_STAT_RXI_BIT):
        log_irq(dut, "RXI")
        irq_nums.append(0)

    if bit_is_set(stat_val, cc.INT_STAT_TXI_BIT):
        log_irq(dut, "TXI")
        irq_nums.append(1)

    if bit_is_set(stat_val, cc.INT_STAT_FCSI_BIT):
        log_irq(dut, "FCSI")
        irq_nums.append(4)

    return irq_nums


@cocotb.coroutine
async def ctucan_handle_fcsi_irq(dut, wbs):
    reg_val = await cc.read_reg_16(dut, wbs, cc.FAULT_STATE_OFFSET)
    if bit_is_set(reg_val, cc.FAULT_STATE_ERA_BIT):
        dut._log.info("ctucan is in bus-active state")

    if bit_is_set(reg_val, cc.FAULT_STATE_ERP_BIT):
        dut._log.info("ctucan is in bus-active state")

    if bit_is_set(reg_val, cc.FAULT_STATE_BOF_BIT):
        dut._log.info("ctucan is in bus-active state")


@cocotb.coroutine
async def ctucan_handle_irq(dut, wbs):
    while True:
        await RisingEdge(dut.irq)

        irq_bit_list = await ctucan_check_irq(dut, wbs)
        for irq_bit in irq_bit_list:
            if irq_bit == cc.INT_STAT_FCSI_BIT:
                await ctucan_handle_fcsi_irq(dut, wbs)
            elif irq_bit in [cc.INT_STAT_RXI_BIT, cc.INT_STAT_TXI_BIT]:
                await cc.irq_clear(dut, wbs, irq_bit)
                await ctucan_check_irq(dut, wbs)


@cocotb.coroutine
async def ctucan_configure(dut, wbs):
    irq_handler = cocotb.fork(ctucan_handle_irq(dut, wbs))

    await cc.disable(dut, wbs)
    disabled = await cc.is_disabled(dut, wbs)
    if not disabled:
        raise Exception("ctucan enabled, when it should be disabled")

    await ctucan_configure_irqs(dut, wbs)
    irq_bit_list = await ctucan_check_irq(dut, wbs)
    if irq_bit_list:
        raise Exception(f"irq list should be empty but is {irq_bit_list}")

    await ctucan_configure_timings(dut, wbs)
    await cc.enable_loop(dut, wbs)
    await cc.enable_selfack(dut, wbs)

    await cc.enable(dut, wbs)
    enabled = not await cc.is_disabled(dut, wbs)
    if not enabled:
        raise Exception("ctucan disabled, when it should be enabled")

    while True:
        initialized = await cc.is_initialized(dut, wbs)
        await ClockCycles(dut.sys_clk, num_cycles=100)  # busy wait
        if initialized:
            break

    return lambda: irq_handler.kill()


@cocotb.test()
async def can_fd_send_receive(dut):

    # constants
    CLK_PERIOD = 10  # 100MHz
    RESET_CYCLES = 10
    SEND_IDF = 0x123
    SEND_DATA = 0x1122334455667788
    SEND_WAIT_TIME = 100000

    # initialization
    cocotb.start_soon(Clock(dut.sys_clk, CLK_PERIOD, 'ns').start())
    wbs = cc.create_wb_master(dut, dut.sys_clk)
    await reset(dut, RESET_CYCLES)

    # configure ctucan
    await cc.reset(dut, wbs)
    finalize = await ctucan_configure(dut, wbs)

    # send and receive looped frame
    await cc.send_fd_frame(dut, wbs, SEND_DATA, SEND_IDF, brs=True)
    await ClockCycles(dut.sys_clk, num_cycles=SEND_WAIT_TIME)
    while True:
        empty = await cc.rx_empty(dut, wbs)
        await ClockCycles(dut.sys_clk, num_cycles=100)
        if not empty:
            break
    await cc.recv_frame(dut, wbs)

    # cleanup
    finalize()


def test_cocotb():
    TOP_LEVEL = "top_test"
    MODULE = "test_ctucan"
    VHDL_TOP_LEVEL = "can_top_level"
    VHDL_LIBRARY = "ctu_can_fd_rtl"
    WRAPPER_TOP_LEVEL = "CTUCAN"

    tests_dir = os.path.dirname(__file__)

    top_file = os.path.join(tests_dir, f"{TOP_LEVEL}.v")
    vhdl_dir = os.path.join(tests_dir, "..", "ctucan", "vhdl")
    vhdl_sources = collect_sources(vhdl_dir, ".vhd", absolute=True)

    output_dir = get_test_output_dir(__file__)
    output_sim_build = os.path.join(output_dir, "sim_build")
    output_ctucan_verilog = os.path.join(output_dir, f"{VHDL_TOP_LEVEL}.v")
    output_wrapper_file = os.path.join(output_dir, f"{WRAPPER_TOP_LEVEL}.v")

    os.makedirs(output_dir, exist_ok=True)

    with open(output_ctucan_verilog, "w") as ctucan_verilog, \
         open(output_wrapper_file, "w") as wrapper_file:

        # convert ctucan
        convert_to_verilog(
            vhdl_sources,
            output_ctucan_verilog,
            VHDL_TOP_LEVEL,
            library=VHDL_LIBRARY
        )

        # generate wishbone wrapper
        irq = Signal()
        can_rx = Signal()
        can_tx = Signal()
        ctucan_wb_wrapper = CTUCANWishboneWrapper(can_rx, can_tx, irq)
        wrapper = verilog.convert(
            ctucan_wb_wrapper,
            ctucan_wb_wrapper.get_ios(),
            name=WRAPPER_TOP_LEVEL
        )
        wrapper_file.write(str(wrapper))
        wrapper_file.flush()

        # run simulation
        verilog_sources = [
            output_ctucan_verilog, output_wrapper_file, top_file
        ]
        cocotb_test.simulator.run(
            python_search=[tests_dir],
            verilog_sources=verilog_sources,
            toplevel=TOP_LEVEL,
            module=MODULE,
            compile_args=["-g2005"],
            sim_build=output_sim_build,
            waves=True
        )
