--------------------------------------------------------------------------------
-- 
-- CTU CAN FD IP Core
-- Copyright (C) 2015-2018
-- 
-- Authors:
--     Ondrej Ille <ondrej.ille@gmail.com>
--     Martin Jerabek <martin.jerabek01@gmail.com>
-- 
-- Project advisors: 
-- 	Jiri Novak <jnovak@fel.cvut.cz>
-- 	Pavel Pisa <pisa@cmp.felk.cvut.cz>
-- 
-- Department of Measurement         (http://meas.fel.cvut.cz/)
-- Faculty of Electrical Engineering (http://www.fel.cvut.cz)
-- Czech Technical University        (http://www.cvut.cz/)
-- 
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this VHDL component and associated documentation files (the "Component"),
-- to deal in the Component without restriction, including without limitation
-- the rights to use, copy, modify, merge, publish, distribute, sublicense,
-- and/or sell copies of the Component, and to permit persons to whom the
-- Component is furnished to do so, subject to the following conditions:
-- 
-- The above copyright notice and this permission notice shall be included in
-- all copies or substantial portions of the Component.
-- 
-- THE COMPONENT IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHTHOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
-- FROM, OUT OF OR IN CONNECTION WITH THE COMPONENT OR THE USE OR OTHER DEALINGS
-- IN THE COMPONENT.
-- 
-- The CAN protocol is developed by Robert Bosch GmbH and protected by patents.
-- Anybody who wants to implement this IP core on silicon has to obtain a CAN
-- protocol license from Bosch.
-- 
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
-- Module:
--  TX Data Cache.
--
-- Purpose:
--  Stores TX Data into FIFO buffer in time of regular sample point and read
--  at the time of secondary sample point. Output data are used for bit 
--  error detection.
--------------------------------------------------------------------------------

Library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.ALL;

Library ctu_can_fd_rtl;
use ctu_can_fd_rtl.id_transfer.all;
use ctu_can_fd_rtl.can_constants.all;
use ctu_can_fd_rtl.can_components.all;
use ctu_can_fd_rtl.can_types.all;
use ctu_can_fd_rtl.cmn_lib.all;
use ctu_can_fd_rtl.drv_stat_pkg.all;
use ctu_can_fd_rtl.reduce_lib.all;

use ctu_can_fd_rtl.CAN_FD_register_map.all;
use ctu_can_fd_rtl.CAN_FD_frame_format.all;

entity tx_data_cache is
    generic(
        -- Reset polarity
        G_RESET_POLARITY        :     std_logic := '0';
        
        -- Depth of FIFO (Number of bits that can be stored)
        G_TX_CACHE_DEPTH        :     natural range 4 to 32 := 8;
        
        -- FIFO reset value
        G_TX_CACHE_RST_VAL      :     std_logic := '0'
    );
    port(
        ------------------------------------------------------------------------
        -- Clock and Asynchronous reset
        ------------------------------------------------------------------------
        -- System clock
        clk_sys         :in   std_logic;
        
        -- Asynchronous reset
        res_n           :in   std_logic;

        ------------------------------------------------------------------------
        -- Control signals
        ------------------------------------------------------------------------
        -- Store input data
        write           :in   std_logic;
        
        -- Read output data
        read            :in   std_logic;
        
        ------------------------------------------------------------------------
        -- Data signals
        ------------------------------------------------------------------------
        -- Data inputs
        data_in         :in   std_logic;
        
        -- Data output
        data_out        :out  std_logic
    );
end entity;

architecture rtl of tx_data_cache is

    -- Cache Memory (FIFO in DFFs)
    signal tx_cache_mem         : std_logic_vector(G_TX_CACHE_DEPTH - 1 downto 0);
    
    ---------------------------------------------------------------------------
    -- Access pointers
    ---------------------------------------------------------------------------
    -- Write Pointer
    signal write_pointer_q      : natural range 0 to G_TX_CACHE_DEPTH - 1;
    signal write_pointer_d      : natural range 0 to G_TX_CACHE_DEPTH - 1;

    -- Read pointer
    signal read_pointer_q       : natural range 0 to G_TX_CACHE_DEPTH - 1;
    signal read_pointer_d       : natural range 0 to G_TX_CACHE_DEPTH - 1; 

begin
    
    ----------------------------------------------------------------------------
    -- Combinationally incrementing write and read pointers
    ----------------------------------------------------------------------------
    write_pointer_d <= (write_pointer_q + 1) mod G_TX_CACHE_DEPTH;
    read_pointer_d <= (read_pointer_q + 1) mod G_TX_CACHE_DEPTH;

    
    ----------------------------------------------------------------------------
    -- Incrementing the pointers upon read or write.
    ----------------------------------------------------------------------------
    write_ptr_proc : process(clk_sys, res_n)
    begin
        if (res_n = G_RESET_POLARITY) then
            write_pointer_q        <= 0;
        elsif (rising_edge(clk_sys)) then
            if (write = '1') then
                write_pointer_q    <= write_pointer_d;
            end if;
        end if;
    end process;


    read_ptr_proc : process(clk_sys, res_n)
    begin
        if (res_n = G_RESET_POLARITY) then
            read_pointer_q         <= 0;
        elsif (rising_edge(clk_sys)) then
            if (read = '1') then
                read_pointer_q     <= read_pointer_d;
            end if;
        end if;
    end process;


    ----------------------------------------------------------------------------
    -- Storing data to FIFO.
    ----------------------------------------------------------------------------
    tx_cache_mem_proc : process(clk_sys, res_n)
    begin
        if (res_n = G_RESET_POLARITY) then
            tx_cache_mem <= (OTHERS => G_TX_CACHE_RST_VAL);
        elsif (rising_edge(clk_sys)) then
            if (write = '1') then
                tx_cache_mem(write_pointer_q) <= data_in;
            end if;
        end if;
    end process;


    ----------------------------------------------------------------------------
    -- Reading data from FIFO combinationally.
    -- We need to have the data available right away, not pipelined!
    ----------------------------------------------------------------------------
    data_out <= tx_cache_mem(read_pointer_q);


end architecture;