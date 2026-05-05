`ifdef ABV
module top_abv #(
    parameter int unsigned WIDTH = 8
) (
    input logic clk_i,
    input logic rst_ni,
    input logic en_i,
    input logic [WIDTH-1:0] count_o
);

  localparam logic [WIDTH-1:0] MaxCount = {WIDTH{1'b1}};

  // Assertions

  reset_clears_counter_a :
  assert property (@(posedge clk_i) !rst_ni |=> count_o == '0)
  else $fatal("count_o did not clear after reset");

  enable_low_holds_counter_a :
  assert property (@(posedge clk_i) disable iff (!rst_ni) !en_i |=> count_o == $past(count_o))
  else $fatal("count_o changed while en_i was low");

  enable_high_increments_counter_a :
  assert property (@(posedge clk_i) disable iff (!rst_ni) en_i |=> count_o == $past(count_o) + 1'b1)
  else $fatal("count_o did not increment while en_i was high");

  // Covers

  reset_observed_c :
  cover property (@(posedge clk_i) !rst_ni);

  enable_low_hold_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) $past(
      rst_ni
  ) && !$past(
      en_i
  ) && count_o == $past(
      count_o
  ));

  enable_high_increment_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) $past(
      rst_ni
  ) && $past(
      en_i
  ) && count_o == $past(
      count_o
  ) + 1'b1);

  wraparound_setup_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) en_i && count_o == MaxCount);

  // Covergroups
`ifndef NO_COVERGROUPS

  covergroup counter_cg @(posedge clk_i);
    option.per_instance = 1;

    cp_count: coverpoint count_o {
      bins low = {[0 : MaxCount / 4]};
      bins mid = {[MaxCount / 4 + 1 : MaxCount * 3 / 4]};
      bins high = {[MaxCount * 3 / 4 + 1 : MaxCount - 1]};
      bins max = {MaxCount};
    }

    cp_en: coverpoint en_i {bins disabled = {1'b0}; bins enabled = {1'b1};}

    cp_rst: coverpoint rst_ni {bins active = {1'b0}; bins inactive = {1'b1};}

    cx_en_count : cross cp_en, cp_count;
  endgroup

  counter_cg counter_cg_i = new();

`endif

endmodule
`endif
