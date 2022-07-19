`timescale 1ns / 1ns

module top_test(
	output irq,
	input [13:0] wb_adr,
	input [31:0] wb_dat_w,
	output [31:0] wb_dat_r,
	input [3:0] wb_sel,
	input wb_cyc,
	input wb_stb,
	output wb_ack,
	input wb_we,
	input sys_clk,
	input sys_rst
);

wire can_rx;
wire can_tx;

assign can_rx = can_tx;

CTUCAN can(
	.can_rx(can_rx),
	.can_tx(can_tx),
	.irq(irq),
	.bus_adr(wb_adr),
	.bus_dat_w(wb_dat_w),
	.bus_dat_r(wb_dat_r),
	.bus_sel(wb_sel),
	.bus_cyc(wb_cyc),
	.bus_stb(wb_stb),
	.bus_ack(wb_ack),
	.bus_we(wb_we),
	.sys_clk(sys_clk),
	.sys_rst(sys_rst)
);

endmodule
