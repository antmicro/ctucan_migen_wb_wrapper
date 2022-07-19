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
--  Interrupt Manager
--
-- Purpose:
--  Captures interrupts to Interrupt vector. Maintains Interrupt Enable and 
--  Interrupt Mask registers. Configured (Set and Clear) from Memory registers.
--  An edge is detected on each interrupt source. If an interrupt is unmasked,
--  it is captured to interrupt vector. If an interrupt is enabled and it is
--  active in Interrupt vector, it causes Interrupt output to be asserted.
--  Interrupt output is pipelined to make sure it is glitch free.
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

entity int_manager is
    generic(
        -- Reset polarity
        G_RESET_POLARITY     : std_logic := '0';
        
        -- Number of supported interrupts
        G_INT_COUNT          : natural  := 11;
        
        -- Number of TXT Buffers
        G_TXT_BUFFER_COUNT   : natural := 4
    );
    port(
        ------------------------------------------------------------------------
        -- Clock and Asynchronous reset
        ------------------------------------------------------------------------
        -- System clock
        clk_sys                 :in   std_logic;
        
        -- Asynchronous Reset
        res_n                   :in   std_logic;

        ------------------------------------------------------------------------
        -- Interrupt sources
        ------------------------------------------------------------------------
        -- Error appeared
        err_detected            :in   std_logic;

        -- Fault confinement state changed
        fcs_changed             :in   std_logic;

        -- Error warning limit reached
        err_warning_limit       :in   std_logic;

        -- Arbitration was lost input
        arbitration_lost        :in   std_logic;

        -- Transmitted frame is valid
        tran_valid              :in   std_logic;

        -- Bit Rate Was Shifted
        br_shifted              :in   std_logic;

        -- Rx Buffer data overrun
        rx_data_overrun         :in   std_logic;
        
        -- Received frame is valid
        rec_valid               :in   std_logic;
        
        -- RX Buffer is full
        rx_full          :in   std_logic;
        
        -- Recieve buffer is empty
        rx_empty         :in   std_logic;

        -- HW command on TXT Buffers interrupt
        txtb_hw_cmd_int  :in   std_logic_vector(G_TXT_BUFFER_COUNT - 1 downto 0);
        
        -- Overload frame is being transmitted
        is_overload      :in   std_logic;

        ------------------------------------------------------------------------
        -- Memory registers Interface
        ------------------------------------------------------------------------
        drv_bus          :in   std_logic_vector(1023 downto 0);

        -- Interrupt output
        int              :out  std_logic; 

        -- Interrupt vector
        int_vector       :out  std_logic_vector(G_INT_COUNT - 1 downto 0);

        -- Interrupt mask
        int_mask         :out  std_logic_vector(G_INT_COUNT - 1 downto 0);

        -- Interrupt enable
        int_ena          :out  std_logic_vector(G_INT_COUNT - 1 downto 0)
    );
end entity;

architecture rtl of int_manager is
  
    ----------------------------------------------------------------------------
    -- Driving bus aliases 
    ----------------------------------------------------------------------------
    signal drv_int_vect_clr       :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal drv_int_ena_set        :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal drv_int_ena_clr        :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal drv_int_mask_set       :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal drv_int_mask_clr       :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    ----------------------------------------------------------------------------
    -- Internal registers and signals
    ----------------------------------------------------------------------------

    signal int_ena_i              :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal int_mask_i             :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal int_vect_i             :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    signal int_input_active       :     std_logic_vector(G_INT_COUNT - 1 downto 0);

    constant zero_mask            :     std_logic_vector(G_INT_COUNT - 1 downto 0)
                                                := (OTHERS => '0');
                                                
    ----------------------------------------------------------------------------
    -- Reset over set priority assignment
    ----------------------------------------------------------------------------
    type int_s_r_priority_type is array(0 to G_INT_COUNT - 1) of boolean;
    
    constant int_clear_priority     :     int_s_r_priority_type :=
        (false,  -- RXI_IND
         false,  -- TXI_IND
         false,  -- EWLI_IND
         false,  -- DOI_IND
         false,  -- EPI_IND
         false,  -- ALI_IND
         false,  -- BEI_IND
         false,  -- LFI_IND
         false,  -- RXFI_IND
         false,  -- BSI_IND
         false,  -- RBNEI_IND
         false   -- TXBHCI_IND
        );

    -- Internal value of an interrupt
    signal int_i                : std_logic;

begin
  
    -- Driving bus aliases
    drv_int_vect_clr  <= drv_bus(DRV_INT_CLR_HIGH downto DRV_INT_CLR_LOW);
    drv_int_ena_set   <= drv_bus(DRV_INT_ENA_SET_HIGH downto DRV_INT_ENA_SET_LOW);
    drv_int_ena_clr   <= drv_bus(DRV_INT_ENA_CLR_HIGH downto DRV_INT_ENA_CLR_LOW);
    drv_int_mask_set  <= drv_bus(DRV_INT_MASK_SET_HIGH downto DRV_INT_MASK_SET_LOW);
    drv_int_mask_clr  <= drv_bus(DRV_INT_MASK_CLR_HIGH downto DRV_INT_MASK_CLR_LOW);


    ---------------------------------------------------------------------------      
    -- Register to output propagation
    ---------------------------------------------------------------------------
    int_vector                          <= int_vect_i;
    int_mask                            <= int_mask_i;
    int_ena                             <= int_ena_i;


    ---------------------------------------------------------------------------      
    -- Driving Interrupt output when there is at least one active interrupt
    -- enabled.
    ---------------------------------------------------------------------------
    int_i  <= '0' when (int_vect_i and int_ena_i) = zero_mask else
              '1';

    ---------------------------------------------------------------------------
    -- Interrupt register masking and enabling
    ---------------------------------------------------------------------------
    int_input_active(RXI_IND)       <= rec_valid;
    int_input_active(TXI_IND)       <= tran_valid;
    int_input_active(EWLI_IND)      <= err_warning_limit;
    int_input_active(DOI_IND)       <= rx_data_overrun;
    int_input_active(FCSI_IND)      <= fcs_changed;
    int_input_active(ALI_IND)       <= arbitration_lost;
    int_input_active(BEI_IND)       <= err_detected;
    int_input_active(RXFI_IND)      <= rx_full;
    int_input_active(BSI_IND)       <= br_shifted;
    int_input_active(RBNEI_IND)     <= not rx_empty;
    int_input_active(TXBHCI_IND)    <= or_reduce(txtb_hw_cmd_int);

    -- Overload frame interrupt
    int_input_active(OFI_IND)       <= is_overload;

    ---------------------------------------------------------------------------
    -- Interrupt module instances
    ---------------------------------------------------------------------------
    int_module_gen : for i in 0 to G_INT_COUNT - 1 generate
        
        int_module_inst : int_module
        generic map(        
            G_RESET_POLARITY       => G_RESET_POLARITY,
            G_CLEAR_PRIORITY       => int_clear_priority(i)
        )
        port map(
            clk_sys                => clk_sys,              -- IN
            res_n                  => res_n,                -- IN

            int_status_set         => int_input_active(i),  -- IN
            int_status_clear       => drv_int_vect_clr(i),  -- IN

            int_mask_set           => drv_int_mask_set(i),  -- IN
            int_mask_clear         => drv_int_mask_clr(i),  -- IN

            int_ena_set            => drv_int_ena_set(i),   -- IN
            int_ena_clear          => drv_int_ena_clr(i),   -- IN

            int_status             => int_vect_i(i),        -- OUT
            int_mask               => int_mask_i(i),        -- OUT
            int_ena                => int_ena_i(i)          -- OUT
        );
    end generate int_module_gen;

    ---------------------------------------------------------------------------
    -- Output interrupt DFF to make sure that interrupt output will be
    -- glitch free!
    ---------------------------------------------------------------------------
    dff_int_output_reg : dff_arst
    generic map(
        G_RESET_POLARITY   => G_RESET_POLARITY,
        G_RST_VAL          => '0'
    )
    port map(
        arst               => res_n,        -- IN
        clk                => clk_sys,      -- IN
        input              => int_i,        -- IN

        output             => int           -- OUT
    );

end architecture;