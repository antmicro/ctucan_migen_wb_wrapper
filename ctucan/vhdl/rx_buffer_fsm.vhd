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
--  RX Buffer FSM.
-- 
-- Purpose:
--  Reacts on commands from CAN Core and controls storing of CAN frame 
--  continusly to RX Buffer RAM.
--------------------------------------------------------------------------------

Library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.ALL;
use ieee.math_real.ALL;

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

entity rx_buffer_fsm is
    generic(
        G_RESET_POLARITY     :       std_logic := '0'
    );
    port(
        ------------------------------------------------------------------------
        -- Clocks and reset 
        ------------------------------------------------------------------------
        -- System clock
        clk_sys              :in     std_logic;
        
        -- Asynchronous reset
        res_n                :in     std_logic;

        ------------------------------------------------------------------------
        -- Control signals from CAN Core (Filtered by Frame filters)
        ------------------------------------------------------------------------
        -- Start Storing of Metadata to RX Buffer (first 4 words of frame)
        store_metadata_f     :in     std_logic;
       
        -- Store Data word to RX Buffer
        store_data_f         :in     std_logic;

        -- Received frame valid
        rec_valid_f          :in     std_logic;
        
        -- Abort storing of RX Frame to RX Buffer.
        rec_abort_f          :in     std_logic;

        -----------------------------------------------------------------------
        -- FSM outputs
        -----------------------------------------------------------------------
        -- Intent to write to RX Buffer RAM
        write_raw_intent     :out    std_logic;

        -- Write Timestamp to RX Buffer RAM memory
        write_ts             :out    std_logic;

        -- Storing of Timestamp has ended.
        stored_ts            :out    std_logic;

        -- Data selector for selection of memory word to be stored in RX Buffer 
        -- RAM (one hot coded)
        data_selector        :out    std_logic_vector(4 downto 0);

        -- Load timestamp write pointer from regular write pointer
        store_ts_wr_ptr      :out    std_logic;

        -- Increment timestamp write pointer by 1
        inc_ts_wr_ptr        :out    std_logic;

        -- Reset internal overrun flag
        reset_overrun_flag   :out    std_logic
    );
end entity;

architecture rtl of rx_buffer_fsm is

    -- RX Buffer FSM
    signal curr_state               :       t_rx_buf_state;
    signal next_state               :       t_rx_buf_state;
    
    -- Clock enable for state register
    signal rx_fsm_ce                :       std_logic;


begin

    ----------------------------------------------------------------------------
    -- Next State process
    ----------------------------------------------------------------------------
    next_state_proc : process(curr_state, store_metadata_f, rec_abort_f, 
        rec_valid_f)
    begin
        next_state <= curr_state;
        
        case curr_state is

        --------------------------------------------------------------------
        -- Idle, waiting for "store_metada" to start storing first 4 words.
        --------------------------------------------------------------------
        when s_rxb_idle =>
            if (store_metadata_f = '1' and rec_abort_f = '0') then
                next_state      <= s_rxb_store_frame_format;
            end if;

        --------------------------------------------------------------------
        -- Storing FRAME_FORM_W. Proceed execpt if error ocurrs.
        --------------------------------------------------------------------
        when s_rxb_store_frame_format =>
            if (rec_abort_f = '1') then
                next_state      <= s_rxb_idle;
            else
                next_state      <= s_rxb_store_identifier;
            end if;

        --------------------------------------------------------------------
        -- Storing IDENTIFIER_W.
        -- Move to storing timestamp words. Note that if SW configured
        -- timestamp from end of the frame, we dont have it yet! We store
        -- invalid timestamp and later (if the frame is received OK), we
        -- repeat the writes with timestamp captured at the end of frame!
        --------------------------------------------------------------------
        when s_rxb_store_identifier =>
            next_state      <= s_rxb_skip_ts_low;
            
        --------------------------------------------------------------------
        -- Skip through TIMESTAMP_L_W, store only zeroes.
        --------------------------------------------------------------------
        when s_rxb_skip_ts_low =>
            next_state      <= s_rxb_skip_ts_high;
            
        --------------------------------------------------------------------
        -- Skip through TIMESTAMP_U_W, store only zeroes.
        --------------------------------------------------------------------
        when s_rxb_skip_ts_high =>
            next_state      <= s_rxb_store_data;
            
        --------------------------------------------------------------------
        -- Store DATA_W. If error ocurrs, abort the storing. If storing is
        -- finished, go to idle or again timestamp storing depending on the
        -- timestamp option configuration. Note that now timestamp storing
        -- is realized via different states!
         --------------------------------------------------------------------
        when s_rxb_store_data =>
            if (rec_abort_f = '1') then 
                next_state      <= s_rxb_idle;
            elsif (rec_valid_f = '1') then
                next_state      <= s_rxb_store_end_ts_low;
            end if;

        --------------------------------------------------------------------
        -- Store TIMESTAMP_L_W.
        --------------------------------------------------------------------
        when s_rxb_store_end_ts_low =>
            next_state      <= s_rxb_store_end_ts_high;

        --------------------------------------------------------------------
        -- Store first TIMESTAMP_U_W.
        --------------------------------------------------------------------
        when s_rxb_store_end_ts_high =>
            next_state      <= s_rxb_idle;
            
        end case;
    end process;


    ----------------------------------------------------------------------------
    -- Current State process (outputs)
    ----------------------------------------------------------------------------
    curr_state_proc : process(curr_state, store_data_f)
    begin
        write_raw_intent <= '0';
        write_ts <= '0'; 
        data_selector <= (OTHERS => '0');
        stored_ts <= '0';
        store_ts_wr_ptr <= '0';
        inc_ts_wr_ptr <= '0';
        reset_overrun_flag <= '0';
        
        case curr_state is
        when s_rxb_idle =>
            reset_overrun_flag <= '1';
            
        when s_rxb_store_frame_format =>
            write_raw_intent <= '1';
            data_selector    <= "00001";
            
        when s_rxb_store_identifier =>
            write_raw_intent <= '1';
            data_selector    <= "00010";

        when s_rxb_skip_ts_low =>
            write_raw_intent <= '1';

            -- Here we capture value of Raw write pointer to Timestamp write pointer
            -- so that it can be later used for Timestamp storing.
            store_ts_wr_ptr <= '1';
            
        when s_rxb_skip_ts_high =>
            write_raw_intent <= '1';
            
        when s_rxb_store_data =>
            data_selector    <= "00100";
            
            if (store_data_f = '1') then
                write_raw_intent      <= '1';
            end if;
            
        when s_rxb_store_end_ts_low =>
            data_selector    <= "01000";

            -- Timestamp write pointer is incremented once more when lower
            -- timestamp word was stored, to point to higher timestamp word.
            inc_ts_wr_ptr <= '1';
            
            -- Signalling that timestamp is stored to memory.
            write_ts   <= '1';
            
        when s_rxb_store_end_ts_high =>
            data_selector    <= "10000";
            
            -- Storing of timestamp is ending and frame can be committed.
            stored_ts <= '1';
            
            -- Signalling that timestamp is stored to memory.
            write_ts   <= '1';
        end case;
    end process;
    

    ----------------------------------------------------------------------------
    -- State register process
    ----------------------------------------------------------------------------
    state_reg_proc : process(clk_sys, res_n)
    begin
        if (res_n = G_RESET_POLARITY) then
            curr_state <= s_rxb_idle;
        elsif (rising_edge(clk_sys)) then
            if (rx_fsm_ce = '1') then
                curr_state <= next_state;
            end if;
        end if;
    end process;
    
    -- Clock enable for State reg
    rx_fsm_ce <= '1' when (next_state /= curr_state) else
                 '0';
    
end architecture;