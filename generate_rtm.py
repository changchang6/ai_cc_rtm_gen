#!/usr/bin/env python3
"""
RTM Generator for APLC-Lite
Generates complete RTM file with Checkers and Testcases based on LRS
"""

import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from copy import copy
import os

# Read template
template_path = "TBUS_RTM.xlsx"
output_path = "TBUS_RTM_Generated.xlsx"

wb = openpyxl.load_workbook(template_path)

# ============================================
# Checker List - Generated based on LRS
# ============================================
checkers = [
    {
        "chk_id": "CHK_001",
        "chk_name": "clk_freq_checker",
        "chk_description": """1.检查频率值是否正确：连续采集clk_i时钟上升沿和下降沿并计算实际频率/周期，判断是否处于目标频率100MHz的允许误差范围内（±1%）；
2.检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内。""",
        "note": "覆盖TP_001, TP_002"
    },
    {
        "chk_id": "CHK_002",
        "chk_name": "rst_async_sync_checker",
        "chk_description": """1.检查rst_ni异步复位行为：rst_ni下降沿立即触发复位，无需等待clk_i上升沿；
2.检查同步释放行为：rst_ni释放时在clk_i上升沿同步退出复位状态；
3.检查复位后状态：front_state=IDLE(3'd0)，back_state=S_IDLE(3'd0)。""",
        "note": "覆盖TP_003, TP_004"
    },
    {
        "chk_id": "CHK_003",
        "chk_name": "rst_output_checker",
        "chk_description": """检查复位后所有输出端口的默认值：
1.pdo_oe_o=0（非发送态）；
2.htrans_o=2'b00（IDLE）；
3.csr_rd_en_o=0，csr_wr_en_o=0；
4.pdo_o=4'b0。""",
        "note": "覆盖TP_005"
    },
    {
        "chk_id": "CHK_004",
        "chk_name": "csr_write_checker",
        "chk_description": """检查CSR写操作时序正确性：
1.csr_wr_en_o脉冲持续1个时钟周期；
2.同周期csr_addr_o和csr_wdata_o有效；
3.外部CSR File在同一周期采样写入数据；
4.写操作返回STS_OK(0x00)。""",
        "note": "覆盖TP_006"
    },
    {
        "chk_id": "CHK_005",
        "chk_name": "csr_read_checker",
        "chk_description": """检查CSR读操作时序正确性：
1.csr_rd_en_o脉冲持续1个时钟周期；
2.下一周期外部CSR File将读数据稳定在csr_rdata_i上；
3.模块正确采样rdata；
4.读操作返回STS_OK(0x00)+rdata[31:0]。""",
        "note": "覆盖TP_007"
    },
    {
        "chk_id": "CHK_006",
        "chk_name": "csr_bad_reg_checker",
        "chk_description": """检查CSR地址越界检测：
1.当reg_addr>=0x40时，前置检查拒绝；
2.返回STS_BAD_REG(0x10)；
3.不发起CSR读/写操作（csr_rd_en_o=0, csr_wr_en_o=0）。""",
        "note": "覆盖TP_008"
    },
    {
        "chk_id": "CHK_007",
        "chk_name": "test_mode_checker",
        "chk_description": """检查test_mode_i=0时的命令拒绝行为：
1.前置检查检测到test_mode_i=0；
2.返回STS_NOT_IN_TEST(0x04)；
3.不发起CSR/AHB访问。""",
        "note": "覆盖TP_009, TP_032"
    },
    {
        "chk_id": "CHK_008",
        "chk_name": "disabled_checker",
        "chk_description": """检查en_i=0时的命令拒绝行为：
1.前置检查检测到en_i=0；
2.返回STS_DISABLED(0x08)；
3.不发起CSR/AHB访问。""",
        "note": "覆盖TP_010, TP_033"
    },
    {
        "chk_id": "CHK_009",
        "chk_name": "normal_cmd_checker",
        "chk_description": """检查正常命令执行行为：
1.test_mode_i=1且en_i=1时前置检查通过；
2.WR_CSR/RD_CSR/AHB_WR32/AHB_RD32命令正常执行；
3.返回正确状态码和数据。""",
        "note": "覆盖TP_011"
    },
    {
        "chk_id": "CHK_010",
        "chk_name": "lane_1bit_checker",
        "chk_description": """检查1-bit模式(lane_mode_i=2'b00)数据收发：
1.每拍收发1bit，使用pdi_i[0]/pdo_o[0]；
2.帧接收周期等于帧长bit数；
3.MSB-first顺序传输；
4.pdi_i[3:1]被忽略。""",
        "note": "覆盖TP_012"
    },
    {
        "chk_id": "CHK_011",
        "chk_name": "lane_4bit_checker",
        "chk_description": """检查4-bit模式(lane_mode_i=2'b01)数据收发：
1.每拍收发4bit，使用pdi_i[3:0]/pdo_o[3:0]；
2.帧接收周期等于帧长/4；
3.MSB-first顺序，高nibble优先发送。""",
        "note": "覆盖TP_013"
    },
    {
        "chk_id": "CHK_012",
        "chk_name": "pcs_frame_checker",
        "chk_description": """检查pcs_n_i帧边界控制：
1.pcs_n_i=1时空闲态；
2.pcs_n_i=0时开启帧接收；
3.pcs_n_i拉高时结束事务。""",
        "note": "覆盖TP_014"
    },
    {
        "chk_id": "CHK_013",
        "chk_name": "pdi_lane_checker",
        "chk_description": """检查pdi_i数据线使用：
1.1-bit模式仅pdi_i[0]有效，其余位忽略；
2.4-bit模式pdi_i[3:0]均有效；
3.MSB-first顺序传输。""",
        "note": "覆盖TP_015"
    },
    {
        "chk_id": "CHK_014",
        "chk_name": "pdo_oe_checker",
        "chk_description": """检查pdo_o和pdo_oe_o输出控制：
1.响应阶段pdo_oe_o=1，模块驱动pdo_o；
2.非发送阶段pdo_oe_o=0，pdo_o值无意义；
3.半双工模式，主机和模块不同时驱动。""",
        "note": "覆盖TP_016"
    },
    {
        "chk_id": "CHK_015",
        "chk_name": "frame_wr_csr_checker",
        "chk_description": """检查WR_CSR帧格式与接收：
1.接收48bit(opcode8+reg_addr8+wdata32)；
2.产生frame_valid信号；
3.响应8bit状态码。""",
        "note": "覆盖TP_017"
    },
    {
        "chk_id": "CHK_016",
        "chk_name": "frame_rd_csr_checker",
        "chk_description": """检查RD_CSR帧格式与接收：
1.接收16bit(opcode8+reg_addr8)；
2.产生frame_valid信号；
3.响应40bit(8bit状态+32bit读数据)。""",
        "note": "覆盖TP_018"
    },
    {
        "chk_id": "CHK_017",
        "chk_name": "frame_ahb_wr_checker",
        "chk_description": """检查AHB_WR32帧格式与接收：
1.接收72bit(opcode8+addr32+wdata32)；
2.产生frame_valid信号；
3.响应8bit状态码。""",
        "note": "覆盖TP_019"
    },
    {
        "chk_id": "CHK_018",
        "chk_name": "frame_ahb_rd_checker",
        "chk_description": """检查AHB_RD32帧格式与接收：
1.接收40bit(opcode8+addr32)；
2.产生frame_valid信号；
3.响应40bit(8bit状态+32bit读数据)。""",
        "note": "覆盖TP_020"
    },
    {
        "chk_id": "CHK_019",
        "chk_name": "frame_abort_checker",
        "chk_description": """检查帧中止检测：
1.pcs_n_i在rx_count<expected_rx_bits时提前拉高；
2.产生frame_abort信号；
3.返回STS_FRAME_ERR(0x01)；
4.不发起CSR/AHB访问。""",
        "note": "覆盖TP_021, TP_030"
    },
    {
        "chk_id": "CHK_020",
        "chk_name": "turnaround_checker",
        "chk_description": """检查turnaround时序：
1.请求阶段与响应阶段之间固定插入1个clk_i周期turnaround；
2.turnaround期间pdo_oe_o=0；
3.TX阶段pdo_oe_o=1。""",
        "note": "覆盖TP_022"
    },
    {
        "chk_id": "CHK_021",
        "chk_name": "opcode_decode_checker",
        "chk_description": """检查opcode解码行为：
1.接收8bit后锁存opcode；
2.根据opcode确定expected_rx_bits；
3.正确发起对应类型任务（WR_CSR=0x10, RD_CSR=0x11, AHB_WR32=0x20, AHB_RD32=0x21）。""",
        "note": "覆盖TP_023"
    },
    {
        "chk_id": "CHK_022",
        "chk_name": "bad_opcode_checker",
        "chk_description": """检查非法opcode检测：
1.opcode不在{0x10,0x11,0x20,0x21}中；
2.返回STS_BAD_OPCODE(0x02)；
3.不发起CSR/AHB访问。""",
        "note": "覆盖TP_024, TP_031"
    },
    {
        "chk_id": "CHK_023",
        "chk_name": "ctrl_reg_checker",
        "chk_description": """检查CTRL寄存器配置：
1.EN=1时模块使能；
2.LANE_MODE=00对应1-bit模式，01对应4-bit模式；
3.SOFT_RST写1触发协议上下文清零并恢复默认lane模式。""",
        "note": "覆盖TP_025"
    },
    {
        "chk_id": "CHK_024",
        "chk_name": "lane_switch_violation_checker",
        "chk_description": """检查lane_mode切换违规影响：
1.pcs_n_i=0期间lane_mode_i改变；
2.移位宽度bpc立即改变；
3.帧数据错位；
4.可能误触发STS_BAD_OPCODE或STS_FRAME_ERR。""",
        "note": "覆盖TP_026"
    },
    {
        "chk_id": "CHK_025",
        "chk_name": "lane_switch_valid_checker",
        "chk_description": """检查空闲态lane_mode切换：
1.pcs_n_i=1时切换lane_mode_i；
2.新事务使用更新后的lane_mode；
3.帧数据正确，无错位。""",
        "note": "覆盖TP_027"
    },
    {
        "chk_id": "CHK_026",
        "chk_name": "no_irq_checker",
        "chk_description": """检查MVP版本无独立中断输出：
1.触发各类错误事件；
2.无IRQ信号拉高；
3.错误信息通过STATUS和LAST_ERR寄存器查询。""",
        "note": "覆盖TP_028"
    },
    {
        "chk_id": "CHK_027",
        "chk_name": "polling_status_checker",
        "chk_description": """检查轮询状态获取方式：
1.每次错误状态通过响应帧8bit状态码返回给ATE；
2.前一条错误信息被新命令覆盖；
3.ATE应每条命令后检查状态码。""",
        "note": "覆盖TP_029"
    },
    {
        "chk_id": "CHK_028",
        "chk_name": "align_err_checker",
        "chk_description": """检查地址对齐错误检测：
1.AHB_WR32/AHB_RD32命令addr[1:0]!=2'b00；
2.返回STS_ALIGN_ERR(0x20)；
3.不发起AHB访问。""",
        "note": "覆盖TP_035"
    },
    {
        "chk_id": "CHK_029",
        "chk_name": "ahb_hresp_checker",
        "chk_description": """检查AHB错误响应处理：
1.STATE_WAIT检测到hresp_i=1；
2.转STATE_ERR；
3.返回STS_AHB_ERR(0x40)。""",
        "note": "覆盖TP_036"
    },
    {
        "chk_id": "CHK_030",
        "chk_name": "ahb_timeout_checker",
        "chk_description": """检查AHB超时处理：
1.9-bit超时计数器在STATE_WAIT递增；
2.达BUS_TIMEOUT_CYCLES-1(默认255)触发STATE_ERR；
3.返回STS_AHB_ERR(0x40)。""",
        "note": "覆盖TP_037, TP_047"
    },
    {
        "chk_id": "CHK_031",
        "chk_name": "error_priority_checker",
        "chk_description": """检查错误优先级链：
1.多个前置错误条件同时成立；
2.按固定优先级仅报告最高优先级错误：
FRAME_ERR(0x01)>BAD_OPCODE(0x02)>NOT_IN_TEST(0x04)>DISABLED(0x08)>BAD_REG(0x10)>ALIGN_ERR(0x20)；
3.仅返回一个状态码。""",
        "note": "覆盖TP_038"
    },
    {
        "chk_id": "CHK_032",
        "chk_name": "ahb_err_vs_prechk_checker",
        "chk_description": """检查AHB错误与前置错误的互斥性：
1.AHB错误仅在所有前置检查通过后才可能发生；
2.返回STS_AHB_ERR(0x40)。""",
        "note": "覆盖TP_039"
    },
    {
        "chk_id": "CHK_033",
        "chk_name": "idle_power_checker",
        "chk_description": """检查空闲态功耗控制：
1.pcs_n_i=1时空闲态；
2.接收/发送移位寄存器不更新；
3.超时计数器不工作。""",
        "note": "覆盖TP_040"
    },
    {
        "chk_id": "CHK_034",
        "chk_name": "ahb_idle_checker",
        "chk_description": """检查非测试态AHB输出：
1.test_mode_i=0或无有效任务；
2.htrans_o保持IDLE(2'b00)；
3.无AHB总线翻转。""",
        "note": "覆盖TP_041"
    },
    {
        "chk_id": "CHK_035",
        "chk_name": "timeout_counter_checker",
        "chk_description": """检查超时计数器工作条件：
1.仅在STATE_WAIT期间超时计数器递增；
2.STATE_REQ时清零；
3.IDLE态不工作。""",
        "note": "覆盖TP_042"
    },
    {
        "chk_id": "CHK_036",
        "chk_name": "latency_ahb_rd_4bit_checker",
        "chk_description": """检查4-bit模式AHB_RD32延时：
请求接收10cyc+译码1~2cyc+AHB返回1~N cyc+turnaround 1cyc+响应发送10cyc≈23~24 cycles最小延时。""",
        "note": "覆盖TP_043"
    },
    {
        "chk_id": "CHK_037",
        "chk_name": "latency_ahb_wr_4bit_checker",
        "chk_description": """检查4-bit模式AHB_WR32延时：
请求接收18cyc+执行2cyc+turnaround 1cyc+响应发送2cyc≈23 cycles最小延时。""",
        "note": "覆盖TP_044"
    },
    {
        "chk_id": "CHK_038",
        "chk_name": "latency_ahb_rd_1bit_checker",
        "chk_description": """检查1-bit模式AHB_RD32延时：
请求接收40cyc+译码1~2cyc+AHB返回1~N cyc+turnaround 1cyc+响应发送40cyc≈83~84 cycles最小延时。""",
        "note": "覆盖TP_045"
    },
    {
        "chk_id": "CHK_039",
        "chk_name": "latency_wr_csr_1bit_checker",
        "chk_description": """检查1-bit模式WR_CSR延时：
请求接收48cyc+执行~6cyc+turnaround 1cyc+响应发送8cyc≈63 cycles最小延时。""",
        "note": "覆盖TP_046"
    },
    {
        "chk_id": "CHK_040",
        "chk_name": "dfx_observability_checker",
        "chk_description": """检查内部调试可观测点：
可观测front_state、back_state、opcode、addr、wdata、rdata、status_code、rx_count、tx_count、lane_mode等信号。""",
        "note": "覆盖TP_048"
    },
    {
        "chk_id": "CHK_041",
        "chk_name": "csr_not_in_ahb_map_checker",
        "chk_description": """检查CSR不在AHB memory map中：
1.模块CSR不进入SoC AHB memory map；
2.仅通过协议命令(WR_CSR/RD_CSR)访问。""",
        "note": "覆盖TP_049"
    },
    {
        "chk_id": "CHK_042",
        "chk_name": "ahb_addr_space_checker",
        "chk_description": """检查AHB地址空间：
1.AHB Master采用32bit地址空间和word(32-bit)访问粒度；
2.具体可达目标地址范围由SoC顶层统一约束。""",
        "note": "覆盖TP_050"
    },
    {
        "chk_id": "CHK_043",
        "chk_name": "ahb_write_phase_checker",
        "chk_description": """检查AHB写2-phase流水时序：
1.T1(STATE_REQ)驱动haddr_o/hwrite_o/htrans_o=NONSEQ(2'b10)；
2.T2(STATE_WAIT)htrans_o回到IDLE，驱动hwdata_o；
3.haddr与hwdata错开1拍。""",
        "note": "覆盖TP_051"
    },
    {
        "chk_id": "CHK_044",
        "chk_name": "ahb_read_phase_checker",
        "chk_description": """检查AHB读2-phase流水时序：
1.T1(STATE_REQ)驱动haddr_o/htrans_o=NONSEQ；
2.T2(STATE_WAIT)htrans_o=IDLE；
3.hready_i=1时采样hrdata_i。""",
        "note": "覆盖TP_052"
    },
    {
        "chk_id": "CHK_045",
        "chk_name": "ahb_fixed_signal_checker",
        "chk_description": """检查AHB固定输出信号：
1.hsize_o固定输出3'b010(WORD)；
2.hburst_o固定输出3'b000(SINGLE)；
3.不支持byte/halfword与burst传输。""",
        "note": "覆盖TP_053"
    },
    {
        "chk_id": "CHK_046",
        "chk_name": "ahb_htrans_checker",
        "chk_description": """检查htrans_o在不同FSM状态下的值：
1.htrans_o仅在STATE_REQ(地址相)驱动NONSEQ(2'b10)持续1周期；
2.其余时刻均为IDLE(2'b00)。""",
        "note": "覆盖TP_054"
    },
    {
        "chk_id": "CHK_047",
        "chk_name": "ahb_err_recovery_checker",
        "chk_description": """检查AHB错误后FSM恢复：
1.STATE_ERR下一拍自动转STATE_IDLE；
2.AHB输出恢复htrans=IDLE, haddr=0；
3.模块可立即接受新请求。""",
        "note": "覆盖TP_055"
    },
]

# ============================================
# DV Testcase List - Generated based on LRS
# ============================================
testcases = [
    {
        "tc_id": "TC_001",
        "tc_name": "clk_freq_test",
        "tc_description": """配置条件：
1.配置clk_i为100MHz连续时钟；
2.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.驱动clk_i持续运行，发送WR_CSR、RD_CSR、AHB_WR32、AHB_RD32命令帧；
2.使用频率计测量时钟频率。

期望结果：
1.所有内部逻辑在clk_i上升沿正确同步；
2.协议接收、状态机控制和AHB-Lite主接口同域工作，无跨时钟域问题；
3.模块在100MHz目标频率下正常工作，所有时序满足约束。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_001, TP_002"
    },
    {
        "tc_id": "TC_002",
        "tc_name": "rst_async_sync_test",
        "tc_description": """配置条件：
1.rst_n_i连接复位源，模块处于任意工作状态。

输入激励：
1.rst_n_i拉低触发异步复位；
2.释放rst_n_i（同步释放）；
3.检查front_state和back_state状态；
4.检查所有输出端口默认值。

期望结果：
1.rst_n_i下降沿立即触发复位；
2.释放时在clk_i上升沿同步退出复位；
3.front_state=IDLE(3'd0)，back_state=S_IDLE(3'd0)；
4.pdo_oe_o=0，htrans_o=2'b00，csr_rd_en_o=0，csr_wr_en_o=0，pdo_o=4'b0。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_003, TP_004, TP_005"
    },
    {
        "tc_id": "TC_003",
        "tc_name": "csr_write_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01；
2.外部CSR File就绪。

输入激励：
1.发送WR_CSR(0x10)命令写VERSION(0x00)、CTRL(0x04)、STATUS(0x08)、LAST_ERR(0x0C)；
2.观测csr_wr_en_o, csr_addr_o, csr_wdata_o信号。

期望结果：
1.csr_wr_en_o脉冲持续1周期；
2.同周期csr_addr_o和csr_wdata_o有效；
3.外部CSR File采样写入数据；
4.写操作返回STS_OK(0x00)。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_006"
    },
    {
        "tc_id": "TC_004",
        "tc_name": "csr_read_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01；
2.外部CSR File就绪，预置读数据。

输入激励：
1.发送RD_CSR(0x11)命令读VERSION(0x00)、CTRL(0x04)；
2.观测csr_rd_en_o, csr_rdata_i信号。

期望结果：
1.csr_rd_en_o脉冲持续1周期；
2.下一周期外部CSR File将读数据稳定在csr_rdata_i上；
3.模块正确采样rdata；
4.读操作返回STS_OK(0x00)+rdata[31:0]。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_007"
    },
    {
        "tc_id": "TC_005",
        "tc_name": "csr_bad_reg_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送WR_CSR/RD_CSR命令访问reg_addr>=0x40的地址（如0x40, 0x80, 0xFF）。

期望结果：
1.前置检查拒绝，返回STS_BAD_REG(0x10)；
2.不发起CSR读/写操作（csr_rd_en_o=0, csr_wr_en_o=0）。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_008"
    },
    {
        "tc_id": "TC_006",
        "tc_name": "test_mode_reject_test",
        "tc_description": """配置条件：
1.test_mode_i=0, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送有效命令帧(RD_CSR 0x11, AHB_RD32 0x21等)。

期望结果：
1.前置检查检测到test_mode_i=0；
2.返回STS_NOT_IN_TEST(0x04)；
3.不发起CSR/AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_009, TP_032"
    },
    {
        "tc_id": "TC_007",
        "tc_name": "disabled_reject_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=0, lane_mode_i=2'b01。

输入激励：
1.发送有效命令帧(RD_CSR 0x11, AHB_RD32 0x21等)。

期望结果：
1.前置检查检测到en_i=0；
2.返回STS_DISABLED(0x08)；
3.不发起CSR/AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_010, TP_033"
    },
    {
        "tc_id": "TC_008",
        "tc_name": "normal_cmd_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01；
2.外部CSR File就绪，AHB从设备就绪。

输入激励：
1.发送WR_CSR(0x10)、RD_CSR(0x11)、AHB_WR32(0x20)、AHB_RD32(0x21)命令。

期望结果：
1.前置检查通过；
2.正常执行命令并返回正确状态码和数据。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_011"
    },
    {
        "tc_id": "TC_009",
        "tc_name": "lane_1bit_test",
        "tc_description": """配置条件：
1.lane_mode_i=2'b00(1-bit模式), test_mode_i=1, en_i=1。

输入激励：
1.发送WR_CSR/AHB_RD32命令帧；
2.观测pdi_i[0]和pdo_o[0]数据流。

期望结果：
1.每拍收发1bit(pdi_i[0])；
2.帧接收周期为帧长bit数（WR_CSR 48拍，AHB_RD32 40拍）；
3.命令执行正确；
4.pdi_i[3:1]被忽略。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_012"
    },
    {
        "tc_id": "TC_010",
        "tc_name": "lane_4bit_test",
        "tc_description": """配置条件：
1.lane_mode_i=2'b01(4-bit模式), test_mode_i=1, en_i=1。

输入激励：
1.发送WR_CSR/AHB_RD32命令帧；
2.观测pdi_i[3:0]和pdo_o[3:0]数据流。

期望结果：
1.每拍收发4bit(pdi_i[3:0])；
2.帧接收周期为帧长/4（WR_CSR 12拍，AHB_RD32 10拍）；
3.命令执行正确，MSB-first顺序。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_013"
    },
    {
        "tc_id": "TC_011",
        "tc_name": "pcs_frame_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.pcs_n_i拉低开启事务；
2.发送完整命令帧；
3.pcs_n_i拉高结束事务。

期望结果：
1.pcs_n_i=1时空闲；
2.pcs_n_i=0时开启帧接收；
3.pcs_n_i拉高时结束事务。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_014"
    },
    {
        "tc_id": "TC_012",
        "tc_name": "pdi_lane_mode_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1。

输入激励：
1.1-bit模式(lane_mode_i=2'b00)使用pdi_i[0]发送命令；
2.4-bit模式(lane_mode_i=2'b01)使用pdi_i[3:0]发送命令。

期望结果：
1.1-bit模式仅bit0有效，其余位忽略；
2.4-bit模式全部4位有效；
3.MSB-first顺序传输。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_015"
    },
    {
        "tc_id": "TC_013",
        "tc_name": "pdo_oe_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送命令并等待命令执行完成；
2.观测pdo_o和pdo_oe_o信号。

期望结果：
1.响应阶段pdo_oe_o=1，模块驱动pdo_o输出数据；
2.非发送阶段pdo_oe_o=0，pdo_o值无意义；
3.半双工，主机和模块不同时驱动。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_016"
    },
    {
        "tc_id": "TC_014",
        "tc_name": "frame_format_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送WR_CSR(48bit)命令帧；
2.发送RD_CSR(16bit)命令帧；
3.发送AHB_WR32(72bit)命令帧；
4.发送AHB_RD32(40bit)命令帧。

期望结果：
1.WR_CSR接收48bit后产生frame_valid，响应8bit状态码；
2.RD_CSR接收16bit后产生frame_valid，响应40bit；
3.AHB_WR32接收72bit后产生frame_valid，响应8bit；
4.AHB_RD32接收40bit后产生frame_valid，响应40bit。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_017, TP_018, TP_019, TP_020"
    },
    {
        "tc_id": "TC_015",
        "tc_name": "frame_abort_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送WR_CSR帧，pcs_n_i在rx_count<expected_rx_bits时提前拉高。

期望结果：
1.产生frame_abort，返回STS_FRAME_ERR(0x01)；
2.不发起CSR/AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_021, TP_030"
    },
    {
        "tc_id": "TC_016",
        "tc_name": "turnaround_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送命令执行完成后观测请求→响应之间的时序。

期望结果：
1.请求阶段与响应阶段之间固定插入1个clk_i周期turnaround；
2.turnaround期间pdo_oe_o=0；
3.TX阶段pdo_oe_o=1。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_022"
    },
    {
        "tc_id": "TC_017",
        "tc_name": "opcode_decode_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送opcode为0x10(WR_CSR)的命令帧；
2.发送opcode为0x11(RD_CSR)的命令帧；
3.发送opcode为0x20(AHB_WR32)的命令帧；
4.发送opcode为0x21(AHB_RD32)的命令帧。

期望结果：
1.前端收满8bit后锁存opcode；
2.根据opcode确定expected_rx_bits；
3.正确发起对应类型任务。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_023"
    },
    {
        "tc_id": "TC_018",
        "tc_name": "bad_opcode_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送opcode为0xFF、0x00、0x30等非法值的命令帧。

期望结果：
1.前置检查检测到非法opcode；
2.返回STS_BAD_OPCODE(0x02)；
3.不发起CSR/AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_024, TP_031"
    },
    {
        "tc_id": "TC_019",
        "tc_name": "ctrl_reg_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1。

输入激励：
1.通过WR_CSR命令配置CTRL.EN=1；
2.配置CTRL.LANE_MODE=00；
3.配置CTRL.LANE_MODE=01；
4.配置CTRL.SOFT_RST=1。

期望结果：
1.LANE_MODE=00对应1-bit模式，01对应4-bit模式；
2.SOFT_RST写1触发协议上下文清零并恢复默认lane模式。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_025"
    },
    {
        "tc_id": "TC_020",
        "tc_name": "lane_switch_violation_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01初始值；
2.pcs_n_i=0(事务执行期间)。

输入激励：
1.在事务执行期间改变lane_mode_i（如从01变00）。

期望结果：
1.移位宽度bpc立即改变；
2.帧数据错位；
3.模块不检测此违规；
4.可能误触发STS_BAD_OPCODE或STS_FRAME_ERR。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_026"
    },
    {
        "tc_id": "TC_021",
        "tc_name": "lane_switch_valid_test",
        "tc_description": """配置条件：
1.pcs_n_i=1(空闲态)。

输入激励：
1.在空闲态切换lane_mode_i；
2.然后发起新事务。

期望结果：
1.新事务使用更新后的lane_mode；
2.帧数据正确，无错位。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_027"
    },
    {
        "tc_id": "TC_022",
        "tc_name": "no_irq_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1。

输入激励：
1.触发各类错误事件(帧中止、非法opcode、AHB错误等)。

期望结果：
1.MVP版本不实现独立中断输出；
2.无IRQ信号拉高；
3.错误信息通过STATUS寄存器和LAST_ERR寄存器查询。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_028"
    },
    {
        "tc_id": "TC_023",
        "tc_name": "polling_status_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1。

输入激励：
1.连续发送多条错误命令。

期望结果：
1.每次错误状态通过响应帧8bit状态码直接返回给ATE；
2.前一条错误信息被新命令覆盖；
3.ATE应每条命令后检查状态码。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_029"
    },
    {
        "tc_id": "TC_024",
        "tc_name": "align_err_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发送AHB_WR32/AHB_RD32命令，addr[1:0]=2'b01/10/11（非对齐地址）。

期望结果：
1.返回STS_ALIGN_ERR(0x20)；
2.不发起AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_035"
    },
    {
        "tc_id": "TC_025",
        "tc_name": "ahb_hresp_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发起AHB命令；
2.从设备返回hresp_i=1。

期望结果：
1.STATE_WAIT检测到hresp_i=1，转STATE_ERR；
2.返回STS_AHB_ERR(0x40)。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_036"
    },
    {
        "tc_id": "TC_026",
        "tc_name": "ahb_timeout_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发起AHB命令；
2.hready_i持续为0超过256周期。

期望结果：
1.9-bit超时计数器在STATE_WAIT递增至255(BUS_TIMEOUT_CYCLES-1)；
2.触发STATE_ERR；
3.返回STS_AHB_ERR(0x40)。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_037, TP_047"
    },
    {
        "tc_id": "TC_027",
        "tc_name": "error_priority_test",
        "tc_description": """配置条件：
1.test_mode_i=0, en_i=0；
2.addr非对齐。

输入激励：
1.发送同时满足多个前置错误条件的命令帧。

期望结果：
1.按固定优先级链仅报告最高优先级错误：
FRAME_ERR(0x01)>BAD_OPCODE(0x02)>NOT_IN_TEST(0x04)>DISABLED(0x08)>BAD_REG(0x10)>ALIGN_ERR(0x20)；
2.仅返回一个状态码。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_038"
    },
    {
        "tc_id": "TC_028",
        "tc_name": "ahb_err_vs_prechk_test",
        "tc_description": """配置条件：
1.AHB命令前置检查全部通过。

输入激励：
1.命令执行期间AHB返回hresp_i=1。

期望结果：
1.AHB错误与前置错误互斥；
2.前置检查通过后才可能发生AHB错误；
3.返回STS_AHB_ERR(0x40)。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_039"
    },
    {
        "tc_id": "TC_029",
        "tc_name": "idle_power_test",
        "tc_description": """配置条件：
1.模块空闲态(pcs_n_i=1)。

输入激励：
1.观测接收/发送移位寄存器和超时计数器状态。

期望结果：
1.接收移位寄存器不更新；
2.发送移位寄存器不翻转；
3.超时计数器不工作。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_040"
    },
    {
        "tc_id": "TC_030",
        "tc_name": "ahb_idle_test",
        "tc_description": """配置条件：
1.test_mode_i=0或无有效任务。

输入激励：
1.观测AHB输出端口。

期望结果：
1.htrans_o保持IDLE(2'b00)；
2.无AHB总线翻转。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_041"
    },
    {
        "tc_id": "TC_031",
        "tc_name": "timeout_counter_test",
        "tc_description": """配置条件：
1.模块处于STATE_WAIT(AHB等待态)。

输入激励：
1.观测超时计数器。

期望结果：
1.仅在STATE_WAIT期间超时计数器递增；
2.STATE_REQ时清零；
3.IDLE态不工作。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_042"
    },
    {
        "tc_id": "TC_032",
        "tc_name": "latency_4bit_test",
        "tc_description": """配置条件：
1.4-bit模式, hready_i=1(零等待), test_mode_i=1, en_i=1。

输入激励：
1.发送AHB_RD32命令，测量端到端延时；
2.发送AHB_WR32命令，测量端到端延时。

期望结果：
1.AHB_RD32：请求接收10cyc+译码1~2cyc+AHB返回1~N cyc+turnaround 1cyc+响应发送10cyc≈23~24 cycles最小延时；
2.AHB_WR32：请求接收18cyc+执行2cyc+turnaround 1cyc+响应发送2cyc≈23 cycles最小延时。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_043, TP_044"
    },
    {
        "tc_id": "TC_033",
        "tc_name": "latency_1bit_test",
        "tc_description": """配置条件：
1.1-bit模式, hready_i=1, test_mode_i=1, en_i=1。

输入激励：
1.发送AHB_RD32命令，测量端到端延时；
2.发送WR_CSR命令，测量端到端延时。

期望结果：
1.AHB_RD32：请求接收40cyc+译码1~2cyc+AHB返回1~N cyc+turnaround 1cyc+响应发送40cyc≈83~84 cycles最小延时；
2.WR_CSR：请求接收48cyc+执行~6cyc+turnaround 1cyc+响应发送8cyc≈63 cycles最小延时。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_045, TP_046"
    },
    {
        "tc_id": "TC_034",
        "tc_name": "dfx_test",
        "tc_description": """配置条件：
1.仿真/调试环境。

输入激励：
1.运行各类命令；
2.观测内部调试点。

期望结果：
1.可观测front_state、back_state、opcode、addr、wdata、rdata、status_code、rx_count、tx_count、lane_mode等信号；
2.便于波形定位和故障复现。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_048"
    },
    {
        "tc_id": "TC_035",
        "tc_name": "csr_not_in_ahb_map_test",
        "tc_description": """配置条件：
1.SoC集成环境。

输入激励：
1.检查模块CSR是否出现在AHB memory map中。

期望结果：
1.模块CSR不进入SoC AHB memory map；
2.仅通过协议命令(WR_CSR/RD_CSR)访问。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_049"
    },
    {
        "tc_id": "TC_036",
        "tc_name": "ahb_addr_space_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01。

输入激励：
1.发起AHB_WR32/AHB_RD32命令访问不同地址。

期望结果：
1.AHB Master采用32bit地址空间和word(32-bit)访问粒度；
2.具体可达目标地址范围由SoC顶层统一约束。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_050"
    },
    {
        "tc_id": "TC_037",
        "tc_name": "ahb_write_phase_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01；
2.发起AHB写命令。

输入激励：
1.观测AHB 2-phase流水时序。

期望结果：
1.T1(STATE_REQ)驱动haddr_o/hwrite_o/htrans_o=NONSEQ(2'b10)；
2.T2(STATE_WAIT)htrans_o回到IDLE，驱动hwdata_o；
3.haddr与hwdata错开1拍。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_051"
    },
    {
        "tc_id": "TC_038",
        "tc_name": "ahb_read_phase_test",
        "tc_description": """配置条件：
1.test_mode_i=1, en_i=1, lane_mode_i=2'b01；
2.发起AHB读命令。

输入激励：
1.观测AHB 2-phase流水时序。

期望结果：
1.T1(STATE_REQ)驱动haddr_o/htrans_o=NONSEQ；
2.T2(STATE_WAIT)htrans_o=IDLE；
3.hready_i=1时采样hrdata_i。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_052"
    },
    {
        "tc_id": "TC_039",
        "tc_name": "ahb_fixed_signal_test",
        "tc_description": """配置条件：
1.发起AHB命令。

输入激励：
1.检查hsize_o和hburst_o输出。

期望结果：
1.hsize_o固定输出3'b010(WORD)；
2.hburst_o固定输出3'b000(SINGLE)；
3.不支持byte/halfword与burst传输。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_053"
    },
    {
        "tc_id": "TC_040",
        "tc_name": "ahb_htrans_test",
        "tc_description": """配置条件：
1.AHB命令执行期间。

输入激励：
1.观测htrans_o在不同FSM状态下的值。

期望结果：
1.htrans_o仅在STATE_REQ(地址相)驱动NONSEQ(2'b10)持续1周期；
2.其余时刻均为IDLE(2'b00)。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_054"
    },
    {
        "tc_id": "TC_041",
        "tc_name": "ahb_err_recovery_test",
        "tc_description": """配置条件：
1.AHB错误(STATE_ERR)发生后。

输入激励：
1.观测FSM状态恢复。

期望结果：
1.STATE_ERR下一拍自动转STATE_IDLE；
2.AHB输出恢复htrans=IDLE, haddr=0；
3.模块可立即接受新请求，无需外部干预。

coverage check点：
直接用例覆盖，不收功能覆盖率""",
        "note": "覆盖TP_055"
    },
]

# TP to Checker/Testcase mapping
tp_mapping = {
    "TP_001": ("CHK_001", "TC_001"),
    "TP_002": ("CHK_001", "TC_001"),
    "TP_003": ("CHK_002", "TC_002"),
    "TP_004": ("CHK_002", "TC_002"),
    "TP_005": ("CHK_003", "TC_002"),
    "TP_006": ("CHK_004", "TC_003"),
    "TP_007": ("CHK_005", "TC_004"),
    "TP_008": ("CHK_006", "TC_005"),
    "TP_009": ("CHK_007", "TC_006"),
    "TP_010": ("CHK_008", "TC_007"),
    "TP_011": ("CHK_009", "TC_008"),
    "TP_012": ("CHK_010", "TC_009"),
    "TP_013": ("CHK_011", "TC_010"),
    "TP_014": ("CHK_012", "TC_011"),
    "TP_015": ("CHK_013", "TC_012"),
    "TP_016": ("CHK_014", "TC_013"),
    "TP_017": ("CHK_015", "TC_014"),
    "TP_018": ("CHK_016", "TC_014"),
    "TP_019": ("CHK_017", "TC_014"),
    "TP_020": ("CHK_018", "TC_014"),
    "TP_021": ("CHK_019", "TC_015"),
    "TP_022": ("CHK_020", "TC_016"),
    "TP_023": ("CHK_021", "TC_017"),
    "TP_024": ("CHK_022", "TC_018"),
    "TP_025": ("CHK_023", "TC_019"),
    "TP_026": ("CHK_024", "TC_020"),
    "TP_027": ("CHK_025", "TC_021"),
    "TP_028": ("CHK_026", "TC_022"),
    "TP_029": ("CHK_027", "TC_023"),
    "TP_030": ("CHK_019", "TC_015"),
    "TP_031": ("CHK_022", "TC_018"),
    "TP_032": ("CHK_007", "TC_006"),
    "TP_033": ("CHK_008", "TC_007"),
    "TP_034": ("CHK_006", "TC_005"),
    "TP_035": ("CHK_028", "TC_024"),
    "TP_036": ("CHK_029", "TC_025"),
    "TP_037": ("CHK_030", "TC_026"),
    "TP_038": ("CHK_031", "TC_027"),
    "TP_039": ("CHK_032", "TC_028"),
    "TP_040": ("CHK_033", "TC_029"),
    "TP_041": ("CHK_034", "TC_030"),
    "TP_042": ("CHK_035", "TC_031"),
    "TP_043": ("CHK_036", "TC_032"),
    "TP_044": ("CHK_037", "TC_032"),
    "TP_045": ("CHK_038", "TC_033"),
    "TP_046": ("CHK_039", "TC_033"),
    "TP_047": ("CHK_030", "TC_026"),
    "TP_048": ("CHK_040", "TC_034"),
    "TP_049": ("CHK_041", "TC_035"),
    "TP_050": ("CHK_042", "TC_036"),
    "TP_051": ("CHK_043", "TC_037"),
    "TP_052": ("CHK_044", "TC_038"),
    "TP_053": ("CHK_045", "TC_039"),
    "TP_054": ("CHK_046", "TC_040"),
    "TP_055": ("CHK_047", "TC_041"),
}

def write_checkers(wb, checkers):
    """Write checkers to Checker List sheet"""
    ws = wb['Checker List']

    # First, unmerge the instruction cells
    merged_to_remove = []
    for merged in ws.merged_cells.ranges:
        if merged.min_row >= 16:  # Instruction section
            merged_to_remove.append(merged)
    for merged in merged_to_remove:
        ws.unmerge_cells(str(merged))

    # Clear all existing content from row 3 onwards
    for row in range(3, ws.max_row + 1):
        for col in range(1, 5):
            ws.cell(row=row, column=col).value = None

    # Calculate where instruction section should go
    instruction_start = 3 + len(checkers) + 1  # Leave 1 blank row

    # Write checkers starting from row 3
    for i, chk in enumerate(checkers):
        row = 3 + i
        ws.cell(row=row, column=1, value=chk['chk_id'])
        ws.cell(row=row, column=2, value=chk['chk_name'])
        ws.cell(row=row, column=3, value=chk['chk_description'])
        ws.cell(row=row, column=4, value=chk.get('note', ''))

        # Apply style
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            cell.font = Font(name='宋体', size=10)

    # Write back instruction section
    # Row 1: Header (already exists)
    # Row 2: Column headers (already exists)
    # Instruction rows
    ws.cell(row=instruction_start, column=1, value='填写要求')
    ws.merge_cells(start_row=instruction_start, start_column=1, end_row=instruction_start, end_column=4)
    ws.cell(row=instruction_start, column=1).font = Font(bold=True)
    ws.cell(row=instruction_start, column=1).alignment = Alignment(horizontal='center')

    ws.cell(row=instruction_start+1, column=1, value='CHK Name')
    ws.cell(row=instruction_start+1, column=2, value='如果是SVA checker，需填写SVA property名字')
    ws.merge_cells(start_row=instruction_start+1, start_column=2, end_row=instruction_start+1, end_column=4)

    ws.cell(row=instruction_start+2, column=1, value='CHK描述')
    ws.cell(row=instruction_start+2, column=2, value='1、需要定性+定量描述，需具体到check的信号、取值 \n2、和DV SPEC中Checker方案描述的区别 — RTM中描述check的内容，DV SPEC中描述checker的实现方案(例如是通过SVA实现还是scoreboard实时数据比对，还是文件对比)')
    ws.merge_cells(start_row=instruction_start+2, start_column=2, end_row=instruction_start+2, end_column=4)

    # Apply style to instruction rows
    for row_offset in range(3):
        row = instruction_start + row_offset
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            cell.font = Font(name='宋体', size=10)

def write_testcases(wb, testcases):
    """Write testcases to DV Testcase List sheet"""
    ws = wb['DV Testcase List']

    # Clear existing testcase entries (row 3 onwards)
    for row in range(3, ws.max_row + 1):
        for col in range(1, 5):
            ws.cell(row=row, column=col).value = None

    # Start writing from row 3
    start_row = 3

    for i, tc in enumerate(testcases):
        row = start_row + i
        ws.cell(row=row, column=1, value=tc['tc_id'])
        ws.cell(row=row, column=2, value=tc['tc_name'])
        ws.cell(row=row, column=3, value=tc['tc_description'])
        ws.cell(row=row, column=4, value=tc.get('note', ''))

        # Copy style from template row
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

def link_tp_to_checker_testcase(wb, tp_mapping):
    """Link TP to checker and testcase in FL-TP sheet"""
    ws = wb['FL-TP']

    for row in range(3, ws.max_row + 1):
        tp_id = ws.cell(row=row, column=3).value
        if tp_id and tp_id in tp_mapping:
            checker_id, testcase_id = tp_mapping[tp_id]
            ws.cell(row=row, column=5, value=checker_id)
            ws.cell(row=row, column=6, value=testcase_id)

# Main execution
print("Writing Checker List...")
write_checkers(wb, checkers)

print("Writing DV Testcase List...")
write_testcases(wb, testcases)

print("Linking TP to Checker/Testcase...")
link_tp_to_checker_testcase(wb, tp_mapping)

print(f"Saving to {output_path}...")
wb.save(output_path)

print("RTM generation completed!")
print(f"Generated {len(checkers)} Checkers and {len(testcases)} Testcases")
print(f"Covered {len(tp_mapping)} Test Points")
