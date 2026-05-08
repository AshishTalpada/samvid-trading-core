module tick_normalizer (
    input clk,
    input [63:0] raw_price,
    output reg [63:0] norm_price
);
    always @(posedge clk) begin
        norm_price <= raw_price / 10000;
    end
endmodule
