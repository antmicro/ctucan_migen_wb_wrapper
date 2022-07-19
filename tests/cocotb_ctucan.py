import cocotb

from enum import Enum
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.wishbone.driver import WishboneMaster
from cocotbext.wishbone.driver import WBOp

DEVICE_ID_OFFSET = 0x0
VERSION_OFFSET = 0x2
MODE_OFFSET = 0x4
SETTINGS_OFFSET = 0x6
INT_STAT_OFFSET = 0x10
INT_ENA_SET_OFFSET = 0x14
INT_ENA_CLR_OFFSET = 0x18
INT_MASK_SET_OFFSET = 0x1C
INT_MASK_CLR_OFFSET = 0x20
BTR_OFFSET = 0x24
BTR_FD_OFFSET = 0x28
RX_DATA_OFFSET = 0x6C
RX_STATUS_OFFSET = 0x68
TRV_DELAY_OFFSET = 0x80
FAULT_STATE_OFFSET = 0x2E
TXT_COMMAND_OFFSET = 0x74
YOLO_OFFSET = 0x90
TXT_BUFFER_1_OFFSET = 0x100
TXT_BUFFER_2_OFFSET = 0x200

RX_STATUS_RXE_BIT = 0
MODE_RST_BIT = 0
MODE_STM_BIT = 2
SETTINGS_ILBP_BIT = 5
SETTINGS_ENA_BIT = 6
FAULT_STATE_ERA_BIT = 0
FAULT_STATE_ERP_BIT = 1
FAULT_STATE_BOF_BIT = 2
TXT_COMMAND_TXCR_BIT = 1
TXT_COMMAND_TXB1_BIT = 8
TXT_COMMAND_TXB2_BIT = 8

INT_STAT_RXI_BIT = 0
INT_STAT_TXI_BIT = 1
INT_STAT_EWLI_BIT = 2
INT_STAT_DOI_BIT = 3
INT_STAT_FCSI_BIT = 4
INT_STAT_ALI_BIT = 5
INT_STAT_BEI_BIT = 6
INT_STAT_OFI_BIT = 7
INT_STAT_RXFI_BIT = 8
INT_STAT_BSI_BIT = 9
INT_STAT_RBNEI_BIT = 10
INT_STAT_TXBHCI_BIT = 11

FRAME_FORMAT_OFFSET = 0x0
IDENTIFIER_OFFSET = 0x4
TIMESTAMP_L_OFFSET = 0x8
TIMESTAMP_U_OFFSET = 0xC
DATA_START_OFFSET = 0x10

IDENTIFIER_STD_START_BIT = 18
IDENTIFIER_EXT_START_BIT = 0

FRAME_FORMAT_DLC_START_BIT = 0
FRAME_FORMAT_RTR_BIT = 5
FRAME_FORMAT_IDE_BIT = 6
FRAME_FORMAT_FDF_BIT = 7
FRAME_FORMAT_BRS_BIT = 9

MAX_EXT_ID_LEN = 29
MAX_ID_LEN = 11
TXT_BUFFER_NUM = 4

# helpers


class FrameType(Enum):
    STD = 1
    FD = 2
    RTR = 3


def get_value(wbRes):
    assert len(wbRes) == 1, "use only with a single wb transaction"
    return wbRes[0].datrd


def bit_to_val(bit):
    return 1 << bit


def round_to_multiple(nbr, mlt):
    return mlt * round(nbr / mlt)


# main functionality


def create_wb_master(dut, clk, name="wb", width=16, timeout=10):
    wb_signals_map = {
        "cyc": "cyc",
        "stb": "stb",
        "we": "we",
        "adr": "adr",
        "datwr": "dat_w",
        "datrd": "dat_r",
        "ack": "ack",
        "sel": "sel",
    }

    return WishboneMaster(
        dut,
        name,
        clk,
        width=width,
        timeout=timeout,
        signals_dict=wb_signals_map
    )


@cocotb.coroutine
async def read_reg_32(dut, wbs, off):
    assert off % 0x4 == 0, "reg not aligned to 0x4"
    wbRes = await wbs.send_cycle([WBOp(off >> 2)])
    result = get_value(wbRes)
    dut._log.info(f"read {hex(result)} from {hex(off)}")
    return result


@cocotb.coroutine
async def write_reg_32(dut, wbs, off, val):
    assert off % 0x4 == 0, "reg not aligned to 0x4"
    dut._log.info(f"write {hex(val)} to {hex(off)}")
    await wbs.send_cycle([WBOp(off >> 2, val)])


@cocotb.coroutine
async def read_reg_16(dut, wbs, off):
    if off % 0x4 == 0:
        reg = await read_reg_32(dut, wbs, off)
        return reg & 0x0000FFFF
    else:
        reg = await read_reg_32(dut, wbs, off & ~(0x4 - 1))
        return (reg & 0xFFFF0000) >> 16


@cocotb.coroutine
async def write_reg_16(dut, wbs, off, val):
    if off % 0x4 == 0:
        addr = off
        reg = await read_reg_32(dut, wbs, addr)
        reg = (reg & 0xFFFF0000) | (val)
    else:
        addr = off & 0x4
        reg = await read_reg_32(dut, wbs, addr)
        reg = (reg & 0x0000FFFF) | (val << 16)
    await write_reg_32(dut, wbs, addr, reg)


@cocotb.coroutine
async def set_bit_16(dut, wbs, off, bit, val):
    reg_val = await read_reg_16(dut, wbs, off)
    val_tmp = 0x1 if val > 0 else 0x0
    reg_val = (reg_val & ~bit_to_val(bit)) | (val_tmp << bit)
    await write_reg_16(dut, wbs, off, reg_val)


@cocotb.coroutine
async def get_bit_16(dut, wbs, off, bit):
    reg_val = await read_reg_16(dut, wbs, off)
    return 0x1 if (reg_val & bit_to_val(bit)) > 0 else 0x0


# ctucan functions


@cocotb.coroutine
async def reset(dut, wbs):
    await set_bit_16(dut, wbs, MODE_OFFSET, MODE_RST_BIT, 0x1)


@cocotb.coroutine
async def read_version(dut, wbs):
    reg_val = await read_reg_16(dut, wbs, VERSION_OFFSET)


@cocotb.coroutine
async def read_deviceid(dut, wbs):
    reg_val = await read_reg_16(dut, wbs, DEVICE_ID_OFFSET)


@cocotb.coroutine
async def read_yolo(dut, wbs):
    reg_val = await read_reg_32(dut, wbs, YOLO_OFFSET)


@cocotb.coroutine
async def is_disabled(dut, wbs):
    reg_val = await get_bit_16(dut, wbs, SETTINGS_OFFSET, SETTINGS_ENA_BIT)
    return True if reg_val == 0 else False


@cocotb.coroutine
async def is_initialized(dut, wbs):
    reg_val = await get_bit_16(
        dut, wbs, FAULT_STATE_OFFSET, FAULT_STATE_ERA_BIT
    )
    return True if reg_val == 1 else False


@cocotb.coroutine
async def disable(dut, wbs):
    await set_bit_16(dut, wbs, SETTINGS_OFFSET, SETTINGS_ENA_BIT, 0x0)


@cocotb.coroutine
async def enable(dut, wbs):
    return await set_bit_16(dut, wbs, SETTINGS_OFFSET, SETTINGS_ENA_BIT, 0x1)


@cocotb.coroutine
async def enable_selfack(dut, wbs):
    await set_bit_16(dut, wbs, MODE_OFFSET, MODE_STM_BIT, 0x1)


@cocotb.coroutine
async def enable_loop(dut, wbs):
    await set_bit_16(dut, wbs, SETTINGS_OFFSET, SETTINGS_ILBP_BIT, 0x1)


@cocotb.coroutine
async def rx_empty(dut, wbs):
    rxe = await get_bit_16(dut, wbs, RX_STATUS_OFFSET, RX_STATUS_RXE_BIT)
    return True if rxe == 1 else False


@cocotb.coroutine
async def send_frame(
    dut,
    wbs,
    frame_type=FrameType.STD,
    data=0x1122334455667788,
    idf=0x123,
    extidf=False,
    brs=False,
    buffno=0
):
    if buffno >= TXT_BUFFER_NUM:
        raise Exception("too high tx buffer number")

    if not extidf and idf.bit_length() > MAX_ID_LEN:
        raise Exception("standard frame identifier too long")

    if extidf and idf.bit_length() > MAX_EXT_ID_LEN:
        raise Exception("extended frame identifier too long")

    idf_off = IDENTIFIER_EXT_START_BIT if extidf else IDENTIFIER_STD_START_BIT
    identifier = (idf << idf_off)

    if buffno == 0:
        buff_off = TXT_BUFFER_1_OFFSET
        buff_select_bit = TXT_COMMAND_TXB1_BIT
    elif buffno == 1:
        buff_off = TXT_BUFFER_2_OFFSET
        buff_select_bit = TXT_COMMAND_TXB2_BIT
    elif buffno == 2:
        buff_off = TXT_BUFFER_3_OFFSET
        buff_select_bit = TXT_COMMAND_TXB3_BIT
    elif buffno == 3:
        buff_off = TXT_BUFFER_4_OFFSET
        buff_select_bit = TXT_COMMAND_TXB4_BIT

    data_length_in_bytes = round_to_multiple(data.bit_length(), 8) // 8
    frame_format = (data_length_in_bytes << FRAME_FORMAT_DLC_START_BIT)
    if frame_type == FrameType.RTR:
        frame_format |= bit_to_val(FRAME_FORMAT_RTR_BIT)
    if frame_type == FrameType.FD:
        frame_format |= bit_to_val(FRAME_FORMAT_FDF_BIT)
        if brs:
            frame_format |= bit_to_val(FRAME_FORMAT_BRS_BIT)

    await write_reg_32(dut, wbs, buff_off + FRAME_FORMAT_OFFSET, frame_format)
    await write_reg_32(dut, wbs, buff_off + IDENTIFIER_OFFSET, identifier)

    if frame_type != FrameType.RTR:
        await write_reg_32(dut, wbs, buff_off + TIMESTAMP_L_OFFSET, 0)
        await write_reg_32(dut, wbs, buff_off + TIMESTAMP_U_OFFSET, 0)

        for i in range(data_length_in_bytes // 4):
            offset = buff_off + DATA_START_OFFSET + i * 0x4
            reg_val = 0xFFFFFFFF & data
            await write_reg_32(dut, wbs, offset, reg_val)
            data >>= 32

    await write_reg_32(
        dut,
        wbs,
        TXT_COMMAND_OFFSET,
        bit_to_val(TXT_COMMAND_TXCR_BIT) | bit_to_val(buff_select_bit)
    )


@cocotb.coroutine
async def send_2_0_frame(dut, wbs, data, idf):
    await send_frame(dut, wbs, frame_type=FrameType.STD, data=data, idf=idf)


@cocotb.coroutine
async def send_2_0_ext_frame(dut, wbs, data, idf):
    await send_frame(
        dut, wbs, frame_type=FrameType.STD, data=data, idf=idf, extidf=True
    )


@cocotb.coroutine
async def send_fd_frame(dut, wbs, data, idf, brs):
    await send_frame(
        dut,
        wbs,
        frame_type=FrameType.FD,
        data=data,
        idf=idf,
        brs=brs,
        extidf=False
    )


@cocotb.coroutine
async def send_fd_ext_frame(dut, wbs, data, idf, brs):
    await send_frame(
        dut,
        wbs,
        frame_type=FrameType.FD,
        data=data,
        idf=idf,
        brs=brs,
        extidf=True
    )


@cocotb.coroutine
async def send_rtr_frame(dut, wbs, idf):
    await send_frame(dut, wbs, frame_type=FrameType.RTR, idf=idf)


@cocotb.coroutine
async def recv_frame(dut, wbs):
    ffw = await read_reg_32(dut, wbs, RX_DATA_OFFSET)
    id = await read_reg_32(dut, wbs, RX_DATA_OFFSET)
    ts_l = await read_reg_32(dut, wbs, RX_DATA_OFFSET)
    ts_h = await read_reg_32(dut, wbs, RX_DATA_OFFSET)

    rwcnt = (ffw >> MAX_ID_LEN) & 0x1F
    for _ in range(rwcnt - 3):  # Skip identifier and 2 timestamp fileds
        data = await read_reg_32(dut, wbs, RX_DATA_OFFSET)
        dut._log.info("data = {}".format(hex(data)))


@cocotb.coroutine
async def irq_mask_all(dut, wbs):
    reg_val = await read_reg_16(dut, wbs, INT_MASK_SET_OFFSET)
    mask = 0x0FFF
    reg_val = (reg_val & ~mask) | mask
    await write_reg_16(dut, wbs, INT_MASK_SET_OFFSET, reg_val)


@cocotb.coroutine
async def irq_enable(dut, wbs, irq_bit):
    await set_bit_16(dut, wbs, INT_ENA_SET_OFFSET, irq_bit, 0x1)


@cocotb.coroutine
async def irq_disable(dut, wbs, irq_bit):
    await set_bit_16(dut, wbs, INT_ENA_SET_OFFSET, irq_bit, 0x1)


@cocotb.coroutine
async def irq_clear(dut, wbs, irq_bit):
    await set_bit_16(dut, wbs, INT_ENA_CLR_OFFSET, irq_bit, 0x1)


@cocotb.coroutine
async def irq_mask(dut, wbs, irq_bit):
    await set_bit_16(dut, wbs, INT_MASK_SET_OFFSET, irq_bit, 0x1)


@cocotb.coroutine
async def irq_unmask(dut, wbs, irq_bit):
    await set_bit_16(dut, wbs, INT_MASK_CLR_OFFSET, irq_bit, 0x1)
