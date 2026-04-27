#!/usr/bin/env python3
"""
APLC-Lite RTM Generator
Generates Checker List, DV Testcase List, and FL-TP links
for the APLC-Lite v2.2 verification module.
"""

import sys
import os

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    '.claude/skills/RTM_TP2TC_skills/scripts')
sys.path.insert(0, SCRIPT_DIR)

from rtm_utils import (
    add_checker_to_rtm,
    add_testcase_to_rtm,
    link_tp_to_checker_testcase,
    save_rtm
)
import openpyxl


# ============================================================
# Checker Definitions (20 checkers)
# ============================================================

CHECKERS = [
    # ---- CHK_APLC_001 ----
    (
        "CHK_APLC_001",
        "clk_freq_checker",
        "检查clk_i时钟域和频率正确性："
        "1.clk_i为单时钟域设计，所有内部逻辑（SLC_CAXIS/SLC_DPCHK/SLC_SAXIS协议侧、SLC_SAXIM AHBM侧）在clk_i上升沿同步工作，无异步时钟域交叉；"
        "2.目标频率100MHz，时钟周期10ns，周期误差在±1%内（9.9ns~10.1ns）；"
        "3.AHB后端与协议侧共用clk_i同域工作，htrans_o/hburst_o/haddr_o均在clk_i上升沿驱动输出；"
        "4.rst_n_i异步复位同步释放后，模块在clk_i上升沿正常采样所有输入（pdi_i[15:0]、pcs_n_i、en_i、lane_mode_i[1:0]、test_mode_i）。",
        None,
        ["TP_001", "TP_002"]
    ),
    # ---- CHK_APLC_002 ----
    (
        "CHK_APLC_002",
        "reset_state_checker",
        "检查rst_ni异步复位及同步释放后模块状态正确性："
        "1.复位后所有状态机回到IDLE态：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；"
        "2.复位后所有输出deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0；"
        "3.pdo_o[15:0]=16'b0，RX/TX FIFO清空：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "4.CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)，LAST_ERR=0x00，BURST_CNT=0；"
        "5.Burst中途复位：axi_state=AXI_BURST时拉低rst_ni，所有FSM立即复位至IDLE，FIFO强制清空，AHB输出回IDLE（htrans_o=2'b00）。",
        None,
        ["TP_003", "TP_004"]
    ),
    # ---- CHK_APLC_003 ----
    (
        "CHK_APLC_003",
        "csr_access_checker",
        "检查CSR接口读写时序与寄存器属性正确性："
        "1.CSR写操作：csr_wr_en_o为单周期脉冲，同一周期内csr_addr_o[7:0]和csr_wdata_o[31:0]有效，外部CSR File在该clk_i上升沿采样完成写入；"
        "2.CSR读操作：csr_rd_en_o为单周期脉冲，外部CSR File在下一周期将读数据稳定在csr_rdata_i[31:0]，模块在该周期采样（1 cycle读延迟）；"
        "3.CSR有效地址范围0x00~0x3F，reg_addr>=0x40的访问在前置检查阶段即被拒绝返回STS_BAD_REG(0x10)，不出现csr_rd_en_o/csr_wr_en_o脉冲；"
        "4.寄存器属性正确：VERSION(0x00,RO)写无效，CTRL(0x04,RW)写后读回一致，STATUS(0x08,RO)写无效，LAST_ERR(0x0C,RO)写无效，BURST_CNT(0x10,WC)写1清零；"
        "5.BURST_CNT(0x10)写入1后计数归零，写入0不影响当前计数值。",
        None,
        ["TP_005", "TP_006", "TP_007"]
    ),
    # ---- CHK_APLC_004 ----
    (
        "CHK_APLC_004",
        "mode_gate_checker",
        "检查test_mode_i与en_i前置门控条件："
        "1.test_mode_i=0时：SLC_DPCHK在frame_valid时刻采样test_mode_i=0，所有命令返回STS_NOT_IN_TEST(0x04)，不发起任何CSR/AHB访问（无csr_wr_en_o/csr_rd_en_o脉冲，无htrans_o=NONSEQ）；"
        "2.en_i=0时：所有命令返回STS_DISABLED(0x08)，不发起任何CSR/AHB访问；"
        "3.test_mode_i=0且en_i=0时：按优先级链返回STS_NOT_IN_TEST(0x04)（优先于STS_DISABLED(0x08)）；"
        "4.两种拒绝场景下，前端FSM仍走IDLE→ISSUE→TA→TX路径返回错误状态码，pdo_oe_o在TX态=1；"
        "5.STATUS[5]=IN_TEST_MODE镜像test_mode_i当前值。",
        None,
        ["TP_008", "TP_009"]
    ),
    # ---- CHK_APLC_005 ----
    (
        "CHK_APLC_005",
        "lane_mode_checker",
        "检查lane_mode_i[1:0]对应的通道宽度和数据信号使用正确性："
        "1.lane_mode_i=2'b00(1-bit模式)：仅使用pdi_i[0]/pdo_o[0]，pdi_i[15:1]忽略，pdo_o[15:1]驱动为0；WR_CSR帧48bit需48个周期接收；"
        "2.lane_mode_i=2'b01(4-bit模式)：使用pdi_i[3:0]/pdo_o[3:0]；WR_CSR帧48bit需12个周期接收；"
        "3.lane_mode_i=2'b10(8-bit模式)：使用pdi_i[7:0]/pdo_o[7:0]；WR_CSR帧48bit需6个周期接收；"
        "4.lane_mode_i=2'b11(16-bit模式)：使用pdi_i[15:0]/pdo_o[15:0]；WR_CSR帧48bit需3个周期接收；"
        "5.SLC_CAXIS按lane_mode_i计算每拍移位宽度bpc(bits per clock)，rx_count_q按bpc步进递增。",
        None,
        ["TP_010", "TP_011", "TP_012", "TP_013"]
    ),
    # ---- CHK_APLC_006 ----
    (
        "CHK_APLC_006",
        "frame_rx_checker",
        "检查帧接收过程和FIFO流控正确性："
        "1.pcs_ni拉低后模块开始接收，rx_count_q按bpc步进；rx_count>=expected_rx_bits时产生frame_valid（寄存输出，延迟1 cycle）；"
        "2.RXFIFO 32×32bit：Burst写命令payload每凑够32bit推入SLC_RXFIFO，非Burst命令头走fast path不经FIFO；"
        "3.rxfifo_full_o=1时SLC_CAXIS暂停rx_shift_en和rxfifo_wr_en，后端BURST_LOOP通过rxfifo_rd_en drain后rxfifo_full_o清零恢复接收；"
        "4.TXFIFO 32×33bit：Burst读命令返回数据每beat(32bit data+1bit last)推入SLC_TXFIFO，txfifo_empty_o=1时SLC_SAXIS暂停移位但pdo_oe_o保持高电平；"
        "5.RX/TX FIFO复位后清空：rxfifo_empty_o=1，txfifo_empty_o=1，rxfifo_cnt[5:0]=0，txfifo_cnt[5:0]=0。",
        None,
        ["TP_014", "TP_015", "TP_047", "TP_048"]
    ),
    # ---- CHK_APLC_007 ----
    (
        "CHK_APLC_007",
        "frame_format_checker",
        "检查6类命令帧格式与turnaround时序正确性："
        "1.WR_CSR(0x10)帧：opcode(8)+reg_addr(8)+wdata(32)=48bit请求/8bit状态响应；RD_CSR(0x11)帧：opcode(8)+reg_addr(8)=16bit请求/40bit(状态+数据)响应；"
        "2.AHB_WR32(0x20)帧：opcode(8)+addr(32)+wdata(32)=72bit请求/8bit状态响应；AHB_RD32(0x21)帧：opcode(8)+addr(32)=40bit请求/40bit(状态+数据)响应；"
        "3.请求与响应之间固定1个clk_i周期turnaround（TA态），pdo_oe_o在TX态=1，在TA态=0；"
        "4.Burst读响应8+32·burst_len bit，beat间无额外turnaround，pdo_oe_o连续有效直至最后beat完成；"
        "5.所有帧字段按MSB-first传输，pdo_oe_o仅在TX/TX_BURST态驱动为1。",
        None,
        ["TP_016", "TP_017", "TP_018"]
    ),
    # ---- CHK_APLC_008 ----
    (
        "CHK_APLC_008",
        "burst_frame_checker",
        "检查Burst命令帧两段式解析与expected_rx_bits修正正确性："
        "1.Burst header格式：{opcode[7:0], burst_len[4:0], rsvd[2:0], addr[31:0]}共48bit；"
        "2.前8bit锁定opcode_latched_q确定初始expected_rx_bits；收满16bit后提取burst_len_latched_q[4:0]；"
        "3.AHB_WR_BURST(0x22)修正expected_rx_bits为48+32·burst_len bit；AHB_RD_BURST(0x23)保持48bit；"
        "4.Burst写payload每32bit beat直接写入SLC_RXFIFO，不经过rx_shift_q[79:0]；"
        "5.burst_len合法值{1,4,8,16}：burst_len=1退化为SINGLE(SLC_SAXIM hburst=3'b000)。",
        None,
        ["TP_019", "TP_020", "TP_021"]
    ),
    # ---- CHK_APLC_009 ----
    (
        "CHK_APLC_009",
        "opcode_decode_checker",
        "检查6种合法opcode解码与非法opcode拒绝："
        "1.合法opcode：0x10(WR_CSR)、0x11(RD_CSR)、0x20(AHB_WR32)、0x21(AHB_RD32)、0x22(AHB_WR_BURST)、0x23(AHB_RD_BURST)，SLC_CCMD正确译码为td_cmd_type；"
        "2.非法opcode（不在{0x10,0x11,0x20,0x21,0x22,0x23}中）返回STS_BAD_OPCODE(0x02)，不发起CSR/AHB访问；"
        "3.CSR类opcode(0x10/0x11)：走SLC_DPIPE CSR通道，驱动csr_wr_en_o/csr_rd_en_o；"
        "4.AHB类opcode(0x20/0x21/0x22/0x23)：走SLC_SAXIM AHB Master通道；"
        "5.Burst opcode(0x22/0x23)：td_burst_len[4:0]和td_hburst[2:0]由SLC_CCMD从burst_len字段编码生成。",
        None,
        ["TP_022", "TP_023"]
    ),
    # ---- CHK_APLC_010 ----
    (
        "CHK_APLC_010",
        "ctrl_config_checker",
        "检查CTRL寄存器配置与lane_mode切换约束："
        "1.CTRL(0x04,RW)字段：EN(bit0)、LANE_MODE[1:0](bits[2:1],00=1-bit/01=4-bit/10=8-bit/11=16-bit)、SOFT_RST(bit3)；"
        "2.SOFT_RST写1触发协议上下文清零并恢复默认lane模式(LANE_MODE=2'b00)，等价于软复位（不清FIFO）；"
        "3.lane_mode_i[1:0]在事务执行期间（pcs_ni=0期间）必须保持稳定：SLC_CAXIS/SLC_SAXIS连续组合采样lane_mode_i计算bpc；"
        "4.事务中途切换lane_mode_i导致移位寄存器步进宽度立即改变，帧数据错位，可能触发STS_BAD_OPCODE(0x02)或STS_FRAME_ERR(0x01)；"
        "5.lane_mode_i切换仅允许在pcs_ni=1(空闲态)期间执行，需等待≥2 cycle同步后开始新事务。",
        None,
        ["TP_024", "TP_025"]
    ),
    # ---- CHK_APLC_011 ----
    (
        "CHK_APLC_011",
        "status_poll_checker",
        "检查STATUS寄存器位域与轮询式状态报告正确性："
        "1.STATUS[0]=BUSY：当前有事务执行时为1；STATUS[1]=RESP_VALID：最近响应有效时为1；STATUS[2]=CMD_ERR(sticky)：命令错误置位；STATUS[3]=BUS_ERR(sticky)：总线错误置位；"
        "2.STATUS[4]=FRAME_ERR(sticky)：帧错误置位；STATUS[5]=IN_TEST_MODE：镜像test_mode_i；STATUS[6]=OUT_EN：镜像pdo_oe_o；STATUS[7]=BURST_ERR(sticky)：Burst专有错误置位；"
        "3.LAST_ERR[7:0]保存最近一次错误码（sticky），新命令开始后覆盖前一条错误信息；"
        "4.v2.2不实现独立中断输出端口(IRQ)，所有错误与完成状态通过STATUS和LAST_ERR寄存器查询，ATE采用轮询方式获取；"
        "5.sticky位由软件通过WC（写1清零）语义清除，BURST_CNT(0x10)同为WC属性。",
        None,
        ["TP_026"]
    ),
    # ---- CHK_APLC_012 ----
    (
        "CHK_APLC_012",
        "precheck_priority_checker",
        "检查前置错误优先级链正确性："
        "1.固定优先级链(高→低)：STS_FRAME_ERR(0x01) > STS_BAD_OPCODE(0x02) > STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08) > STS_BAD_REG(0x10) > STS_ALIGN_ERR(0x20) > STS_BAD_BURST(0x80) > STS_BURST_BOUND(0x81)；"
        "2.任何前置错误均在发起CSR/AHB访问前收敛：不产生csr_wr_en_o/csr_rd_en_o脉冲，不产生htrans_o=NONSEQ；"
        "3.STS_FRAME_ERR(0x01)：pcs_ni在rx_count<expected_rx_bits时提前拉高且opcode已锁存触发frame_abort；"
        "4.STS_ALIGN_ERR(0x20)：AHB命令addr[1:0]!=2'b00时返回，不发起AHB访问；"
        "5.多前置错误同时成立时，仅报告最高优先级单个错误，不存在多错误同时上报。",
        None,
        ["TP_027", "TP_028", "TP_029"]
    ),
    # ---- CHK_APLC_013 ----
    (
        "CHK_APLC_013",
        "ahb_exec_err_checker",
        "检查AHB执行期错误检测与恢复正确性："
        "1.STS_AHB_ERR(0x40)不在前置优先级链中：仅在前置检查全部通过后、AHB事务实际执行期间发生，与前置错误互斥；"
        "2.hresp_i=1时SLC_SAXIM跳转AXI_ERR，返回STS_AHB_ERR(0x40)；Burst内任一beat hresp_i=1立即中止burst剩余beat，进入AXI_ERR；"
        "3.hready_i持续为0超过BUS_TIMEOUT_CYCLES(256)周期（9-bit计数器从0计至255）触发超时，返回STS_AHB_ERR(0x40)；"
        "4.AXI_ERR下一拍自动恢复AXI_IDLE，AHB输出回到空闲值（htrans_o=IDLE, hburst_o=SINGLE, haddr_o=0），RX/TX FIFO强制drain至empty；"
        "5.Burst中途hresp错误时，TXFIFO中已push的部分beat数据仍发出，ATE收到的响应数据流可能短于burst_len。",
        None,
        ["TP_030", "TP_031"]
    ),
    # ---- CHK_APLC_014 ----
    (
        "CHK_APLC_014",
        "burst_param_checker",
        "检查Burst参数前置检查(SLC_DPCHK)正确性："
        "1.STS_BAD_BURST(0x80)：burst_len不在{1,4,8,16}中时返回，不发起任何AHB访问；burst_len=1退化为SINGLE等价于AHB_WR32/AHB_RD32；"
        "2.STS_BURST_BOUND(0x81)：addr[9:0]+4·(burst_len-1)>=1024时返回，不发起任何AHB访问；"
        "3.两项检查均在SLC_DPCHK前置阶段完成，位于错误优先级链中ALIGN_ERR(0x20)之后，与AHB_ERR(0x40)互斥；"
        "4.Burst中途AHB错误：INCR8读第4 beat时hresp_i=1，axi_state跳转AXI_ERR，剩余beat取消，返回STS_AHB_ERR(0x40)；"
        "5.Burst前置错误(BAD_BURST/BURST_BOUND)在Burst header接收完成时一次性判定，不发起任何AHB beat。",
        None,
        ["TP_032", "TP_033", "TP_034"]
    ),
    # ---- CHK_APLC_015 ----
    (
        "CHK_APLC_015",
        "low_power_checker",
        "检查空闲态/反压态门控时序和功耗指标："
        "1.pcs_ni=1时RX/TX移位寄存器不更新，非TX/TA态发送移位寄存器不翻转；超时计数器仅在AXI_WAIT态激活；"
        "2.RXFIFO空时后端BURST_LOOP写数据通道不翻转（门控条件：rxfifo_empty_o=1）；TXFIFO空时前端TX序列化逻辑不启动（门控条件：txfifo_empty_o=1）；"
        "3.rxfifo_full_o=1期间RX路径暂停（rx_shift_en=0），后端消费时门控释放；Burst期间hburst_o在整个burst保持稳定不逐拍翻转；"
        "4.量化目标：时钟门控覆盖率≥80%，空闲功耗≤10%满负荷功耗，FIFO empty态功耗≤5%Burst满速态；"
        "5.test_mode_i=0或无有效任务时AHB输出保持IDLE（htrans_o=IDLE, hburst_o=SINGLE, haddr_o=0）。",
        None,
        ["TP_035", "TP_036"]
    ),
    # ---- CHK_APLC_016 ----
    (
        "CHK_APLC_016",
        "throughput_checker",
        "检查Burst有效吞吐与端到端延时正确性："
        "1.AHB_WR_BURST×16(16-bit lane)：header 48bit+payload 512bit=560bit(35 cycles) + AHB INCR16写16 cycles + turnaround 1 cycle + 响应8bit(1 cycle)，总计54~56 cycles/64B，有效吞吐约116MB/s；"
        "2.AHB_RD_BURST×16(16-bit lane)：请求48bit(3 cycles) + AHB执行17 cycles + turnaround 1 cycle + 响应520bit(33 cycles)，总计54 cycles/64B，有效吞吐约118MB/s；"
        "3.AHB接口固定32-bit字访问，haddr须4-byte对齐(addr[1:0]=2'b00)；hsize_o固定3'b010(WORD)；"
        "4.Burst有效吞吐较MVP Single约7×提升（MVP约16.7MB/s → v2.2约116~118MB/s）；"
        "5.性能前提：AHB零等待(hready_i=1始终)且FIFO非反压；最坏延时=基础延时+BUS_TIMEOUT_CYCLES·burst_len。",
        None,
        ["TP_037", "TP_038"]
    ),
    # ---- CHK_APLC_017 ----
    (
        "CHK_APLC_017",
        "dfx_stats_checker",
        "检查DFX流量统计计数器与状态可观测点正确性："
        "1.每opcode成功计数6路（WR_CSR/RD_CSR/AHB_WR32/AHB_RD32/AHB_WR_BURST/AHB_RD_BURST）：resp_valid且status==STS_OK时递增；"
        "2.每错误码失败计数8路（0x01/0x02/0x04/0x08/0x10/0x20/0x40/0x80）：resp_valid且status!=STS_OK时递增；"
        "3.CSR读/写计数各1路：csr_rd_en_o/csr_wr_en_o上升沿递增；AHB Single读/写计数各1路：AXI_REQ且hburst==SINGLE时递增；"
        "4.front_state_q/back_state_q/axi_state_q由外部CSR File以RO语义暴露，正确反映IDLE/ISSUE/WAIT_RESP/TA/TX/TX_BURST等状态；"
        "5.所有统计计数器属性WC（写1清零），位宽≥16bit防短期溢出。",
        None,
        ["TP_039", "TP_040"]
    ),
    # ---- CHK_APLC_018 ----
    (
        "CHK_APLC_018",
        "dfx_burst_stats_checker",
        "检查Burst相关DFX扩展统计与FIFO可观测点正确性："
        "1.Burst成功计数按hburst类型分6路（INCR4/INCR8/INCR16各读/写）：AXI_REQ且hburst==INCR*时递增；"
        "2.total_burst_beat_cnt(≥24bit)：每hready_i=1且axi_state in {AXI_REQ,AXI_BURST,AXI_WAIT}时自增；rxfifo_backpressure_cnt：rxfifo_full_o上升沿递增；txfifo_stall_cnt：txfifo_empty_o上升沿递增；"
        "3.rxfifo_cnt[5:0]/txfifo_cnt[5:0]正确反映当前FIFO占用beat数；burst_len[4:0]为当前任务Burst长度；"
        "4.axi_state(6态：AXI_IDLE/AXI_REQ/AXI_BURST/AXI_WAIT/AXI_DONE/AXI_ERR)由外部CSR File RO暴露；"
        "5.信号捕获域：协议侧pcs_ni/pdi_i/pdo_o/pdo_oe_o；AHB侧htrans/hburst/haddr/hwrite/hready/hresp/hrdata/hwdata；CSR侧csr_rd/wr_en/addr/wdata/rdata。",
        None,
        ["TP_041", "TP_042"]
    ),
    # ---- CHK_APLC_019 ----
    (
        "CHK_APLC_019",
        "memmap_checker",
        "检查CSR与AHB地址空间隔离正确性："
        "1.模块自身CSR(0x00~0x3F)不进入SoC AHB memory map，通过WR_CSR/RD_CSR协议命令访问，不出现在haddr_o上；"
        "2.对外AHB-Lite Master访问采用32bit地址空间(addr[31:0])和WORD访问粒度(hsize_o=3'b010)；"
        "3.CSR访问通过csr_rd_en_o/csr_wr_en_o/csr_addr_o[7:0]/csr_wdata_o[31:0]/csr_rdata_i[31:0]接口传递至外部CSR File，与AHB总线完全独立；"
        "4.AHB可达目标地址范围由SoC顶层统一约束，APLC-Lite不做无效地址判决（仅做4-byte对齐与Burst 1KB边界检查）；"
        "5.对齐合法的地址若落在无效memory map由SoC AHB互联返回hresp_i=1，APLC-Lite统一映射为STS_AHB_ERR(0x40)。",
        None,
        ["TP_043"]
    ),
    # ---- CHK_APLC_020 ----
    (
        "CHK_APLC_020",
        "ahb_master_checker",
        "检查AHB-Lite Master 2-phase流水时序与Burst协议正确性："
        "1.AHB 2-phase流水：T1地址相(AXI_REQ)驱动haddr_o/hwrite_o/htrans_o=NONSEQ(2'b10)/hburst_o；T2数据相(AXI_WAIT)htrans_o=IDLE，写驱动hwdata_o，读在hready_i=1采样hrdata_i；"
        "2.hsize_o固定3'b010(WORD)；burst_len→hburst映射：1→SINGLE(3'b000)，4→INCR4(3'b011)，8→INCR8(3'b101)，16→INCR16(3'b111)；"
        "3.Burst事务：首拍htrans_o=NONSEQ，后续beat htrans_o=SEQ(2'b11)，haddr每拍+4，hburst_o在整个burst期间保持稳定不翻转；"
        "4.INCR4(3'b011)：NONSEQ+SEQ×3共4拍地址相；INCR8(3'b101)：NONSEQ+SEQ×7共8拍；INCR16(3'b111)：NONSEQ+SEQ×15共16拍；"
        "5.不支持WRAP Burst、BUSY传输、byte/halfword访问、lock/exclusive访问；当前事务完成前不得发起下一笔AHB请求。",
        None,
        ["TP_044", "TP_045", "TP_046"]
    ),
]


# ============================================================
# Testcase Definitions (120 testcases)
# ============================================================

TESTCASES = [
    # ===== Category A: Clock & Reset (TC_APLC_001~006) =====
    (
        "TC_APLC_001",
        "test_clk_100mhz_stability",
        "配置条件："
        "1.模块复位完成，clk_i=100MHz（周期10ns）；"
        "2.test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.配置clk_i频率为100MHz，测量10个时钟周期；"
        "2.连续执行10条WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001设置CTRL.EN=1)；"
        "3.读取STATUS寄存器(opcode=0x11, reg_addr=0x08)验证BUSY位变化时序；"
        "4.持续运行1000个clk_i周期观察时钟稳定性；"
        "5.执行AHB_RD_BURST×4命令(opcode=0x23, burst_len=4, addr=0x10000000)验证AHB侧同步；"
        "期望结果："
        "1.clk_i周期误差在±1%内（9.9ns~10.1ns），所有内部逻辑在clk_i上升沿同步工作；"
        "2.WR_CSR命令返回STS_OK(0x00)，csr_wr_en_o在clk_i上升沿有效；"
        "3.AHB RD_BURST期间htrans_o/hburst_o/haddr_o均在clk_i上升沿驱动输出；"
        "4.协议侧SLC_CAXIS与AHB侧SLC_SAXIM共用clk_i同域无异步域交叉；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_001"],
        ["CHK_APLC_001"]
    ),
    (
        "TC_APLC_002",
        "test_clk_4bit_burst_durability",
        "配置条件："
        "1.模块复位完成，clk_i=100MHz；"
        "2.test_mode_i=1，en_i=1，lane_mode_i=2'b01（4-bit模式）；"
        "输入激励："
        "1.配置lane_mode_i=2'b01，执行AHB_WR_BURST×4命令(opcode=0x22, burst_len=4, addr=0x20000000, wdata随机)；"
        "2.等待命令完成，检查返回状态码；"
        "3.重复执行AHB_WR_BURST×4命令10次；"
        "4.持续运行10µs（1000000个clk_i周期），期间交替执行读/写命令；"
        "5.读取STATUS寄存器(opcode=0x11, reg_addr=0x08)确认无异常状态；"
        "期望结果："
        "1.所有AHB_WR_BURST×4命令返回STS_OK(0x00)；"
        "2.4-bit模式下帧接收12拍（48bit/4bpc），响应2拍（8bit/4bpc）；"
        "3.10µs持续运行期间时钟稳定性满足要求，周期误差在±1%内；"
        "4.STATUS寄存器无sticky错误位（CMD_ERR/BUS_ERR/FRAME_ERR/BURST_ERR均为0）；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_002"],
        ["CHK_APLC_001"]
    ),
    (
        "TC_APLC_003",
        "test_async_reset_idle",
        "配置条件："
        "1.模块空闲态，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b01（4-bit模式）；"
        "输入激励："
        "1.拉低rst_ni触发异步复位（至少持续5个clk_i周期）；"
        "2.释放rst_ni（同步释放）；"
        "3.复位释放后发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证模块恢复工作；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))检查复位后状态；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x0C(LAST_ERR))检查错误寄存器清零；"
        "6.再次拉低rst_ni触发复位，释放后验证FIFO空状态；"
        "期望结果："
        "1.复位后所有状态机回到IDLE态：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；"
        "2.输出信号deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0；"
        "3.pdo_o[15:0]=16'b0，RX/TX FIFO清空：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "4.CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)，LAST_ERR=0x00；"
        "5.复位释放后RD_CSR命令正常响应status_code=STS_OK(0x00)；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_003"],
        ["CHK_APLC_002"]
    ),
    (
        "TC_APLC_004",
        "test_async_reset_mid_burst",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "2.模块正在执行AHB_RD_BURST×16命令；"
        "输入激励："
        "1.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16, addr=0x10000000)；"
        "2.等待axi_state进入AXI_BURST态（Burst执行中间）；"
        "3.在Burst中途异步拉低rst_ni（至少持续5个clk_i周期）；"
        "4.释放rst_ni（同步释放）；"
        "5.复位释放后发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))验证模块恢复；"
        "6.发送新的AHB_RD32命令(opcode=0x21, addr=0x10000000)验证AHB接口恢复；"
        "期望结果："
        "1.rst_ni拉低后所有FSM立即复位至IDLE：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；"
        "2.AHB输出立即回到空闲：htrans_o=2'b00(IDLE)，hburst_o=SINGLE，haddr_o=0；"
        "3.RX/TX FIFO强制清空：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "4.复位释放后新命令正常响应status_code=STS_OK(0x00)；"
        "coverage check点：对axi_state各状态注入复位收集功能覆盖率",
        None,
        ["TP_004"],
        ["CHK_APLC_002"]
    ),
    (
        "TC_APLC_005",
        "test_rst_reset_register_defaults",
        "配置条件："
        "1.模块复位完成，clk_i=100MHz；"
        "2.test_mode_i=1，en_i=1；"
        "输入激励："
        "1.拉低rst_ni触发异步复位并释放；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))读版本寄存器；"
        "3.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))读控制寄存器默认值；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))读状态寄存器；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x0C(LAST_ERR))读错误寄存器；"
        "6.发送RD_CSR命令(opcode=0x11, reg_addr=0x10(BURST_CNT))读Burst计数器；"
        "7.先写CTRL(0x04, wdata=0x07使EN=1/LANE_MODE=11/SOFT_RST=0)再复位，验证CTRL恢复默认；"
        "期望结果："
        "1.VERSION(0x00)读回编译期固化常量，不受复位影响；"
        "2.CTRL(0x04)复位后EN=0，LANE_MODE=2'b00(1-bit)，SOFT_RST=0；"
        "3.STATUS(0x08)复位后BUSY=0，RESP_VALID=0，所有sticky位=0；"
        "4.LAST_ERR(0x0C)复位后ERR_CODE=0x00；BURST_CNT(0x10)复位后=0；"
        "5.写CTRL后复位，读回CTRL.EN=0/LANE_MODE=2'b00证明复位恢复默认值；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_003"],
        ["CHK_APLC_002", "CHK_APLC_003"]
    ),
    (
        "TC_APLC_006",
        "test_rst_random_interval",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "2.随机选择复位注入时机；"
        "输入激励："
        "1.随机选择复位时机：IDLE/ISSUE/WAIT_RESP/AXI_BURST/TA/TX共6种front_state状态；"
        "2.在选定时刻拉低rst_ni持续5~20个随机周期后释放；"
        "3.复位释放后发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证恢复；"
        "4.重复执行N≥50次，每次随机选择不同状态注入复位；"
        "5.对AXI_BURST状态复位，额外验证htrans_o回IDLE和FIFO清空；"
        "期望结果："
        "1.任何时刻复位后FSM均回到IDLE：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；"
        "2.输出deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，FIFO清空；"
        "3.CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)；"
        "4.复位释放后RD_CSR命令返回STS_OK(0x00)；"
        "coverage check点：覆盖front_state 6态×复位注入交叉覆盖率，覆盖rst_ni持续周期随机范围",
        None,
        ["TP_003", "TP_004"],
        ["CHK_APLC_002"]
    ),
    # ===== Category B: CSR Register Access (TC_APLC_007~016) =====
    (
        "TC_APLC_007",
        "test_csr_rw_ctrl",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001设置CTRL.EN=1)；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))读回验证CTRL.EN=1；"
        "3.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000006设置LANE_MODE=2'b11)；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))读回验证LANE_MODE=2'b11且EN仍=1；"
        "5.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000008设置SOFT_RST=1)；"
        "6.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))读回验证SOFT_RST后EN=0/LANE_MODE=2'b00；"
        "7.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000000清零CTRL)；"
        "期望结果："
        "1.WR_CSR(CTRL, wdata=0x01)后读回0x00000001，EN=1证明RW属性——写入值可读回；"
        "2.WR_CSR(CTRL, wdata=0x06)后读回0x00000006，LANE_MODE=2'b11且EN=0（bit0被写0）；"
        "3.WR_CSR(CTRL, SOFT_RST=1)后读回CTRL.EN=0/LANE_MODE=2'b00，证明SOFT_RST触发上下文清零恢复默认；"
        "4.WR_CSR(CTRL, wdata=0x00)后读回0x00000000，全字段清零验证RW可写任意值；"
        "5.每次CSR写操作csr_wr_en_o为单周期脉冲，同周期csr_addr_o/csr_wdata_o有效；"
        "coverage check点：对CTRL各字段(EN/LANE_MODE/SOFT_RST)收集功能覆盖率，覆盖RW属性验证场景",
        None,
        ["TP_005"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_008",
        "test_csr_ro_version",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))读取初始值；"
        "2.发送WR_CSR命令(opcode=0x10, reg_addr=0x00(VERSION), wdata=0xDEADBEEF)尝试写入RO寄存器；"
        "3.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))再次读取验证值未改变；"
        "4.发送WR_CSR命令(opcode=0x10, reg_addr=0x00(VERSION), wdata=0x00000000)尝试写入0；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))再次读取确认仍为复位默认值；"
        "期望结果："
        "1.第1次RD_CSR(VERSION)读回编译期固化常量V0；"
        "2.WR_CSR(VERSION, 0xDEADBEEF)写操作后RD_CSR读回仍为V0，证明RO属性——写入无效；"
        "3.WR_CSR(VERSION, 0x00)写操作后RD_CSR读回仍为V0，证明RO属性——任意值写入均无效；"
        "4.WR_CSR写VERSION时csr_wr_en_o脉冲仍产生（硬件不阻止脉冲），但外部CSR File忽略写入；"
        "coverage check点：对VERSION寄存器RO属性验证场景收集功能覆盖率",
        None,
        ["TP_005"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_009",
        "test_csr_ro_status_lasterr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))读取初始值；"
        "2.发送WR_CSR命令(opcode=0x10, reg_addr=0x08(STATUS), wdata=0xFFFFFFFF)尝试写STATUS；"
        "3.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))读回确认值未改变；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0x0C(LAST_ERR))读取初始值；"
        "5.发送WR_CSR命令(opcode=0x10, reg_addr=0x0C(LAST_ERR), wdata=0xAB)尝试写LAST_ERR；"
        "6.发送RD_CSR命令(opcode=0x11, reg_addr=0x0C(LAST_ERR))读回确认值未改变；"
        "7.触发一个错误（test_mode_i=0发WR_CSR）后再读LAST_ERR验证硬件更新而非写入生效；"
        "期望结果："
        "1.WR_CSR(STATUS, 0xFFFFFFFF)后读回仍为复位默认值，证明RO属性——STATUS不可软件写入；"
        "2.WR_CSR(LAST_ERR, 0xAB)后读回仍为0x00，证明RO属性——LAST_ERR不可软件写入；"
        "3.触发错误后LAST_ERR=STS_NOT_IN_TEST(0x04)由硬件更新，非先前写入的0xAB；"
        "4.STATUS的BUSY/IN_TEST_MODE等位由硬件动态更新，不受软件写入影响；"
        "coverage check点：对STATUS/LAST_ERR RO属性验证场景收集功能覆盖率",
        None,
        ["TP_005"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_010",
        "test_csr_wc_burst_cnt",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x10(BURST_CNT))读复位默认值应为0；"
        "2.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4, addr=0x10000000, wdata随机)执行一次Burst事务；"
        "3.发送RD_CSR命令(opcode=0x11, reg_addr=0x10(BURST_CNT))读回验证计数+1；"
        "4.发送WR_CSR命令(opcode=0x10, reg_addr=0x10(BURST_CNT), wdata=0x00000001)写1清零；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x10(BURST_CNT))读回验证已清零为0；"
        "6.发送WR_CSR命令(opcode=0x10, reg_addr=0x10(BURST_CNT), wdata=0x00000000)写0不清零；"
        "7.再执行一次Burst事务后读BURST_CNT验证写0不影响计数；"
        "期望结果："
        "1.复位后BURST_CNT=0；执行1次Burst后BURST_CNT=1，证明事务成功时计数递增；"
        "2.WR_CSR(BURST_CNT, wdata=1)后读回0，证明WC属性——写1清零生效；"
        "3.WR_CSR(BURST_CNT, wdata=0)后执行Burst，读回1，证明写0不影响当前计数值；"
        "4.BURST_CNT位宽≥16bit防止短期溢出；"
        "coverage check点：对BURST_CNT WC属性验证场景收集功能覆盖率",
        None,
        ["TP_007"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_011",
        "test_csr_bad_reg_addr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x40)访问超出有效范围的地址；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x7F)访问另一个超出范围的地址；"
        "3.发送WR_CSR命令(opcode=0x10, reg_addr=0x40, wdata=0xDEAD)尝试写超出范围地址；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0xFF)访问最大无效地址；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x3F)访问有效上界地址（应正常）；"
        "期望结果："
        "1.reg_addr=0x40返回STS_BAD_REG(0x10)，不产生csr_rd_en_o脉冲，不发起CSR接口访问；"
        "2.reg_addr=0x7F返回STS_BAD_REG(0x10)，同上；"
        "3.reg_addr=0x40 WR_CSR返回STS_BAD_REG(0x10)，不产生csr_wr_en_o脉冲；"
        "4.reg_addr=0xFF返回STS_BAD_REG(0x10)；"
        "5.reg_addr=0x3F返回STS_OK(0x00)（有效上界），产生csr_rd_en_o脉冲正常读；"
        "coverage check点：对CSR地址范围0x00~0x3F(有效)和0x40~0xFF(无效)收集功能覆盖率",
        None,
        ["TP_006"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_012",
        "test_csr_write_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)，观察csr_wr_en_o时序；"
        "2.检查csr_wr_en_o是否为单周期脉冲；"
        "3.检查同一周期内csr_addr_o[7:0]=0x04和csr_wdata_o[31:0]=0x00000001是否有效；"
        "4.发送WR_CSR命令(opcode=0x10, reg_addr=0x10(BURST_CNT), wdata=0x00000001)验证WC写时序；"
        "5.连续发送3条WR_CSR命令验证每条均产生独立的csr_wr_en_o脉冲；"
        "期望结果："
        "1.csr_wr_en_o为单周期脉冲，持续1个clk_i周期后自动拉低；"
        "2.csr_addr_o[7:0]和csr_wdata_o[31:0]在csr_wr_en_o=1同一周期内有效；"
        "3.外部CSR File在csr_wr_en_o=1的clk_i上升沿采样完成写入；"
        "4.连续3条WR_CSR产生3个独立单周期脉冲，间隔至少1 cycle；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_005"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_013",
        "test_csr_read_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.先写CTRL(opcode=0x10, reg_addr=0x04, wdata=0x00000005设置EN=1/LANE_MODE=2'b10)；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))，观察csr_rd_en_o时序；"
        "3.检查csr_rd_en_o是否为单周期脉冲；"
        "4.检查下一周期csr_rdata_i[31:0]是否为0x00000005（1 cycle读延迟）；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))验证RO读时序同样为1 cycle延迟；"
        "期望结果："
        "1.csr_rd_en_o为单周期脉冲，持续1个clk_i周期后自动拉低；"
        "2.csr_addr_o[7:0]在csr_rd_en_o=1同一周期内有效；"
        "3.csr_rdata_i[31:0]在csr_rd_en_o脉冲后的下一clk_i周期有效（1 cycle读延迟）；"
        "4.RD_CSR(CTRL)读回0x00000005，RD_CSR(VERSION)读回编译期常量；"
        "coverage check点：直接用例覆盖，不收功能覆盖率",
        None,
        ["TP_005"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_014",
        "test_csr_all_reg_walk",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.遍历有效CSR地址0x00(VERSION)/0x04(CTRL)/0x08(STATUS)/0x0C(LAST_ERR)/0x10(BURST_CNT)逐一RD_CSR读取；"
        "2.对RW寄存器CTRL(0x04)写入多个值(0x01/0x05/0x07)并每次读回验证；"
        "3.对WC寄存器BURST_CNT(0x10)写1清零并读回验证；"
        "4.对RO寄存器VERSION(0x00)/STATUS(0x08)/LAST_ERR(0x0C)尝试写入后读回验证值不变；"
        "5.遍历保留地址0x14~0x3F逐一RD_CSR读取（预期返回默认值或STS_OK）；"
        "期望结果："
        "1.5个有效CSR地址均返回STS_OK(0x00)，正确读回对应寄存器值；"
        "2.CTRL(0x04)RW属性验证：写0x01读回0x01，写0x05读回0x05，写0x07读回0x07；"
        "3.BURST_CNT(0x10)WC属性验证：写1后读回0；"
        "4.VERSION/STATUS/LAST_ERR RO属性验证：写入后读回仍为原值；"
        "5.保留地址0x14~0x3F读操作返回STS_OK（外部CSR File返回0），不报STS_BAD_REG；"
        "coverage check点：对CSR地址0x00~0x3F全地址空间收集功能覆盖率",
        None,
        ["TP_005", "TP_006"],
        ["CHK_APLC_003"]
    ),
    (
        "TC_APLC_015",
        "test_csr_soft_reset",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；"
        "输入激励："
        "1.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)设置EN=1/LANE_MODE=2'b11/SOFT_RST=0；"
        "2.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))确认配置生效读回0x07；"
        "3.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000008)写SOFT_RST=1触发软复位；"
        "4.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))读取软复位后CTRL值；"
        "5.执行AHB_RD32命令(opcode=0x21, addr=0x10000000)验证模块仍可正常工作；"
        "期望结果："
        "1.写SOFT_RST=1前CTRL读回0x07(EN=1, LANE_MODE=11, SOFT_RST=0)；"
        "2.写SOFT_RST=1后CTRL.EN=0/LANE_MODE=2'b00，协议上下文清零恢复默认lane模式；"
        "3.软复位不清FIFO：rxfifo_empty_o/txfifo_empty_o状态不变（若之前为空仍为空）；"
        "4.软复位后模块可正常接受新命令，AHB_RD32返回STS_OK(0x00)；"
        "5.SOFT_RST位为自清零：写入1后下一拍自动回0（单次触发）；"
        "coverage check点：对CTRL.SOFT_RST触发和恢复场景收集功能覆盖率",
        None,
        ["TP_005"],
        ["CHK_APLC_003", "CHK_APLC_010"]
    ),
    (
        "TC_APLC_016",
        "test_csr_random_access",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.随机配置lane_mode_i（遍历2'b00/01/10/11）；"
        "输入激励："
        "1.随机选择CSR地址：有效地址0x00/0x04/0x08/0x0C/0x10和无效地址0x40/0x7F/0xFF；"
        "2.随机选择读(RD_CSR, opcode=0x11)或写(WR_CSR, opcode=0x10)操作；"
        "3.写操作随机生成wdata；"
        "4.对有效地址读操作检查返回STS_OK(0x00)和csr_rdata_i；"
        "5.对无效地址操作检查返回STS_BAD_REG(0x10)；"
        "6.重复执行N≥100次，每次随机选择地址和操作类型；"
        "期望结果："
        "1.有效CSR地址读操作返回STS_OK(0x00)，读数据与寄存器属性一致（RO不变/RW写后读回/WC清零后为0）；"
        "2.有效CSR地址写操作：RW(CTRL)写后读回一致，RO(VERSION/STATUS/LAST_ERR)写入无效，WC(BURST_CNT)写1清零；"
        "3.无效CSR地址(reg_addr>=0x40)返回STS_BAD_REG(0x10)，不产生csr_wr_en_o/csr_rd_en_o脉冲；"
        "4.所有CSR写操作csr_wr_en_o为单周期脉冲，CSR读操作csr_rd_en_o为单周期脉冲后1 cycle延迟返回数据；"
        "coverage check点：覆盖CSR地址0x00~0x10(有效)×0x40~0xFF(无效)×读/写操作交叉覆盖率",
        None,
        ["TP_005", "TP_006", "TP_007"],
        ["CHK_APLC_003"]
    ),
    # ===== Category C: Work Mode (TC_APLC_017~026) =====
    (
        "TC_APLC_017",
        "test_not_in_test_rejection",
        "配置条件："
        "1.模块复位完成，test_mode_i=0（非测试模式），en_i=1（使能有效）；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，模块处于功能就绪状态；"
        "输入激励："
        "1.保持test_mode_i=0，en_i=1，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.检查响应状态码是否为STS_NOT_IN_TEST(0x04)；"
        "3.验证期间无csr_wr_en_o脉冲产生，CSR接口不发起访问；"
        "4.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))检查STATUS[5]=IN_TEST_MODE=0；"
        "5.验证前端FSM仍走IDLE→ISSUE→TA→TX路径返回错误状态码，pdo_oe_o在TX态=1；"
        "6.重复发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0x12345678)验证同样返回STS_NOT_IN_TEST(0x04)；"
        "期望结果："
        "1.WR_CSR命令返回STS_NOT_IN_TEST(0x04)，不产生csr_wr_en_o脉冲；"
        "2.AHB_WR32命令返回STS_NOT_IN_TEST(0x04)，不产生htrans_o=NONSEQ；"
        "3.STATUS[5]=IN_TEST_MODE镜像test_mode_i=0；"
        "4.前端FSM仍走完整IDLE→ISSUE→TA→TX路径，pdo_oe_o在TX态=1；"
        "5.SLC_DPCHK在frame_valid时刻采样test_mode_i=0即拒绝所有命令；coverage check点：覆盖test_mode_i=0门控拒绝场景，验证STS_NOT_IN_TEST(0x04)优先级判定",

        None,
        ["TP_008"],
        ["CHK_APLC_004"]
    ),
    (
        "TC_APLC_018",
        "test_disabled_rejection",
        "配置条件："
        "1.模块复位完成，test_mode_i=1（测试模式），en_i=0（使能关闭）；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=0，模块处于未使能状态；"
        "输入激励："
        "1.保持test_mode_i=1，en_i=0，发送AHB_RD32命令(opcode=0x21, addr=0x10000000)；"
        "2.检查响应状态码是否为STS_DISABLED(0x08)；"
        "3.验证期间无htrans_o=NONSEQ输出，AHB接口不发起访问；"
        "4.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)验证同样返回STS_DISABLED(0x08)；"
        "5.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))检查STATUS位域反映disabled状态；"
        "6.拉高en_i=1后发送同样命令验证返回STS_OK(0x00)恢复正常；"
        "期望结果："
        "1.en_i=0时AHB_RD32命令返回STS_DISABLED(0x08)，不产生htrans_o=NONSEQ；"
        "2.en_i=0时WR_CSR命令返回STS_DISABLED(0x08)，不产生csr_wr_en_o脉冲；"
        "3.STATUS反映disabled状态；"
        "4.拉高en_i=1后命令正常返回STS_OK(0x00)，证明en_i门控可恢复；"
        "5.SLC_DPCHK在frame_valid时刻采样en_i=0即拒绝所有命令；coverage check点：覆盖en_i=0门控拒绝场景，验证STS_DISABLED(0x08)判定与恢复",

        None,
        ["TP_009"],
        ["CHK_APLC_004"]
    ),
    (
        "TC_APLC_019",
        "test_priority_not_in_test_vs_disabled",
        "配置条件："
        "1.模块复位完成，test_mode_i=0（非测试模式），en_i=0（使能关闭）；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=0，两个门控条件同时不满足；"
        "输入激励："
        "1.保持test_mode_i=0且en_i=0，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.检查响应状态码是否为STS_NOT_IN_TEST(0x04)而非STS_DISABLED(0x08)；"
        "3.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xDEADBEEF)验证优先级一致性；"
        "4.发送AHB_RD_BURST命令(opcode=0x23, burst_len=4, addr=0x10000000)验证Burst命令同样遵循优先级；"
        "5.仅拉高test_mode_i=1（en_i仍=0）验证切换为STS_DISABLED(0x08)；"
        "6.仅拉高en_i=1（test_mode_i仍=0）验证仍为STS_NOT_IN_TEST(0x04)；"
        "期望结果："
        "1.test_mode_i=0且en_i=0时返回STS_NOT_IN_TEST(0x04)，证明优先级链STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)；"
        "2.WR_CSR/AHB_WR32/AHB_RD_BURST命令均返回STS_NOT_IN_TEST(0x04)，优先级与命令类型无关；"
        "3.仅拉高test_mode_i=1后返回STS_DISABLED(0x08)，证明优先级链判定正确；"
        "4.仅拉高en_i=1后仍返回STS_NOT_IN_TEST(0x04)，test_mode_i优先判定；"
        "5.两种拒绝场景下前端FSM仍走IDLE→ISSUE→TA→TX路径返回错误码；coverage check点：覆盖test_mode_i=0且en_i=0双重门控场景，验证STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)优先级",

        None,
        ["TP_008", "TP_009"],
        ["CHK_APLC_004"]
    ),
    (
        "TC_APLC_020",
        "test_lane_1bit_wr_csr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b00（1-bit模式）；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b00；"
        "输入激励："
        "1.配置lane_mode_i=2'b00，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.通过pdi_i[0]逐bit输入帧数据：opcode=0x10(8bit)→reg_addr=0x04(8bit)→wdata=0x00000001(32bit)，共48bit需48个RX周期；"
        "3.验证pdi_i[15:1]被忽略，仅pdi_i[0]有效；"
        "4.观察rx_count_q按bpc=1步进递增从0至47；"
        "5.帧接收完成后等待1 cycle turnaround(TA态)，pdo_oe_o=0；"
        "6.观察TX阶段pdo_o[0]输出8bit状态码STS_OK(0x00)，pdo_o[15:1]驱动为0，pdo_oe_o=1；"
        "7.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证写生效，读回0x00000001；"
        "期望结果："
        "1.48个RX周期完成帧接收，rx_count_q从0递增至47，frame_valid在第49周期产生；"
        "2.pdi_i[15:1]信号被忽略，仅pdi_i[0]参与移位；pdo_o[15:1]驱动为0，仅pdo_o[0]有效；"
        "3.WR_CSR返回STS_OK(0x00)，csr_wr_en_o单周期脉冲有效，csr_addr_o=0x04，csr_wdata_o=0x00000001；"
        "4.RD_CSR读回CTRL=0x00000001证明写入成功；"
        "5.SLC_CAXIS按lane_mode_i=2'b00计算bpc=1(bits per clock)；coverage check点：覆盖1-bit模式(lane_mode_i=2b00)帧接收场景，收集bpc=1与opcode交叉覆盖率",

        None,
        ["TP_010"],
        ["CHK_APLC_005"]
    ),
    (
        "TC_APLC_021",
        "test_lane_4bit_wr_csr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b01（4-bit模式）；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b01；"
        "输入激励："
        "1.配置lane_mode_i=2'b01，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000005)；"
        "2.通过pdi_i[3:0]每拍输入4bit帧数据：opcode=0x10(8bit/2拍)→reg_addr=0x04(8bit/2拍)→wdata=0x00000005(32bit/8拍)，共48bit需12个RX周期；"
        "3.验证pdi_i[15:4]被忽略，仅pdi_i[3:0]有效；"
        "4.观察rx_count_q按bpc=4步进递增从0至44(步长4)；"
        "5.帧接收完成后等待1 cycle turnaround(TA态)，pdo_oe_o=0；"
        "6.观察TX阶段pdo_o[3:0]输出8bit状态码STS_OK(0x00)需2拍，pdo_o[15:4]驱动为0，pdo_oe_o=1；"
        "7.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证写生效读回0x00000005；"
        "期望结果："
        "1.12个RX周期完成帧接收，rx_count_q按步长4递增(0→4→8→...→44→48)，frame_valid产生；"
        "2.pdi_i[15:4]信号被忽略，仅pdi_i[3:0]参与移位；pdo_o[15:4]驱动为0，仅pdo_o[3:0]有效；"
        "3.WR_CSR返回STS_OK(0x00)，csr_wr_en_o单周期脉冲，csr_addr_o=0x04，csr_wdata_o=0x00000005；"
        "4.RD_CSR读回CTRL=0x00000005(EN=1, LANE_MODE=2'b10)证明写入成功；"
        "5.SLC_CAXIS按lane_mode_i=2'b01计算bpc=4(bits per clock)；coverage check点：覆盖4-bit模式(lane_mode_i=2b01)帧接收场景，收集bpc=4与opcode交叉覆盖率",

        None,
        ["TP_011"],
        ["CHK_APLC_005"]
    ),
    (
        "TC_APLC_022",
        "test_lane_8bit_wr_csr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b10（8-bit模式）；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b10；"
        "输入激励："
        "1.配置lane_mode_i=2'b10，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000003)；"
        "2.通过pdi_i[7:0]每拍输入8bit帧数据：opcode=0x10(8bit/1拍)→reg_addr=0x04(8bit/1拍)→wdata=0x00000003(32bit/4拍)，共48bit需6个RX周期；"
        "3.验证pdi_i[15:8]被忽略，仅pdi_i[7:0]有效；"
        "4.观察rx_count_q按bpc=8步进递增从0至40(步长8)；"
        "5.帧接收完成后等待1 cycle turnaround(TA态)，pdo_oe_o=0；"
        "6.观察TX阶段pdo_o[7:0]输出8bit状态码STS_OK(0x00)需1拍，pdo_o[15:8]驱动为0，pdo_oe_o=1；"
        "7.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证写生效读回0x00000003；"
        "期望结果："
        "1.6个RX周期完成帧接收，rx_count_q按步长8递增(0→8→16→...→40→48)，frame_valid产生；"
        "2.pdi_i[15:8]信号被忽略，仅pdi_i[7:0]参与移位；pdo_o[15:8]驱动为0，仅pdo_o[7:0]有效；"
        "3.WR_CSR返回STS_OK(0x00)，csr_wr_en_o单周期脉冲，csr_addr_o=0x04，csr_wdata_o=0x00000003；"
        "4.RD_CSR读回CTRL=0x00000003(EN=1, LANE_MODE=2'b01)证明写入成功；"
        "5.SLC_CAXIS按lane_mode_i=2'b10计算bpc=8(bits per clock)；coverage check点：覆盖8-bit模式(lane_mode_i=2b10)帧接收场景，收集bpc=8与opcode交叉覆盖率",

        None,
        ["TP_012"],
        ["CHK_APLC_005"]
    ),
    (
        "TC_APLC_023",
        "test_lane_16bit_wr_csr",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b11；"
        "输入激励："
        "1.配置lane_mode_i=2'b11，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)；"
        "2.通过pdi_i[15:0]每拍输入16bit帧数据：opcode=0x10+reg_addr=0x04(16bit/1拍)→wdata=0x00000007(32bit/2拍)，共48bit需3个RX周期；"
        "3.验证pdi_i[15:0]全部有效，无忽略位；"
        "4.观察rx_count_q按bpc=16步进递增从0至32(步长16)；"
        "5.帧接收完成后等待1 cycle turnaround(TA态)，pdo_oe_o=0；"
        "6.观察TX阶段pdo_o[15:0]输出8bit状态码STS_OK(0x00)需1拍(高8bit为0)，pdo_oe_o=1；"
        "7.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))验证写生效读回0x00000007；"
        "期望结果："
        "1.3个RX周期完成帧接收，rx_count_q按步长16递增(0→16→32→48)，frame_valid在第4周期产生(寄存输出延迟1 cycle)；"
        "2.pdi_i[15:0]全部有效参与移位；pdo_o[15:0]输出响应数据，高位补0；"
        "3.WR_CSR返回STS_OK(0x00)，csr_wr_en_o单周期脉冲，csr_addr_o=0x04，csr_wdata_o=0x00000007；"
        "4.RD_CSR读回CTRL=0x00000007(EN=1, LANE_MODE=2'b11)证明写入成功；"
        "5.SLC_CAXIS按lane_mode_i=2'b11计算bpc=16(bits per clock)；coverage check点：覆盖16-bit模式(lane_mode_i=2b11)帧接收场景，收集bpc=16与opcode交叉覆盖率",

        None,
        ["TP_013"],
        ["CHK_APLC_005"]
    ),
    (
        "TC_APLC_024",
        "test_lane_switch_idle",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.初始lane_mode_i=2'b00（1-bit模式）；"
        "3.pcs_ni=1（空闲态），模块无事务执行；"
        "输入激励："
        "1.在pcs_ni=1期间将lane_mode_i从2'b00切换为2'b01（4-bit模式）；"
        "2.等待≥2个clk_i周期同步后发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "3.验证4-bit模式下帧接收12拍（48bit/4bpc）正常完成返回STS_OK(0x00)；"
        "4.在pcs_ni=1期间将lane_mode_i从2'b01切换为2'b11（16-bit模式）；"
        "5.等待≥2个clk_i周期同步后发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))；"
        "6.验证16-bit模式下帧接收1拍（16bit/16bpc）正常完成返回STS_OK(0x00)；"
        "7.在pcs_ni=1期间将lane_mode_i从2'b11切换为2'b10（8-bit模式）并执行AHB_WR32验证；"
        "期望结果："
        "1.pcs_ni=1期间切换lane_mode_i后新事务按新bpc工作，命令返回STS_OK(0x00)；"
        "2.4-bit模式WR_CSR：12拍RX→1拍TA→2拍TX，响应正确；"
        "3.16-bit模式RD_CSR：1拍RX→1拍TA→3拍TX，响应正确；"
        "4.8-bit模式AHB_WR32正常工作，htrans_o=NONSEQ发起AHB访问；"
        "5.lane_mode_i仅在空闲态切换不触发任何错误，STATUS无sticky错误位；coverage check点：覆盖空闲态(pcs_ni=1)lane_mode切换场景，收集lane_mode切换与新命令执行交叉覆盖率",

        None,
        ["TP_024"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_025",
        "test_lane_switch_mid_transaction",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.初始lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，模块正在执行事务（pcs_ni=0）；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)，在RX阶段中途切换lane_mode_i；"
        "2.在pcs_ni=0期间（rx_count_q=16时）将lane_mode_i从2'b11切换为2'b00（1-bit模式）；"
        "3.观察SLC_CAXIS移位寄存器步进宽度立即改变导致帧数据错位；"
        "4.检查命令响应状态码是否为STS_FRAME_ERR(0x01)或STS_BAD_OPCODE(0x02)；"
        "5.验证STATUS[4]=FRAME_ERR(sticky)置位或STATUS[2]=CMD_ERR置位；"
        "6.等待pcs_ni=1后恢复正常lane_mode_i=2'b11，发送新命令验证模块恢复工作；"
        "期望结果："
        "1.事务中途切换lane_mode_i导致bpc突变，帧数据错位，可能触发STS_FRAME_ERR(0x01)或STS_BAD_OPCODE(0x02)；"
        "2.SLC_CAXIS连续组合采样lane_mode_i计算bpc，切换后步进宽度立即改变；"
        "3.STATUS sticky错误位置位反映帧错误；"
        "4.pcs_ni=1后恢复lane_mode_i=2'b11，新命令正常返回STS_OK(0x00)；"
        "5.lane_mode_i在事务执行期间(pcs_ni=0)必须保持稳定，否则帧数据损坏；coverage check点：覆盖事务中途(pcs_ni=0)lane_mode切换场景，收集lane_mode切换与帧错误交叉覆盖率",

        None,
        ["TP_025"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_026",
        "test_mode_gate_random",
        "配置条件："
        "1.模块复位完成，lane_mode_i=2'b11（16-bit模式）；"
        "2.随机组合test_mode_i和en_i信号；"
        "3.CTRL.EN由先前的WR_CSR命令配置；"
        "输入激励："
        "1.随机选择test_mode_i∈{0,1}和en_i∈{0,1}共4种组合；"
        "2.对每种组合发送随机命令：WR_CSR(0x10)/RD_CSR(0x11)/AHB_WR32(0x20)/AHB_RD32(0x21)；"
        "3.test_mode_i=0时期望STS_NOT_IN_TEST(0x04)，验证无CSR/AHB访问脉冲；"
        "4.en_i=0（且test_mode_i=1）时期望STS_DISABLED(0x08)，验证无CSR/AHB访问脉冲；"
        "5.test_mode_i=0且en_i=0时期望STS_NOT_IN_TEST(0x04)（优先于STS_DISABLED）；"
        "6.test_mode_i=1且en_i=1时期望STS_OK(0x00)正常响应；"
        "7.重复执行N≥50次，每次随机选择组合和命令类型；"
        "期望结果："
        "1.test_mode_i=0所有命令返回STS_NOT_IN_TEST(0x04)，不产生csr_wr_en_o/csr_rd_en_o脉冲和htrans_o=NONSEQ；"
        "2.en_i=0(test_mode_i=1)所有命令返回STS_DISABLED(0x08)，同样不发起任何访问；"
        "3.test_mode_i=0且en_i=0返回STS_NOT_IN_TEST(0x04)证明优先级链正确；"
        "4.test_mode_i=1且en_i=1命令正常返回STS_OK(0x00)；"
        "5.N≥50次随机组合全部符合优先级链判定，无异常；coverage check点：覆盖test_mode_i/en_i随机组合门控场景，N>=50次统计覆盖4种组合",

        None,
        ["TP_008", "TP_009"],
        ["CHK_APLC_004"]
    ),
    # ===== Category D: Protocol Frame (TC_APLC_027~040) =====
    (
        "TC_APLC_027",
        "test_wr_csr_16bit_full_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b11；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)；"
        "2.RX阶段：pdi_i[15:0]在3个clk_i周期输入48bit帧数据（第1拍：{0x10,0x04}，第2拍：0x0000，第3拍：0x0007）；"
        "3.观察rx_count_q按16步进：0→16→32→48，frame_valid在第4周期产生；"
        "4.ISSUE阶段：frame_valid后进入ISSUE态，驱动csr_wr_en_o=1单周期脉冲，同周期csr_addr_o=0x04，csr_wdata_o=0x00000007；"
        "5.TA阶段：csr_wr_en_o后1 cycle turnaround，pdo_oe_o=0，pdo_o[15:0]高阻；"
        "6.TX阶段：pdo_oe_o=1，pdo_o[15:0]输出8bit状态码STS_OK(0x00)占1拍（高8bit补0）；"
        "7.TX完成后pdo_oe_o=0，front_state回到IDLE；"
        "期望结果："
        "1.RX 3拍→ISSUE 1拍(csr_wr_en_o)→TA 1拍→TX 1拍，完整时序6个clk_i周期；"
        "2.csr_wr_en_o在ISSUE态为单周期脉冲，同周期csr_addr_o[7:0]=0x04，csr_wdata_o[31:0]=0x00000007有效；"
        "3.TA态pdo_oe_o=0，TX态pdo_oe_o=1，pdo_o输出0x0000(status_code=STS_OK(0x00))；"
        "4.RD_CSR(opcode=0x11, reg_addr=0x04)读回CTRL=0x00000007验证CSR写入生效；"
        "5.front_state完整路径IDLE→ISSUE→TA→TX→IDLE无异常跳转；coverage check点：覆盖16-bit WR_CSR完整时序(IDLE->ISSUE->TA->TX)场景，收集front_state路径覆盖率",

        None,
        ["TP_014"],
        ["CHK_APLC_006"]
    ),
    (
        "TC_APLC_028",
        "test_wr_csr_4bit_turnaround",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b01（4-bit模式），bpc=4；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b01；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.RX阶段：pdi_i[3:0]在12个clk_i周期输入48bit帧数据，rx_count_q按步长4递增(0→4→8→...→44→48)；"
        "3.ISSUE阶段：frame_valid后驱动csr_wr_en_o=1单周期脉冲，csr_addr_o=0x04，csr_wdata_o=0x00000001；"
        "4.TA阶段：固定1 cycle turnaround，pdo_oe_o=0，pdo_o[3:0]高阻；"
        "5.TX阶段：pdo_oe_o=1，pdo_o[3:0]输出8bit状态码STS_OK(0x00)需2拍（第1拍高4位0x0，第2拍低4位0x0）；"
        "6.验证pdi_i[15:4]被忽略，pdo_o[15:4]驱动为0；"
        "期望结果："
        "1.RX 12拍→ISSUE 1拍(csr_wr_en_o)→TA 1拍→TX 2拍，完整时序16个clk_i周期；"
        "2.csr_wr_en_o单周期脉冲有效，同周期csr_addr_o=0x04，csr_wdata_o=0x00000001；"
        "3.TA态pdo_oe_o=0，TX态pdo_oe_o=1；pdo_o[3:0]输出0x00(status_code=STS_OK)分2拍；"
        "4.4-bit模式下turnaround时序与16-bit模式一致，均为1 cycle固定；"
        "5.RD_CSR读回CTRL=0x00000001验证写入生效；coverage check点：覆盖4-bit WR_CSR turnaround时序场景，收集TX拍数与lane_mode交叉覆盖率",

        None,
        ["TP_015"],
        ["CHK_APLC_006"]
    ),
    (
        "TC_APLC_029",
        "test_rd_csr_16bit_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，先写CTRL(0x04, wdata=0x00000005)使其有已知值；"
        "输入激励："
        "1.先发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000005)设置已知值；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))读取CTRL；"
        "3.RX阶段：pdi_i[15:0]在1个clk_i周期输入16bit帧数据（{0x11,0x04}），rx_count_q从0→16；"
        "4.ISSUE阶段：frame_valid后驱动csr_rd_en_o=1单周期脉冲，csr_addr_o=0x04；"
        "5.下一周期外部CSR File将读数据稳定在csr_rdata_i[31:0]=0x00000005（1 cycle读延迟）；"
        "6.TA阶段：1 cycle turnaround，pdo_oe_o=0；"
        "7.TX阶段：pdo_oe_o=1，pdo_o[15:0]输出40bit响应{status_code(8)+rdata(32)}=0x00_00000005需3拍；"
        "期望结果："
        "1.RX 1拍→ISSUE 1拍(csr_rd_en_o)→1 cycle读延迟(csr_rdata_i有效)→TA 1拍→TX 3拍；"
        "2.csr_rd_en_o单周期脉冲有效，同周期csr_addr_o=0x04；"
        "3.csr_rdata_i[31:0]在csr_rd_en_o下一周期有效，值为0x00000005；"
        "4.TX 3拍输出：第1拍{0x00,0x00}(status+高16bit rdata)，第2拍中16bit，第3拍低16bit=0x0005；"
        "5.RD_CSR响应40bit(status_code=STS_OK(0x00)+rdata=0x00000005)正确；coverage check点：覆盖16-bit RD_CSR读时序场景，收集csr_rd_en_o脉冲与1-cycle读延迟交叉覆盖率",

        None,
        ["TP_016"],
        ["CHK_APLC_007"]
    ),
    (
        "TC_APLC_030",
        "test_ahb_wr32_16bit_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终；"
        "输入激励："
        "1.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xCAFEBABE)；"
        "2.RX阶段：pdi_i[15:0]在5个clk_i周期输入72bit帧数据（{0x20,0x10000000,0xCAFEBABE}），rx_count_q按16步进；"
        "3.ISSUE阶段：frame_valid后进入AXI_REQ态，驱动htrans_o=NONSEQ(2'b10)，haddr_o=0x10000000，hwrite_o=1，hburst_o=SINGLE(3'b000)；"
        "4.AXI_WAIT阶段：htrans_o=IDLE(2'b00)，驱动hwdata_o=0xCAFEBABE，等待hready_i=1采样；"
        "5.TA阶段：AHB完成1 cycle turnaround，pdo_oe_o=0；"
        "6.TX阶段：pdo_oe_o=1，pdo_o[15:0]输出8bit状态码STS_OK(0x00)占1拍；"
        "期望结果："
        "1.RX 5拍(72bit/16bpc)→AXI_REQ(NONSEQ,地址相)→AXI_WAIT(hwdata,数据相)→TA 1拍→TX 1拍；"
        "2.htrans_o在AXI_REQ态=NONSEQ(2'b10)，AXI_WAIT态=IDLE(2'b00)，hsize_o=3'b010(WORD)；"
        "3.hwdata_o在AXI_WAIT态有效输出0xCAFEBABE，hready_i=1时AHB事务完成；"
        "4.TX输出status_code=STS_OK(0x00)，AHB写入成功；"
        "5.AHB 2-phase流水时序正确：T1地址相→T2数据相；coverage check点：覆盖16-bit AHB_WR32完整时序场景，收集AXI_REQ->AXI_WAIT->TA->TX路径覆盖率",

        None,
        ["TP_017"],
        ["CHK_APLC_007"]
    ),
    (
        "TC_APLC_031",
        "test_ahb_rd32_16bit_timing",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终，hrdata_i预设已知值0xDEADC0DE；"
        "输入激励："
        "1.发送AHB_RD32命令(opcode=0x21, addr=0x20000000)；"
        "2.RX阶段：pdi_i[15:0]在3个clk_i周期输入40bit帧数据（{0x21,0x20000000}），rx_count_q按16步进0→16→32→40；"
        "3.ISSUE阶段：frame_valid后进入AXI_REQ态，驱动htrans_o=NONSEQ(2'b10)，haddr_o=0x20000000，hwrite_o=0，hburst_o=SINGLE(3'b000)；"
        "4.AXI_WAIT阶段：htrans_o=IDLE，hready_i=1时采样hrdata_i=0xDEADC0DE；"
        "5.TA阶段：1 cycle turnaround，pdo_oe_o=0；"
        "6.TX阶段：pdo_oe_o=1，pdo_o[15:0]输出40bit响应{STS_OK(0x00)+0xDEADC0DE}需3拍；"
        "期望结果："
        "1.RX 3拍(40bit/16bpc)→AXI_REQ(NONSEQ)→AXI_WAIT(hrdata)→TA 1拍→TX 3拍；"
        "2.htrans_o在AXI_REQ态=NONSEQ(2'b10)，haddr_o=0x20000000，hwrite_o=0(读)，hsize_o=3'b010；"
        "3.AXI_WAIT态hready_i=1时采样hrdata_i=0xDEADC0DE；"
        "4.TX 3拍输出40bit：{STS_OK(0x00),0xDEADC0DE}正确，pdo_oe_o=1连续3拍；"
        "5.AHB_RD32响应格式40bit(status_code+read_data)与LRS规格一致；coverage check点：覆盖16-bit AHB_RD32完整时序场景，收集AXI_REQ->AXI_WAIT->TA->TX路径覆盖率",

        None,
        ["TP_018"],
        ["CHK_APLC_007"]
    ),
    (
        "TC_APLC_032",
        "test_rd_burst_incr4_16bit",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终，hrdata_i按beat返回4个32bit数据；"
        "输入激励："
        "1.发送AHB_RD_BURST命令(opcode=0x23, burst_len=4, addr=0x10000000)；"
        "2.RX阶段：3拍输入48bit header（{0x23, burst_len=4, rsvd=0, addr=0x10000000}）；"
        "3.AHB执行：axi_state进入AXI_REQ态，首拍htrans_o=NONSEQ(2'b10)，后续3拍htrans_o=SEQ(2'b11)，hburst_o=INCR4(3'b011)稳定；"
        "4.AXI_WAIT态：逐拍采样hready_i=1和hrdata_i，haddr_o每拍+4(0x10000000→0x10000004→0x10000008→0x1000000C)；"
        "5.TA阶段：1 cycle turnaround；"
        "6.TX_BURST阶段：pdo_oe_o=1连续输出17拍响应（8bit status+4×32bit data=136bit/16bpc≈9拍，含status头）；"
        "期望结果："
        "1.hburst_o=INCR4(3'b011)在整个burst期间保持稳定不翻转；"
        "2.首拍htrans_o=NONSEQ(2'b10)，后续3拍htrans_o=SEQ(2'b11)，haddr每拍+4；"
        "3.TX_BURST输出：先8bit status_code=STS_OK(0x00)，再4×32bit read data连续输出无额外turnaround；"
        "4.pdo_oe_o在TX_BURST期间连续有效直至最后beat完成；"
        "5.hsize_o固定3'b010(WORD)，burst_len=4对应INCR4映射正确；coverage check点：覆盖INCR4读Burst场景，收集hburst_o=INCR4(3b011)与htrans_o交叉覆盖率",

        None,
        ["TP_019"],
        ["CHK_APLC_008"]
    ),
    (
        "TC_APLC_033",
        "test_rd_burst_incr8_16bit",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终，hrdata_i按beat返回8个32bit数据；"
        "输入激励："
        "1.发送AHB_RD_BURST命令(opcode=0x23, burst_len=8, addr=0x20000000)；"
        "2.RX阶段：3拍输入48bit header（{0x23, burst_len=8, rsvd=0, addr=0x20000000}）；"
        "3.AHB执行：axi_state进入AXI_REQ态，首拍htrans_o=NONSEQ(2'b10)，后续7拍htrans_o=SEQ(2'b11)，hburst_o=INCR8(3'b101)稳定；"
        "4.AXI_WAIT态：逐拍采样hready_i=1和hrdata_i，haddr_o从0x20000000每拍+4递增；"
        "5.TA阶段：1 cycle turnaround，pdo_oe_o=0；"
        "6.TX_BURST阶段：pdo_oe_o=1连续输出17拍响应（8bit status+8×32bit data=264bit/16bpc≈17拍）；"
        "期望结果："
        "1.hburst_o=INCR8(3'b101)在整个burst期间保持稳定不翻转；"
        "2.首拍htrans_o=NONSEQ(2'b10)，后续7拍htrans_o=SEQ(2'b11)，共8拍地址相；"
        "3.TX_BURST输出：先8bit status_code=STS_OK(0x00)，再8×32bit read data连续输出，beat间无额外turnaround；"
        "4.pdo_oe_o在TX_BURST期间连续有效直至最后beat完成；"
        "5.burst_len=8对应INCR8映射正确：hburst_o=3'b101，NONSEQ+SEQ×7共8拍；coverage check点：覆盖INCR8读Burst场景，收集hburst_o=INCR8(3b101)与burst_len=8交叉覆盖率",

        None,
        ["TP_020"],
        ["CHK_APLC_008"]
    ),
    (
        "TC_APLC_034",
        "test_wr_burst_incr4_16bit",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终；"
        "输入激励："
        "1.发送AHB_WR_BURST命令(opcode=0x22, burst_len=4, addr=0x30000000, wdata=4个32bit随机数据)；"
        "2.RX阶段：3拍输入48bit header，随后8拍输入128bit payload（4×32bit，每32bit需2拍16bit），修正expected_rx_bits=48+128=176bit；"
        "3.Burst写payload每凑够32bit推入SLC_RXFIFO，rxfifo_cnt[5:0]递增；"
        "4.AHB执行：BURST_LOOP从RXFIFO读取数据，axi_state进入AXI_REQ+AXI_BURST，hburst_o=INCR4(3'b011)；"
        "5.首拍htrans_o=NONSEQ(2'b10)，后续3拍htrans_o=SEQ(2'b11)，hwdata_o逐拍输出4×32bit；"
        "6.TA阶段：1 cycle turnaround；TX阶段输出8bit STS_OK(0x00)；"
        "期望结果："
        "1.RX 11拍(48bit header+128bit payload=176bit/16bpc)→AXI_REQ+AXI_BURST→TA→TX 1拍；"
        "2.Burst写payload每32bit beat推入RXFIFO，rxfifo_cnt[5:0]反映当前FIFO占用；"
        "3.hburst_o=INCR4(3'b011)稳定，首拍NONSEQ+后续3拍SEQ，hwdata_o逐拍输出4×32bit payload；"
        "4.TX输出status_code=STS_OK(0x00)，AHB写入成功；"
        "5.burst_len=4对应INCR4映射正确，BURST_LOOP正确drain RXFIFO；coverage check点：覆盖INCR4写Burst场景，收集RXFIFO推入与rxfifo_cnt递增与AXI_BURST路径覆盖率",

        None,
        ["TP_021"],
        ["CHK_APLC_008"]
    ),
    (
        "TC_APLC_035",
        "test_frame_abort_opcode_latched",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，模块正常工作；"
        "输入激励："
        "1.开始发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.RX阶段：第1拍pdi_i[15:0]输入{0x10,0x04}，opcode=0x10已锁存(opcode_latched_q有效)；"
        "3.在rx_count_q=16（已收2拍，opcode已锁存但帧未完成）时提前拉高pcs_ni触发frame_abort；"
        "4.观察SLC_DPCHK检测到frame_abort条件：pcs_ni在rx_count<expected_rx_bits时提前拉高；"
        "5.检查响应状态码是否为STS_FRAME_ERR(0x01)；"
        "6.检查STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01；"
        "期望结果："
        "1.pcs_ni提前拉高且opcode已锁存时触发frame_abort，返回STS_FRAME_ERR(0x01)；"
        "2.STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01记录帧错误；"
        "3.不发起CSR/AHB访问（无csr_wr_en_o脉冲，无htrans_o=NONSEQ）；"
        "4.前端FSM走IDLE→ISSUE→TA→TX路径返回STS_FRAME_ERR(0x01)；"
        "5.frame_abort在发起CSR/AHB访问前收敛，符合前置优先级链最高优先级STS_FRAME_ERR(0x01)；coverage check点：覆盖frame_abort(opcode已锁存)场景，收集STS_FRAME_ERR(0x01)前置优先级链覆盖率",

        None,
        ["TP_029"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_036",
        "test_frame_abort_opcode_not_latched",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，模块正常工作；"
        "输入激励："
        "1.开始发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.RX阶段：第1拍pdi_i[15:0]输入{0x10,0x04}，但在rx_count_q<8时（opcode未锁存，不足8bit）提前拉高pcs_ni；"
        "3.在16-bit模式下第1拍rx_count_q=16已含8bit opcode，因此切换至1-bit模式测试：rx_count_q=4时拉高pcs_ni（不足8bit，opcode_latched_q无效）；"
        "4.观察SLC_DPCHK检测到pcs_ni提前拉高但opcode未锁存，执行静默复位(silent reset)；"
        "5.检查无STS_FRAME_ERR(0x01)返回，前端FSM直接回IDLE不发起响应；"
        "6.验证STATUS寄存器无sticky错误位置位，LAST_ERR不变；"
        "期望结果："
        "1.opcode未锁存时(pcs_ni提前拉高且rx_count<8bit)执行静默复位，不返回STS_FRAME_ERR(0x01)；"
        "2.前端FSM直接回到IDLE，不发起任何响应（无TX阶段，pdo_oe_o不拉高）；"
        "3.STATUS寄存器无sticky错误位置位，LAST_ERR保持原值不变；"
        "4.不发起CSR/AHB访问（无csr_wr_en_o/csr_rd_en_o脉冲，无htrans_o=NONSEQ）；"
        "5.静默复位后模块可正常接受下一命令，新命令返回STS_OK(0x00)；coverage check点：覆盖frame_abort(opcode未锁存)场景，收集静默复位与opcode_latched_q状态交叉覆盖率",

        None,
        ["TP_029"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_037",
        "test_rxfifo_full_backpressure",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，RXFIFO深度32×32bit；"
        "输入激励："
        "1.发送AHB_WR_BURST命令(opcode=0x22, burst_len=16, addr=0x10000000, wdata=16×32bit=512bit随机数据)；"
        "2.RX阶段：Burst写payload每32bit推入SLC_RXFIFO，rxfifo_cnt[5:0]递增；"
        "3.当rxfifo_cnt[5:0]=32时rxfifo_full_o=1，SLC_CAXIS暂停rx_shift_en和rxfifo_wr_en；"
        "4.后端BURST_LOOP通过rxfifo_rd_en drain RXFIFO数据写入AHB，rxfifo_full_o清零；"
        "5.观察反压暂停和恢复过程：rxfifo_full_o=1→rx_shift_en=0→rxfifo_rd_en drain→rxfifo_full_o=0→rx_shift_en恢复；"
        "6.验证反压后命令仍正确完成返回STS_OK(0x00)；"
        "期望结果："
        "1.RXFIFO填充至32时rxfifo_full_o=1，SLC_CAXIS暂停rx_shift_en和rxfifo_wr_en；"
        "2.后端BURST_LOOP通过rxfifo_rd_en drain数据后rxfifo_full_o清零恢复接收；"
        "3.反压暂停和恢复过程中无数据丢失，所有16×32bit payload正确写入AHB；"
        "4.AHB_WR_BURST命令最终返回STS_OK(0x00)；"
        "5.RXFIFO门控条件：rxfifo_empty_o=1时后端BURST_LOOP写数据通道不翻转；coverage check点：覆盖RXFIFO满反压场景，收集rxfifo_full_o=1与rx_shift_en暂停恢复交叉覆盖率",

        None,
        ["TP_047"],
        ["CHK_APLC_006"]
    ),
    (
        "TC_APLC_038",
        "test_txfifo_empty_stall",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，TXFIFO深度32×33bit，AHB从端hready_i有延迟响应；"
        "输入激励："
        "1.发送AHB_RD_BURST命令(opcode=0x23, burst_len=4, addr=0x20000000)；"
        "2.AHB执行：AXI_REQ→AXI_WAIT逐拍读取4个32bit数据推入SLC_TXFIFO；"
        "3.前端TX序列化逻辑从TXFIFO读取数据输出，若TXFIFO暂时为空(txfifo_empty_o=1)则SLC_SAXIS暂停移位；"
        "4.验证pdo_oe_o在TX_BURST期间保持高电平即使TXFIFO暂时为空（stall不释放pdo_oe_o）；"
        "5.当TXFIFO重新有数据(txfifo_empty_o=0)后SLC_SAXIS恢复移位输出；"
        "6.验证最终4×32bit read data完整输出无丢失；"
        "期望结果："
        "1.TXFIFO空时(txfifo_empty_o=1)SLC_SAXIS暂停移位，但pdo_oe_o保持高电平不释放；"
        "2.TXFIFO重新有数据后移位恢复，pdo_o[15:0]继续输出后续beat数据；"
        "3.4×32bit read data完整输出无丢失，beat间无额外turnaround；"
        "4.pdo_oe_o在整个TX_BURST期间连续有效直至最后beat完成；"
        "5.TXFIFO门控条件：txfifo_empty_o=1时前端TX序列化逻辑不启动翻转；coverage check点：覆盖TXFIFO空stall场景，收集txfifo_empty_o=1与pdo_oe_o保持高电平交叉覆盖率",

        None,
        ["TP_048"],
        ["CHK_APLC_006"]
    ),
    (
        "TC_APLC_039",
        "test_all_lane_frame_format",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.随机选择lane_mode_i∈{2'b00(1-bit),2'b01(4-bit),2'b10(8-bit),2'b11(16-bit)}；"
        "3.CTRL.EN=1，随机选择opcode；"
        "输入激励："
        "1.随机选择lane_mode和opcode的组合：4种lane_mode×6种opcode(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32/AHB_WR_BURST/AHB_RD_BURST)=24种组合；"
        "2.对每种组合发送对应命令，验证帧接收拍数与bpc匹配（1-bit:48/bpc=48拍,4-bit:48/4=12拍,8-bit:48/8=6拍,16-bit:48/16=3拍）；"
        "3.验证RX阶段rx_count_q按bpc步进递增；"
        "4.验证TA阶段固定1 cycle turnaround，pdo_oe_o=0；"
        "5.验证TX/TX_BURST阶段pdo_oe_o=1，响应数据格式正确（8bit status或40bit status+data）；"
        "6.重复执行N≥24次确保覆盖所有组合；"
        "期望结果："
        "1.所有24种lane_mode×opcode组合命令均返回STS_OK(0x00)或预期状态码；"
        "2.帧接收拍数与bpc严格匹配，rx_count_q按正确步长递增；"
        "3.TA阶段固定1 cycle turnaround，TX/TX_BURST阶段pdo_oe_o=1，帧格式与LRS规格一致；"
        "4.不同lane_mode下pdi_i/pdo_o有效位宽正确：1-bit仅[0]，4-bit[3:0]，8-bit[7:0]，16-bit[15:0]；"
        "5.Burst命令的expected_rx_bits修正(48+32·burst_len)正确；coverage check点：覆盖4种lane_mode与6种opcode=24种组合帧格式场景，收集全交叉覆盖率",

        None,
        ["TP_014", "TP_015", "TP_016", "TP_017", "TP_018"],
        ["CHK_APLC_005", "CHK_APLC_007"]
    ),
    (
        "TC_APLC_040",
        "test_burst_frame_random",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.随机选择lane_mode_i和burst_len；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终；"
        "输入激励："
        "1.随机选择burst_len∈{1,4,8,16}和lane_mode∈{2'b00,2'b01,2'b10,2'b11}共16种组合；"
        "2.发送AHB_WR_BURST命令(opcode=0x22, 随机burst_len, 随机addr=4对齐, 随机wdata)；"
        "3.发送AHB_RD_BURST命令(opcode=0x23, 随机burst_len, 随机addr=4对齐)；"
        "4.验证Burst header两段式解析：前8bit锁定opcode_latched_q，收满16bit后提取burst_len_latched_q[4:0]；"
        "5.验证AHB_WR_BURST修正expected_rx_bits=48+32·burst_len，AHB_RD_BURST保持48；"
        "6.验证hburst_o映射：1→SINGLE(3'b000),4→INCR4(3'b011),8→INCR8(3'b101),16→INCR16(3'b111)；"
        "7.重复执行N≥32次覆盖所有组合；"
        "期望结果："
        "1.所有16种burst_len×lane_mode组合命令均返回STS_OK(0x00)；"
        "2.Burst header两段式解析正确：opcode_latched_q和burst_len_latched_q[4:0]提取无误；"
        "3.AHB_WR_BURST的expected_rx_bits=48+32·burst_len修正正确，RX拍数与lane_mode匹配；"
        "4.hburst_o映射正确：1→3'b000,4→3'b011,8→3'b101,16→3'b111；"
        "5.Burst写payload推入RXFIFO，Burst读返回数据推入TXFIFO，FIFO流控正常；coverage check点：覆盖burst_len与lane_mode=16种组合Burst帧格式场景，收集全交叉覆盖率",

        None,
        ["TP_019", "TP_020", "TP_021"],
        ["CHK_APLC_008"]
    ),
    # ===== Category E: Opcode & Control (TC_APLC_041~048) =====
    (
        "TC_APLC_041",
        "test_bad_opcode_0xff",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，模块正常工作；"
        "输入激励："
        "1.发送opcode=0xFF的非法命令，帧格式：{0xFF, reg_addr=0x04}（16bit RX在1拍内完成）；"
        "2.观察SLC_CCMD接收到opcode=0xFF后无法匹配任何合法opcode{0x10,0x11,0x20,0x21,0x22,0x23}；"
        "3.检查前置检查返回STS_BAD_OPCODE(0x02)；"
        "4.验证不产生csr_wr_en_o/csr_rd_en_o脉冲，不产生htrans_o=NONSEQ；"
        "5.检查STATUS[2]=CMD_ERR(sticky)置位，LAST_ERR[7:0]=0x02；"
        "6.发送合法WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)验证模块恢复正常；"
        "期望结果："
        "1.opcode=0xFF返回STS_BAD_OPCODE(0x02)，SLC_CCMD正确译码拒绝非法opcode；"
        "2.不产生csr_wr_en_o/csr_rd_en_o脉冲和htrans_o=NONSEQ，CSR/AHB访问均不发起；"
        "3.STATUS[2]=CMD_ERR(sticky)置位，LAST_ERR[7:0]=0x02记录非法opcode错误；"
        "4.后续合法WR_CSR命令正常返回STS_OK(0x00)，模块从错误中恢复；"
        "5.STS_BAD_OPCODE(0x02)位于前置优先级链中，在发起CSR/AHB访问前收敛；coverage check点：覆盖非法opcode=0xFF场景，收集STS_BAD_OPCODE(0x02)前置优先级链覆盖率",

        None,
        ["TP_022"],
        ["CHK_APLC_009"]
    ),
    (
        "TC_APLC_042",
        "test_all_legal_opcodes",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)，检查返回STS_OK(0x00)；"
        "2.发送RD_CSR命令(opcode=0x11, reg_addr=0x04(CTRL))，检查返回STS_OK(0x00)和csr_rdata_i；"
        "3.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0x12345678)，检查返回STS_OK(0x00)；"
        "4.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)，检查返回STS_OK(0x00)和hrdata_i；"
        "5.发送AHB_WR_BURST命令(opcode=0x22, burst_len=4, addr=0x20000000, wdata随机)，检查返回STS_OK(0x00)；"
        "6.发送AHB_RD_BURST命令(opcode=0x23, burst_len=4, addr=0x20000000)，检查返回STS_OK(0x00)；"
        "7.验证6种opcode的td_cmd_type译码与通道选择(CSR/AHB)正确；"
        "期望结果："
        "1.6种合法opcode{0x10,0x11,0x20,0x21,0x22,0x23}均返回STS_OK(0x00)；"
        "2.CSR类opcode(0x10/0x11)走SLC_DPIPE CSR通道，驱动csr_wr_en_o/csr_rd_en_o；"
        "3.AHB类opcode(0x20/0x21/0x22/0x23)走SLC_SAXIM AHB Master通道，驱动htrans_o=NONSEQ；"
        "4.Burst opcode(0x22/0x23)的td_burst_len[4:0]和td_hburst[2:0]由SLC_CCMD从burst_len编码生成；"
        "5.SLC_CCMD正确译码6种合法opcode为td_cmd_type，无译码冲突；coverage check点：覆盖6种合法opcode遍历场景，收集td_cmd_type译码与通道选择全交叉覆盖率",

        None,
        ["TP_023"],
        ["CHK_APLC_009"]
    ),
    (
        "TC_APLC_043",
        "test_ctrl_lane_mode_config",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，CTRL(0x04,RW)字段：EN(bit0)/LANE_MODE[1:0](bits[2:1])/SOFT_RST(bit3)；"
        "输入激励："
        "1.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)设置EN=1/LANE_MODE=2'b00(1-bit)；"
        "2.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))读回验证LANE_MODE=2'b00；"
        "3.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000003)设置EN=1/LANE_MODE=2'b01(4-bit)；"
        "4.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))读回验证LANE_MODE=2'b01；"
        "5.依次写入LANE_MODE=2'b10(8-bit, wdata=0x05)和LANE_MODE=2'b11(16-bit, wdata=0x07)并读回验证；"
        "6.验证各LANE_MODE下命令执行正常（WR_CSR返回STS_OK(0x00)）；"
        "期望结果："
        "1.CTRL.LANE_MODE=2'b00读回0x00000001，EN=1/LANE_MODE=1-bit验证通过；"
        "2.CTRL.LANE_MODE=2'b01读回0x00000003，EN=1/LANE_MODE=4-bit验证通过；"
        "3.CTRL.LANE_MODE=2'b10读回0x00000005，EN=1/LANE_MODE=8-bit验证通过；"
        "4.CTRL.LANE_MODE=2'b11读回0x00000007，EN=1/LANE_MODE=16-bit验证通过；"
        "5.各LANE_MODE配置下WR_CSR命令正常返回STS_OK(0x00)，CTRL寄存器RW属性正确；coverage check点：覆盖CTRL.LANE_MODE各值(2b00/01/10/11)配置读回场景，收集LANE_MODE与RW属性覆盖率",

        None,
        ["TP_024"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_044",
        "test_ctrl_soft_reset",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，CTRL.LANE_MODE=2'b11，模块已执行若干命令；"
        "输入激励："
        "1.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000007)设置EN=1/LANE_MODE=2'b11；"
        "2.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))确认读回0x07；"
        "3.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000008)写SOFT_RST=1(bit3=1)触发软复位；"
        "4.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))读取软复位后CTRL值；"
        "5.发送RD_CSR(opcode=0x11, reg_addr=0x08(STATUS))检查STATUS是否清除了协议上下文；"
        "6.执行AHB_RD32命令(opcode=0x21, addr=0x10000000)验证软复位后模块仍可工作；"
        "期望结果："
        "1.写SOFT_RST=1前CTRL读回0x07(EN=1, LANE_MODE=2'b11, SOFT_RST=0)；"
        "2.写SOFT_RST=1后CTRL.EN=0/LANE_MODE=2'b00，协议上下文清零恢复默认lane模式；"
        "3.SOFT_RST位自清零：写入1后下一拍自动回0（单次触发）；"
        "4.软复位不清FIFO：rxfifo_empty_o/txfifo_empty_o状态不变；"
        "5.软复位后模块可正常接受新命令，AHB_RD32返回STS_OK(0x00)；coverage check点：覆盖CTRL.SOFT_RST=1软复位场景，收集SOFT_RST触发与上下文清零恢复覆盖率",

        None,
        ["TP_024"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_045",
        "test_lane_switch_at_idle",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.初始lane_mode_i=2'b00（1-bit模式）；"
        "3.CTRL.EN=1，模块空闲态(pcs_ni=1)；"
        "输入激励："
        "1.在pcs_ni=1期间将lane_mode_i从2'b00切换为2'b01（4-bit模式）；"
        "2.等待≥2个clk_i周期同步后发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "3.验证4-bit模式下帧接收12拍正常完成，返回STS_OK(0x00)；"
        "4.在pcs_ni=1期间将lane_mode_i从2'b01切换为2'b10（8-bit模式）；"
        "5.等待≥2个clk_i周期后发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xABCD1234)；"
        "6.验证8-bit模式下帧接收9拍(72bit/8bpc)正常完成返回STS_OK(0x00)；"
        "7.继续切换至2'b11(16-bit)并验证命令正常；"
        "期望结果："
        "1.pcs_ni=1期间切换lane_mode_i后新命令按新bpc工作，所有命令返回STS_OK(0x00)；"
        "2.4-bit模式WR_CSR：12拍RX→TA→TX，帧格式正确；"
        "3.8-bit模式AHB_WR32：9拍RX→AXI_REQ→AXI_WAIT→TA→TX，htrans_o=NONSEQ正常；"
        "4.16-bit模式命令正常工作，帧接收3拍(48bit/16bpc)；"
        "5.lane_mode_i仅在空闲态(pcs_ni=1)切换不触发任何错误，STATUS无sticky位置位；coverage check点：覆盖空闲态lane_mode切换场景，收集lane_mode切换与新bpc命令执行交叉覆盖率",

        None,
        ["TP_024"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_046",
        "test_lane_switch_mid_rx",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.初始lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，模块正在执行WR_CSR命令RX阶段；"
        "输入激励："
        "1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)，16-bit模式RX需3拍；"
        "2.在RX第2拍（rx_count_q=32时，帧未完成）将lane_mode_i从2'b11切换为2'b01（4-bit模式）；"
        "3.观察SLC_CAXIS移位寄存器步进宽度从bpc=16突变至bpc=4，帧数据错位；"
        "4.检查命令响应状态码：可能返回STS_FRAME_ERR(0x01)或STS_BAD_OPCODE(0x02)；"
        "5.检查STATUS[4]=FRAME_ERR或STATUS[2]=CMD_ERR sticky位置位；"
        "6.等待pcs_ni=1后恢复lane_mode_i=2'b11，发送新命令验证模块可恢复；"
        "期望结果："
        "1.RX阶段中途切换lane_mode_i导致bpc突变，帧数据错位触发错误；"
        "2.返回STS_FRAME_ERR(0x01)或STS_BAD_OPCODE(0x02)，STATUS对应sticky位置位；"
        "3.SLC_CAXIS连续组合采样lane_mode_i计算bpc，切换后步进宽度立即改变；"
        "4.pcs_ni=1后恢复lane_mode_i=2'b11，新命令正常返回STS_OK(0x00)；"
        "5.lane_mode_i在事务执行期间(pcs_ni=0)必须保持稳定否则帧损坏；coverage check点：覆盖RX阶段lane_mode切换场景，收集lane_mode切换与STS_FRAME_ERR/STS_BAD_OPCODE交叉覆盖率",

        None,
        ["TP_025"],
        ["CHK_APLC_010"]
    ),
    (
        "TC_APLC_047",
        "test_opcode_random_legal",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i=1始终，hresp_i=0始终；"
        "输入激励："
        "1.随机选择opcode：合法opcode∈{0x10,0x11,0x20,0x21,0x22,0x23}和非法opcode∈{0x00,0xFF,0x30,0x50,0x7F,0xAB}；"
        "2.对每个随机opcode发送对应帧格式的命令；"
        "3.合法opcode验证返回STS_OK(0x00)，检查CSR/AHB通道选择正确；"
        "4.非法opcode验证返回STS_BAD_OPCODE(0x02)，检查无CSR/AHB访问脉冲；"
        "5.对CSR类opcode(0x10/0x11)验证csr_wr_en_o/csr_rd_en_o脉冲产生；"
        "6.对AHB类opcode(0x20/0x21/0x22/0x23)验证htrans_o=NONSEQ产生；"
        "7.重复执行N≥200次，覆盖合法与非法opcode的广泛范围；"
        "期望结果："
        "1.合法opcode{0x10,0x11,0x20,0x21,0x22,0x23}返回STS_OK(0x00)，通道选择(CSR/AHB)正确；"
        "2.非法opcode返回STS_BAD_OPCODE(0x02)，不产生csr_wr_en_o/csr_rd_en_o脉冲和htrans_o=NONSEQ；"
        "3.CSR类opcode驱动csr_wr_en_o/csr_rd_en_o，AHB类opcode驱动htrans_o=NONSEQ；"
        "4.Burst opcode(0x22/0x23)的td_burst_len和td_hburst编码正确；"
        "5.N≥200次随机测试中SLC_CCMD译码100%正确，无译码冲突或漏判；coverage check点：覆盖合法/非法opcode随机场景N>=200次，收集opcode值域与STS_OK/STS_BAD_OPCODE交叉覆盖率",

        None,
        ["TP_022", "TP_023"],
        ["CHK_APLC_009"]
    ),
    (
        "TC_APLC_048",
        "test_config_random_combo",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.随机配置lane_mode_i和CTRL寄存器字段；"
        "3.CTRL(0x04,RW)字段：EN(bit0)/LANE_MODE[1:0](bits[2:1])/SOFT_RST(bit3)；"
        "输入激励："
        "1.随机生成CTRL wdata：EN∈{0,1}，LANE_MODE∈{2'b00,2'b01,2'b10,2'b11}，SOFT_RST∈{0,1}；"
        "2.发送WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=随机值)写入CTRL；"
        "3.发送RD_CSR(opcode=0x11, reg_addr=0x04(CTRL))读回验证CTRL值；"
        "4.随机切换lane_mode_i∈{2'b00,2'b01,2'b10,2'b11}（仅在pcs_ni=1时切换）；"
        "5.验证CTRL.LANE_MODE写入值与lane_mode_i一致性对命令执行的影响；"
        "6.验证SOFT_RST=1触发上下文清零恢复默认LANE_MODE=2'b00；"
        "7.重复执行N≥100次覆盖各种CTRL字段×lane_mode组合；"
        "期望结果："
        "1.CTRL写后读回一致，EN/LANE_MODE/SOFT_RST字段RW属性正确；"
        "2.SOFT_RST=1触发协议上下文清零，CTRL.EN=0/LANE_MODE=2'b00恢复默认，SOFT_RST自清零；"
        "3.lane_mode_i在pcs_ni=1期间切换后新命令按新bpc工作，返回STS_OK(0x00)；"
        "4.EN=0时命令返回STS_DISABLED(0x08)，EN=1时命令正常返回STS_OK(0x00)；"
        "5.N≥100次随机组合中CTRL配置与lane_mode切换行为全部符合LRS规格；coverage check点：覆盖CTRL字段随机组合场景N>=100次，收集EN与LANE_MODE与SOFT_RST字段交叉覆盖率",

        None,
        ["TP_024", "TP_025"],
        ["CHK_APLC_010"]
    ),
    # ===== Category F: Interrupt & Status (TC_APLC_049~052) =====
    (
        "TC_APLC_049",
        "test_status_register_poll",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，STATUS(0x08,RO)位域：BUSY/RESP_VALID/CMD_ERR/BUS_ERR/FRAME_ERR/IN_TEST_MODE/OUT_EN/BURST_ERR；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x08(STATUS))读取初始值，验证BUSY=0/RESP_VALID=0/sticky位=0；"
        "2.发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x01)执行成功命令；"
        "3.命令执行期间轮询STATUS验证BUSY=1/RESP_VALID变化；"
        "4.触发错误：test_mode_i=0时发命令使STATUS[2]=CMD_ERR(sticky)置位；"
        "5.恢复test_mode_i=1后轮询STATUS验证IN_TEST_MODE位镜像test_mode_i；"
        "6.发送非法opcode=0xFF使STATUS[2]=CMD_ERR(sticky)置位，轮询验证；"
        "期望结果："
        "1.复位后STATUS：BUSY=0，RESP_VALID=0，所有sticky位=0，IN_TEST_MODE=1，OUT_EN=0；"
        "2.命令执行期间STATUS[0]=BUSY=1，完成后RESP_VALID=1；"
        "3.test_mode_i=0时STATUS[5]=IN_TEST_MODE=0，触发错误后CMD_ERR(sticky)置位；"
        "4.非法opcode后STATUS[2]=CMD_ERR(sticky)置位；"
        "5.STATUS[6]=OUT_EN镜像pdo_oe_o，STATUS[5]=IN_TEST_MODE镜像test_mode_i；coverage check点：覆盖STATUS寄存器轮询场景，收集STATUS各bit位变化与BUSY/RESP_VALID/IN_TEST_MODE覆盖率",

        None,
        ["TP_026"],
        ["CHK_APLC_011"]
    ),
    (
        "TC_APLC_050",
        "test_last_err_sticky",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，LAST_ERR(0x0C,RO)保存最近错误码(sticky)；"
        "输入激励："
        "1.发送RD_CSR命令(opcode=0x11, reg_addr=0x0C(LAST_ERR))读取复位后初始值=0x00；"
        "2.触发STS_BAD_OPCODE(0x02)：发送非法opcode=0xFF命令，读取LAST_ERR验证=0x02；"
        "3.触发STS_NOT_IN_TEST(0x04)：拉低test_mode_i=0发命令，读取LAST_ERR验证=0x04（覆盖0x02）；"
        "4.触发STS_DISABLED(0x08)：test_mode_i=1但en_i=0发命令，读取LAST_ERR验证=0x08（覆盖0x04）；"
        "5.触发STS_BAD_REG(0x10)：发送RD_CSR(reg_addr=0x40)越界访问，读取LAST_ERR验证=0x10；"
        "6.连续执行成功命令(WR_CSR正常)后验证LAST_ERR保持最近错误值不变（sticky不清零）；"
        "期望结果："
        "1.复位后LAST_ERR[7:0]=0x00；"
        "2.每次触发错误后LAST_ERR更新为对应错误码(0x02→0x04→0x08→0x10)，新错误覆盖旧值；"
        "3.连续成功命令后LAST_ERR保持最近错误值不变，sticky不清零；"
        "4.LAST_ERR由WC语义清除：WR_CSR(LAST_ERR, wdata=1)写1清零后读回0x00；"
        "5.LAST_ERR[7:0]位域完整覆盖所有错误码{0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80}；coverage check点：覆盖LAST_ERR sticky行为场景，收集错误码序列覆盖和WC清除覆盖率",

        None,
        ["TP_026"],
        ["CHK_APLC_011"]
    ),
    (
        "TC_APLC_051",
        "test_no_irq_output",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，v2.2设计不实现独立中断输出端口(IRQ)；"
        "输入激励："
        "1.执行成功命令WR_CSR(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x01)，观察无IRQ信号；"
        "2.触发错误：发送非法opcode=0xFF使CMD_ERR置位，观察无IRQ信号；"
        "3.触发STS_AHB_ERR(0x40)：AHB访问期间hresp_i=1，观察无IRQ信号；"
        "4.触发STS_FRAME_ERR(0x01)：中途拉高pcs_ni使frame_abort，观察无IRQ信号；"
        "5.在所有错误场景下轮询STATUS(0x08)和LAST_ERR(0x0C)获取状态，验证轮询机制可行；"
        "6.连续触发多种错误后通过STATUS/LAST_ERR轮询获取完整错误信息；"
        "期望结果："
        "1.v2.2不实现独立IRQ输出端口，所有错误与完成状态通过STATUS和LAST_ERR寄存器查询；"
        "2.成功命令、非法opcode、AHB错误、帧错误场景下均无IRQ信号产生；"
        "3.ATE采用轮询方式：RD_CSR(STATUS)和RD_CSR(LAST_ERR)可获取完整状态信息；"
        "4.STATUS[1]=RESP_VALID标志最近响应有效，STATUS sticky位反映各类错误；"
        "5.LAST_ERR[7:0]记录最近错误码，支持ATE精确诊断错误类型；coverage check点：覆盖无IRQ输出场景，收集STATUS/LAST_ERR轮询与各类错误交叉覆盖率",

        None,
        ["TP_026"],
        ["CHK_APLC_011"]
    ),
    (
        "TC_APLC_052",
        "test_status_random_mixed",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式）；"
        "3.CTRL.EN=1，随机混合成功和失败命令；"
        "4.STATUS(0x08,RO)位域：BUSY[0]/RESP_VALID[1]/CMD_ERR[2]/BUS_ERR[3]/FRAME_ERR[4]/IN_TEST_MODE[5]/OUT_EN[6]/BURST_ERR[7]；"
        "输入激励："
        "1.随机选择命令类型：合法命令(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32)和触发错误命令(非法opcode=0xFF/test_mode_i=0/en_i=0)；"
        "2.执行随机命令后立即轮询STATUS(0x08)和LAST_ERR(0x0C)，记录各sticky位状态；"
        "3.验证成功命令STATUS无新增sticky位，LAST_ERR不变；"
        "4.验证失败命令STATUS对应sticky位置位，LAST_ERR更新为错误码；"
        "5.通过WC语义(WR_CSR(BURST_CNT, wdata=1))清除sticky位后验证STATUS恢复；"
        "6.重复执行N≥50次，随机混合成功/失败命令序列；"
        "期望结果："
        "1.成功命令：STATUS无新增sticky位，BUSY=1→0，RESP_VALID=1，LAST_ERR不变；"
        "2.失败命令：STATUS对应sticky位置位(CMD_ERR/BUS_ERR/FRAME_ERR)，LAST_ERR更新为错误码；"
        "3.WC语义清除sticky位后STATUS恢复，BURST_CNT写1清零；"
        "4.STATUS[5]=IN_TEST_MODE镜像test_mode_i，STATUS[6]=OUT_EN镜像pdo_oe_o；"
        "5.N≥50次随机混合序列中STATUS/LAST_ERR行为100%符合LRS规格；coverage check点：覆盖随机成功/失败混合场景N>=50次，收集STATUS sticky位与LAST_ERR更新与WC清除交叉覆盖率",

        None,
        ["TP_026"],
        ["CHK_APLC_011"]
    ),
    # ===== Category G: Error & Priority (TC_APLC_053~060) =====
    (
        "TC_APLC_053",
        "test_frame_err_priority",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，前置错误优先级链：STS_FRAME_ERR(0x01)>STS_BAD_OPCODE(0x02)>...；"
        "输入激励："
        "1.开始发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x00000001)；"
        "2.RX阶段第1拍输入{0x10,0x04}，opcode=0x10已锁存(opcode_latched_q有效)；"
        "3.在rx_count_q=16时提前拉高pcs_ni触发frame_abort，同时opcode可能被替换为非法值(0xFF)；"
        "4.构造同时存在frame_abort和BAD_OPCODE的场景：中途修改pdi_i使opcode_latched_q错位产生非法opcode；"
        "5.检查响应状态码：应返回STS_FRAME_ERR(0x01)（最高优先级）而非STS_BAD_OPCODE(0x02)；"
        "6.验证STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01；"
        "期望结果："
        "1.frame_abort与BAD_OPCODE同时成立时返回STS_FRAME_ERR(0x01)，证明优先级链STS_FRAME_ERR(0x01)>STS_BAD_OPCODE(0x02)；"
        "2.STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01记录帧错误；"
        "3.不产生csr_wr_en_o/csr_rd_en_o脉冲和htrans_o=NONSEQ，前置错误在CSR/AHB访问前收敛；"
        "4.仅报告最高优先级单个错误，不存在多错误同时上报；"
        "5.前端FSM走IDLE→ISSUE→TA→TX路径返回STS_FRAME_ERR(0x01)；coverage check点：覆盖STS_FRAME_ERR(0x01)优先级最高场景，收集frame_abort与BAD_OPCODE同时成立优先级链覆盖率",

        None,
        ["TP_027", "TP_029"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_054",
        "test_bad_opcode_priority",
        "配置条件："
        "1.模块复位完成，test_mode_i=1（正常），en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，前置错误优先级链：STS_BAD_OPCODE(0x02)>STS_NOT_IN_TEST(0x04)>...；"
        "输入激励："
        "1.发送非法opcode=0xFF命令，同时test_mode_i=1（IN_TEST_MODE有效）；"
        "2.第1拍RX输入{0xFF, 随机addr}，opcode=0xFF锁存后SLC_CCMD译码为BAD_OPCODE；"
        "3.构造同时存在BAD_OPCODE和NOT_IN_TEST的场景：在opcode=0xFF帧中间拉低test_mode_i=0；"
        "4.检查响应状态码：应返回STS_BAD_OPCODE(0x02)（优先级高于STS_NOT_IN_TEST(0x04)）；"
        "5.验证STATUS[2]=CMD_ERR(sticky)置位，LAST_ERR[7:0]=0x02；"
        "6.验证不产生CSR/AHB访问脉冲，前置错误在访问前收敛；"
        "期望结果："
        "1.BAD_OPCODE与NOT_IN_TEST同时成立时返回STS_BAD_OPCODE(0x02)，证明优先级链STS_BAD_OPCODE(0x02)>STS_NOT_IN_TEST(0x04)；"
        "2.STATUS[2]=CMD_ERR(sticky)置位，LAST_ERR[7:0]=0x02记录非法opcode错误；"
        "3.不产生csr_wr_en_o/csr_rd_en_o脉冲和htrans_o=NONSEQ；"
        "4.仅报告最高优先级单个错误STS_BAD_OPCODE(0x02)，不叠加STS_NOT_IN_TEST(0x04)；"
        "5.前端FSM走IDLE→ISSUE→TA→TX路径返回STS_BAD_OPCODE(0x02)；coverage check点：覆盖STS_BAD_OPCODE(0x02)优先级场景，收集BAD_OPCODE与NOT_IN_TEST同时成立优先级链覆盖率",

        None,
        ["TP_027"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_055",
        "test_not_in_test_vs_disabled",
        "配置条件："
        "1.模块复位完成，test_mode_i=0，en_i=0；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=0，两个门控条件同时不满足；"
        "4.前置错误优先级链：STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)>...；"
        "输入激励："
        "1.保持test_mode_i=0且en_i=0，发送WR_CSR命令(opcode=0x10, reg_addr=0x04(CTRL), wdata=0x01)；"
        "2.检查响应状态码应返回STS_NOT_IN_TEST(0x04)而非STS_DISABLED(0x08)；"
        "3.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0x12345678)验证一致性；"
        "4.发送AHB_RD_BURST命令(opcode=0x23, burst_len=4, addr=0x10000000)验证Burst同样遵循优先级；"
        "5.仅拉高test_mode_i=1（en_i仍=0）验证返回STS_DISABLED(0x08)；"
        "6.仅拉高en_i=1（test_mode_i仍=0）验证返回STS_NOT_IN_TEST(0x04)；"
        "期望结果："
        "1.test_mode_i=0且en_i=0时返回STS_NOT_IN_TEST(0x04)，证明优先级链STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)；"
        "2.WR_CSR/AHB_WR32/AHB_RD_BURST命令均返回STS_NOT_IN_TEST(0x04)，优先级与命令类型无关；"
        "3.仅拉高test_mode_i=1后返回STS_DISABLED(0x08)，优先级链第二级判定正确；"
        "4.仅拉高en_i=1后仍返回STS_NOT_IN_TEST(0x04)，test_mode_i优先判定；"
        "5.仅报告最高优先级单个错误，不存在多错误同时上报；coverage check点：覆盖STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)优先级场景，收集双重门控优先级判定覆盖率",

        None,
        ["TP_027"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_056",
        "test_align_err_detection",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB命令addr须4-byte对齐(addr[1:0]=2'b00)；"
        "输入激励："
        "1.发送AHB_WR32命令(opcode=0x20, addr=0x10000001, wdata=0xDEADBEEF)，addr[1:0]=2'b01未对齐；"
        "2.检查SLC_DPCHK前置检查检测到addr[1:0]!=2'b00，返回STS_ALIGN_ERR(0x20)；"
        "3.验证不产生htrans_o=NONSEQ，AHB访问不发起；"
        "4.发送AHB_RD32命令(opcode=0x21, addr=0x10000002)，addr[1:0]=2'b10未对齐，验证同样返回STS_ALIGN_ERR(0x20)；"
        "5.发送AHB_WR32命令(opcode=0x20, addr=0x10000003, wdata=0x12345678)，addr[1:0]=2'b11未对齐，验证STS_ALIGN_ERR(0x20)；"
        "6.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xCAFEBABE)，addr[1:0]=2'b00对齐，验证STS_OK(0x00)；"
        "期望结果："
        "1.addr[1:0]=2'b01/2'b10/2'b11均返回STS_ALIGN_ERR(0x20)，不发起AHB访问；"
        "2.addr[1:0]=2'b00返回STS_OK(0x00)，AHB正常执行；"
        "3.STS_ALIGN_ERR(0x20)位于前置优先级链中ALIGN_ERR(0x20)位置，不产生htrans_o=NONSEQ；"
        "4.STATUS sticky位置位反映对齐错误，LAST_ERR[7:0]=0x20；"
        "5.AHB接口固定32-bit字访问(hsize_o=3'b010)，addr必须4-byte对齐；coverage check点：覆盖STS_ALIGN_ERR(0x20)检测场景，收集addr[1:0]=2b01/10/11与对齐错误交叉覆盖率",

        None,
        ["TP_028"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_057",
        "test_frame_abort_during_rx",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，模块正在执行命令RX阶段；"
        "输入激励："
        "1.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xCAFEBABE)，16-bit模式RX需5拍(72bit)；"
        "2.在RX第3拍（rx_count_q=48时，opcode=0x20已锁存但帧未完成expected_rx_bits=72）提前拉高pcs_ni；"
        "3.观察SLC_DPCHK检测到frame_abort条件：pcs_ni在rx_count<expected_rx_bits时提前拉高且opcode已锁存；"
        "4.检查响应状态码应返回STS_FRAME_ERR(0x01)；"
        "5.验证不产生htrans_o=NONSEQ，AHB访问不发起；"
        "6.检查STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01；"
        "期望结果："
        "1.RX中途提前拉高pcs_ni且opcode已锁存触发frame_abort，返回STS_FRAME_ERR(0x01)；"
        "2.STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01记录帧错误；"
        "3.不产生htrans_o=NONSEQ，AHB访问不发起（前置错误在AHB访问前收敛）；"
        "4.frame_abort在发起CSR/AHB访问前收敛，符合优先级链最高优先级STS_FRAME_ERR(0x01)；"
        "5.前端FSM走IDLE→ISSUE→TA→TX路径返回STS_FRAME_ERR(0x01)，pdo_oe_o在TX态=1；coverage check点：覆盖RX阶段frame_abort场景，收集rx_count_q值与opcode_latched_q与STS_FRAME_ERR交叉覆盖率",

        None,
        ["TP_029"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_058",
        "test_frame_abort_burst_payload",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，正在执行AHB_WR_BURST命令payload接收阶段；"
        "输入激励："
        "1.发送AHB_WR_BURST命令(opcode=0x22, burst_len=4, addr=0x10000000, wdata=4×32bit)，expected_rx_bits=48+128=176；"
        "2.RX阶段：3拍header接收完成，进入payload阶段（8拍128bit数据），rxfifo_cnt[5:0]递增；"
        "3.在payload第4拍（rx_count_q=112，仍有64bit未接收）提前拉高pcs_ni触发frame_abort；"
        "4.检查响应状态码应返回STS_FRAME_ERR(0x01)；"
        "5.验证RXFIFO中已push的部分beat数据被drain清空：rxfifo_empty_o最终=1；"
        "6.检查STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01；"
        "期望结果："
        "1.Burst payload中途frame_abort返回STS_FRAME_ERR(0x01)，不发起AHB写入；"
        "2.RXFIFO中已push的部分beat数据被drain清空，rxfifo_empty_o最终=1；"
        "3.不产生htrans_o=NONSEQ，AHB访问不发起（前置错误在AHB访问前收敛）；"
        "4.STATUS[4]=FRAME_ERR(sticky)置位，LAST_ERR[7:0]=0x01记录帧错误；"
        "5.Burst命令frame_abort时RXFIFO drain确保FIFO不残留脏数据，模块恢复后可正常接受新命令；coverage check点：覆盖Burst payload阶段frame_abort场景，收集rxfifo_cnt值与RXFIFO drain与STS_FRAME_ERR交叉覆盖率",

        None,
        ["TP_029"],
        ["CHK_APLC_012"]
    ),
    (
        "TC_APLC_059",
        "test_ahb_hresp_error_single",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hresp_i可配置为1(错误响应)；"
        "输入激励："
        "1.配置AHB从端在AHB_WR32访问时返回hresp_i=1（错误响应）；"
        "2.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xDEADBEEF)；"
        "3.观察SLC_SAXIM在AXI_WAIT态采样到hresp_i=1后跳转AXI_ERR；"
        "4.检查响应状态码应返回STS_AHB_ERR(0x40)；"
        "5.验证AXI_ERR下一拍自动恢复AXI_IDLE：htrans_o=IDLE(2'b00)，hburst_o=SINGLE(3'b000)，haddr_o=0；"
        "6.验证RX/TX FIFO强制drain至empty：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "期望结果："
        "1.hresp_i=1时SLC_SAXIM跳转AXI_ERR，返回STS_AHB_ERR(0x40)；"
        "2.AXI_ERR下一拍自动恢复AXI_IDLE：htrans_o=2'b00(IDLE)，hburst_o=SINGLE，haddr_o=0；"
        "3.RX/TX FIFO强制drain至empty：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "4.STS_AHB_ERR(0x40)不在前置优先级链中，仅在前置检查通过后AHB执行期间发生；"
        "5.STATUS[3]=BUS_ERR(sticky)置位，LAST_ERR[7:0]=0x40记录AHB错误；coverage check点：覆盖AHB hresp_i=1错误场景，收集AXI_ERR恢复与STS_AHB_ERR(0x40)与FIFO drain交叉覆盖率",

        None,
        ["TP_030"],
        ["CHK_APLC_013"]
    ),
    (
        "TC_APLC_060",
        "test_ahb_timeout_256",
        "配置条件："
        "1.模块复位完成，test_mode_i=1，en_i=1；"
        "2.lane_mode_i=2'b11（16-bit模式），bpc=16；"
        "3.CTRL.EN=1，AHB从端hready_i可配置为0(不就绪)；"
        "4.BUS_TIMEOUT_CYCLES=256，9-bit计数器从0计至255；"
        "输入激励："
        "1.配置AHB从端在AHB_RD32访问时持续返回hready_i=0（不就绪）；"
        "2.发送AHB_RD32命令(opcode=0x21, addr=0x20000000)；"
        "3.观察SLC_SAXIM进入AXI_WAIT态后hready_i=0，9-bit超时计数器从0开始递增；"
        "4.持续保持hready_i=0达256个clk_i周期，计数器计至255触发超时；"
        "5.超时后检查响应状态码应返回STS_AHB_ERR(0x40)；"
        "6.验证AXI_ERR下一拍自动恢复AXI_IDLE：htrans_o=IDLE，hburst_o=SINGLE，haddr_o=0；"
        "7.恢复hready_i=1后发送新AHB_RD32命令验证模块恢复正常；"
        "期望结果："
        "1.hready_i=0持续256周期触发超时(9-bit计数器0→255)，返回STS_AHB_ERR(0x40)；"
        "2.AXI_ERR下一拍自动恢复AXI_IDLE：htrans_o=2'b00(IDLE)，hburst_o=SINGLE，haddr_o=0；"
        "3.RX/TX FIFO强制drain至empty：rxfifo_empty_o=1，txfifo_empty_o=1；"
        "4.STATUS[3]=BUS_ERR(sticky)置位，LAST_ERR[7:0]=0x40记录AHB超时错误；"
        "5.恢复hready_i=1后新AHB_RD32命令返回STS_OK(0x00)，模块从超时错误中恢复；coverage check点：覆盖AHB超时256周期场景，收集BUS_TIMEOUT_CYCLES计数器与STS_AHB_ERR(0x40)与AXI_ERR恢复覆盖率",

        None,
        ["TP_031"],
        ["CHK_APLC_013"]
    ),
    (
        "TC_APLC_061",
        "test_ahb_hresp_error_burst",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hresp_i可配置为1(ERROR)；3.Burst命令进行中(axi_state=AXI_BURST)；输入激励：1.发送AHB_RD_BURST×4命令(opcode=0x23, burst_len=4, addr=0x10000000)；2.观察AXI_REQ首拍htrans_o=NONSEQ(2'b10)+hburst_o=INCR4(3'b011)；3.在AXI_BURST第2拍SEQ时force hresp_i=1(ERROR响应)；4.观察SLC_SAXIM检测到hresp_i=1后立即中止burst，跳转AXI_ERR；5.检查返回status_code=STS_AHB_ERR(0x40)；6.验证已完成beat数据仍正确写入TXFIFO，中止beat不写入；期望结果：1.hresp_i=1在burst中途中止：axi_state跳转AXI_ERR，htrans_o=IDLE；2.已完成beat(首拍NONSEQ)的数据仍正确推入TXFIFO；3.中止beat不写入TXFIFO，TXFIFO中仅有已完成beat的数据；4.返回STS_AHB_ERR(0x40)，STATUS[3]=BUS_ERR置位，LAST_ERR=0x40(sticky)；5.AXI_ERR下一拍自动恢复AXI_IDLE：htrans_o=2'b00，hburst_o=SINGLE，haddr_o=0；coverage check点：对burst中途hresp_i=1中止场景收集功能覆盖率",
        None,
        ['TP_034'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_062",
        "test_bad_burst_len",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，burst_len字段可配置；输入激励：1.发送AHB_WR_BURST命令(opcode=0x22)，帧中burst_len字段设为2（非法，不在{1,4,8,16}中）；2.检查返回status_code是否为STS_BAD_BURST(0x80)；3.发送AHB_RD_BURST命令(opcode=0x23)，burst_len=3验证同样被拒绝；4.依次测试burst_len=5,6,7,9,10,11,12,13,14,15等所有非法值；5.验证非法burst_len不发起AHB访问：htrans_o保持IDLE；6.测试burst_len=0场景；期望结果：1.burst_len=2返回STS_BAD_BURST(0x80)，不发起AHB访问（htrans_o=IDLE）；2.burst_len=3/5/6/7/9~15/0均返回STS_BAD_BURST(0x80)；3.合法burst_len(1/4/8/16)正常执行返回STS_OK(0x00)；4.所有BAD_BURST场景不产生csr_wr_en_o/htrans_o脉冲，前置检查即拒绝；5.LAST_ERR更新为0x80(sticky)；coverage check点：对burst_len全空间(0~16)收集功能覆盖率，覆盖合法/非法边界",
        None,
        ['TP_032'],
        ['CHK_APLC_014']
    ),
    (
        "TC_APLC_063",
        "test_burst_bound_1kb",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，地址空间可跨越1KB边界；输入激励：1.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4, addr=0x100003F0)；2.addr=0x100003F0+4×4=0x10000400跨越1KB(0x400)边界；3.检查返回status_code是否为STS_BURST_BOUND(0x81)；4.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8, addr=0x10000800)；5.addr=0x10000800+4×8=0x10000820不跨1KB边界(0x10000800~0x10000BFF在0x800~0xBFF内)，验证正常；6.测试多个跨边界地址：addr=0x100003FC(1 beat跨), addr=0x10000FF0(INCR16跨)；期望结果：1.addr=0x100003F0+4×4跨1KB边界返回STS_BURST_BOUND(0x81)，不发起AHB访问；2.addr=0x10000800+4×8不跨1KB边界返回STS_OK(0x00)；3.BURST_BOUND检查公式：addr[11:0]+4×burst_len<=4096(即不跨4KB页内1KB子边界)；4.BURST_BOUND在前置检查阶段拒绝，不产生htrans_o脉冲；5.LAST_ERR=0x81(sticky)；coverage check点：对burst地址1KB边界场景收集功能覆盖率",
        None,
        ['TP_033'],
        ['CHK_APLC_014']
    ),
    (
        "TC_APLC_064",
        "test_ahb_err_recovery",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hresp_i可配置；输入激励：1.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)，注入hresp_i=1触发STS_AHB_ERR(0x40)；2.验证AXI_ERR→AXI_IDLE自动恢复，htrans_o=IDLE，FIFO drain；3.不执行复位，直接发送WR_CSR命令(opcode=0x10, reg_addr=0x04, wdata=0x01)；4.验证CSR命令在AHB错误后正常工作，返回STS_OK(0x00)；5.发送AHB_WR32命令(opcode=0x20, addr=0x20000000, wdata=0x12345678)验证AHB恢复；6.读取STATUS(0x08)和LAST_ERR(0x0C)确认AHB错误恢复后状态正确；期望结果：1.AHB错误后AXI_ERR→AXI_IDLE自动恢复，后续命令可正常执行；2.WR_CSR在AHB错误后正常返回STS_OK(0x00)，不受前次AHB错误影响；3.AHB_WR32在恢复后正常返回STS_OK(0x00)，htrans_o=NONSEQ+haddr_o=0x20000000；4.STATUS[3]=BUS_ERR(sticky)仍置位，LAST_ERR=0x40(sticky)保持；5.模块不需要复位即可从AHB错误中恢复，仅AXI_ERR态自动回AXI_IDLE；coverage check点：对AHB错误恢复场景收集功能覆盖率",
        None,
        ['TP_030'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_065",
        "test_priority_chain_full",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，配置多条件重叠场景；输入激励：1.构造多条件重叠命令：test_mode_i=0(触发NOT_IN_TEST)+非法opcode(触发BAD_OPCODE)+非对齐地址(触发ALIGN_ERR)；2.检查返回status_code，验证优先级STS_FRAME_ERR(0x01)>STS_BAD_OPCODE(0x02)>STS_NOT_IN_TEST(0x04)>STS_DISABLED(0x08)>STS_BAD_REG(0x10)>STS_ALIGN_ERR(0x20)>STS_BAD_BURST(0x80)>STS_BURST_BOUND(0x81)；3.构造帧中止+非法opcode重叠：提前拉高pcs_ni(frame_abort)+非法opcode，验证返回STS_FRAME_ERR(0x01)；4.构造非法opcode+越界CSR+非对齐重叠：opcode=0xFF+reg_addr=0x40+addr非对齐，验证返回STS_BAD_OPCODE(0x02)；5.构造NOT_IN_TEST+BAD_REG重叠：test_mode_i=0+reg_addr=0x40，验证返回STS_NOT_IN_TEST(0x04)；6.逐级验证8级优先级链中每两个相邻级别的相对优先级；期望结果：1.多条件重叠时仅返回最高优先级错误码，低优先级错误不覆盖；2.FRAME_ERR(0x01)始终最高优先级，任何帧中止场景都返回0x01；3.BAD_OPCODE(0x02)第二优先级，opcode非法时忽略后续地址/寄存器检查；4.完整优先级链：0x01>0x02>0x04>0x08>0x10>0x20>0x80>0x81；5.STS_AHB_ERR(0x40)不在前置优先级链中，与前置错误互斥；coverage check点：对错误优先级链所有相邻级别组合收集功能覆盖率",
        None,
        ['TP_027'],
        ['CHK_APLC_012']
    ),
    (
        "TC_APLC_066",
        "test_ahb_err_vs_precheck_mutex",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hresp_i可配置；输入激励：1.构造场景1：test_mode_i=0(前置错误NOT_IN_TEST)+hresp_i=1(AHB错误)同时满足；2.test_mode_i=0时发送AHB_RD32命令，同时force hresp_i=1；3.验证返回STS_NOT_IN_TEST(0x04)，不发起AHB访问，hresp_i=1被忽略；4.构造场景2：合法opcode+越界CSR(BAD_REG)+同时hresp_i=1；5.发送RD_CSR(reg_addr=0x40)触发BAD_REG，同时hresp_i=1；6.验证返回STS_BAD_REG(0x10)，不发起AHB访问，hresp_i=1被忽略；期望结果：1.前置错误与AHB错误互斥：前置错误优先，不发起AHB访问，hresp_i=1无影响；2.test_mode_i=0+AHB错误：返回STS_NOT_IN_TEST(0x04)，htrans_o=IDLE，hresp_i被忽略；3.BAD_REG+AHB错误：返回STS_BAD_REG(0x10)，无csr_rd_en_o脉冲，hresp_i被忽略；4.STS_AHB_ERR(0x40)仅在前置检查全部通过后AHB执行期间才可能发生；5.证明前置优先级链与执行期错误严格分离；coverage check点：对前置错误×AHB错误互斥场景收集功能覆盖率",
        None,
        ['TP_027', 'TP_030'],
        ['CHK_APLC_012', 'CHK_APLC_013']
    ),
    (
        "TC_APLC_067",
        "test_burst_mid_error_txfifo",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hresp_i可配置；3.TXFIFO深度32×33bit；输入激励：1.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8, addr=0x10000000)；2.正常执行前4个beat，hrdata_i正常返回数据推入TXFIFO；3.在第5个beat上force hresp_i=1(ERROR)，SLC_SAXIM立即中止burst跳转AXI_ERR；4.观察TXFIFO中已有4个beat数据加上status字节准备发送；5.验证TXFIFO强制drain：已有数据被清空，txfifo_empty_o=1；6.验证模块自动恢复AXI_IDLE后可正常执行新命令；期望结果：1.burst中途hresp_i=1：已完成beat数据写入TXFIFO，但AXI_ERR时TXFIFO强制drain清空；2.TXFIFO drain后txfifo_empty_o=1，txfifo_cnt_q=0；3.不输出部分响应帧（TXFIFO清空导致pdo_oe_o=0，无TX输出）；4.返回STS_AHB_ERR(0x40)，LAST_ERR=0x40(sticky)；5.AXI_ERR→AXI_IDLE自动恢复，后续命令正常工作；coverage check点：对burst中途AHB错误TXFIFO drain场景收集功能覆盖率",
        None,
        ['TP_034'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_068",
        "test_timeout_per_beat",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，BUS_TIMEOUT_CYCLES=256，hready_i可配置；输入激励：1.发送AHB_RD_BURST×4命令(opcode=0x23, burst_len=4, addr=0x10000000)；2.在第1个beat地址相正常完成(htrans=NONSEQ, hready_i=1)；3.在第2个beat数据相force hready_i=0，持续255个周期（差1周期未超时）；4.恢复hready_i=1，验证beat正常完成；5.在第3个beat再次force hready_i=0，持续256个周期触发超时；6.验证超时后返回STS_AHB_ERR(0x40)，burst中止；期望结果：1.hready_i=0持续255周期不触发超时(计数器0→254)，恢复后beat正常完成；2.hready_i=0持续256周期(计数器0→255)触发超时，返回STS_AHB_ERR(0x40)；3.超时计数器按beat独立（非全局），每个beat的hready_i=0独立计算256周期上限；4.超时触发后AXI_ERR→AXI_IDLE，TXFIFO drain；5.第1个beat数据正常保留在TXFIFO直到drain；coverage check点：对per-beat超时计数和255/256边界收集功能覆盖率",
        None,
        ['TP_031'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_069",
        "test_error_random_inject",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，支持错误注入；输入激励：1.随机选择错误类型并注入：非法opcode(0x00~0x0F或0x24~0xFF)→STS_BAD_OPCODE(0x02)；2.越界CSR地址(reg_addr>=0x40)→STS_BAD_REG(0x10)；3.非对齐地址(addr[1:0]!=2'b00)→STS_ALIGN_ERR(0x20)；4.非法burst_len(2,3,5,6,7,9~15)→STS_BAD_BURST(0x80)；5.跨1KB边界地址→STS_BURST_BOUND(0x81)；6.force hresp_i=1→STS_AHB_ERR(0x40)；force hready_i=0持续256+周期→超时→STS_AHB_ERR(0x40)；7.帧中止(提前拉高pcs_ni)→STS_FRAME_ERR(0x01)；test_mode_i=0→STS_NOT_IN_TEST(0x04)；en_i=0→STS_DISABLED(0x08)；8.每种错误类型重复N≥20次，每次随机lane_mode和参数；期望结果：1.每种错误注入返回对应错误码，优先级链正确：0x01>0x02>0x04>0x08>0x10>0x20>0x80>0x81；2.前置错误不发起CSR/AHB访问：无csr_wr_en_o/csr_rd_en_o/htrans_o脉冲；3.AHB错误(0x40)仅在前置检查通过后AHB执行期发生，与前置错误互斥；4.LAST_ERR每次更新为最新错误码(sticky)，成功命令不清除；5.所有错误后模块可恢复：前置错误自动恢复，AHB错误AXI_ERR→AXI_IDLE自动恢复；coverage check点：覆盖所有9种状态码×lane_mode×错误类型交叉覆盖率",
        None,
        ['TP_027', 'TP_028', 'TP_029', 'TP_030', 'TP_031', 'TP_032', 'TP_033', 'TP_034'],
        ['CHK_APLC_012', 'CHK_APLC_013', 'CHK_APLC_014']
    ),
    (
        "TC_APLC_070",
        "test_error_priority_random",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1；输入激励：1.随机选择2-3个前置错误条件同时满足的场景；2.例：非法opcode+非对齐地址→验证仅返回最高优先级STS_BAD_OPCODE(0x02)；3.例：test_mode_i=0+越界CSR+非法opcode→验证返回优先级最高的错误码；4.随机构造50组多条件重叠场景，每组验证返回的错误码为最高优先级；5.对所有8级前置优先级链的相邻级别构造验证对；6.验证STS_AHB_ERR(0x40)不与任何前置错误同时返回；期望结果：1.多条件重叠时仅返回优先级链中最高级别错误码；2.8级前置优先级链：FRAME_ERR(0x01)>BAD_OPCODE(0x02)>NOT_IN_TEST(0x04)>DISABLED(0x08)>BAD_REG(0x10)>ALIGN_ERR(0x20)>BAD_BURST(0x80)>BURST_BOUND(0x81)；3.STS_AHB_ERR(0x40)与前置错误互斥，仅在前置检查全通过后AHB执行期产生；4.每次错误后LAST_ERR更新为当前最高优先级错误码(sticky)；5.随机50组场景全部通过优先级链验证；coverage check点：对前置优先级链所有级别组合×随机参数收集功能覆盖率",
        None,
        ['TP_027'],
        ['CHK_APLC_012']
    ),
    (
        "TC_APLC_071",
        "test_idle_toggle_control",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，模块空闲(pcs_ni=1)；输入激励：1.确认模块空闲：pcs_ni=1，front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；2.观察空闲期间：htrans_o=IDLE(2'b00)，hburst_o=SINGLE(3'b000)，haddr_o=0；3.观察空闲期间：pdo_oe_o=0，csr_rd_en_o=0，csr_wr_en_o=0；4.执行一次WR_CSR命令后回到空闲，验证空闲态门控恢复；5.对比空闲态vs活跃态的toggle rate（如有功耗分析工具），验证空闲门控生效；期望结果：1.空闲态所有输出静态：htrans_o=IDLE，hburst_o=SINGLE，haddr_o=0，pdo_oe_o=0；2.空闲态无CSR/AHB访问脉冲：csr_rd_en_o=0，csr_wr_en_o=0，htrans_o保持IDLE；3.空闲态FIFO维持empty：rxfifo_empty_o=1，txfifo_empty_o=1；4.命令执行后回到空闲态，输出信号恢复静态；5.空闲门控：SLC_SAXIM在AXI_IDLE态不驱动AHB总线信号翻转；coverage check点：对空闲态vs活跃态toggle控制收集功能覆盖率",
        None,
        ['TP_035'],
        ['CHK_APLC_015']
    ),
    (
        "TC_APLC_072",
        "test_rxfifo_backpressure_gating",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，RXFIFO深度32×32bit；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000)；2.持续推入payload使rxfifo_cnt增至32，rxfifo_full_o=1；3.观察rxfifo_full_o=1时SLC_CAXIS暂停接收(rx_shift_en=0, rxfifo_wr_en=0)；4.后端BURST_LOOP通过rxfifo_rd_en drain数据，rxfifo_full_o清零后恢复接收；5.观察rxfifo_full_o=1→0期间门控信号变化，验证FIFO门控不影响AHB burst进行；期望结果：1.rxfifo_full_o=1时接收暂停但不影响后端AHB burst执行，hwdata_o从RXFIFO正常读出；2.rxfifo_full_o=0后接收立即恢复，ATE可继续发送数据；3.背压期间hburst_o保持稳定(INCR16)，不翻转；4.RXFIFO full→drain→full循环可正确处理，不丢失数据；5.所有16个32bit payload word正确写入AHB，status=STS_OK(0x00)；coverage check点：对rxfifo_cnt level(0~32)和rxfifo_full_o门控时序收集功能覆盖率",
        None,
        ['TP_036'],
        ['CHK_APLC_015']
    ),
    (
        "TC_APLC_073",
        "test_hburst_stable_burst",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1；输入激励：1.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16, addr=0x10000000)；2.在整个burst期间持续监测hburst_o值，验证保持INCR16(3'b111)不变；3.在burst中途注入rxfifo_full_o=1(通过延长hrdata_i返回)，验证hburst_o仍不翻转；4.发送AHB_WR_BURST×8命令(opcode=0x22, burst_len=8)，验证hburst_o=INCR8(3'b101)全程稳定；5.发送AHB_WR32命令(opcode=0x20)验证hburst_o=SINGLE(3'b000)；期望结果：1.AHB_RD_BURST×16期间hburst_o=INCR16(3'b111)全程稳定，不因背压或FIFO状态翻转；2.AHB_WR_BURST×8期间hburst_o=INCR8(3'b101)全程稳定；3.AHB Single期间hburst_o=SINGLE(3'b000)；4.hburst_o仅在AXI_REQ首拍更新，后续AXI_BURST/AXI_WAIT期间保持不变；5.背压(hready_i=0)不影响hburst_o稳定性；coverage check点：对hburst_o在burst全程稳定性收集功能覆盖率",
        None,
        ['TP_035', 'TP_036'],
        ['CHK_APLC_015']
    ),
    (
        "TC_APLC_074",
        "test_lowpower_random",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1；输入激励：1.随机选择命令序列(Single/Burst)交替执行，期间插入空闲等待；2.在空闲期间验证：htrans_o=IDLE，pdo_oe_o=0，所有输出静态；3.在Burst执行期间注入rxfifo_full_o=1(延长hrdata_i/hready_i返回)，验证背压门控；4.验证hburst_o在burst期间保持稳定，不因背压翻转；5.重复N≥50次，每次随机命令类型、burst_len、空闲间隔、背压时机；期望结果：1.空闲态输出静态：htrans_o=IDLE，pdo_oe_o=0，无CSR/AHB脉冲；2.Burst背压期间hburst_o保持稳定，接收暂停但不影响AHB执行；3.rxfifo_full_o=1→0循环正确处理，不丢失数据；4.所有命令返回正确status_code(STS_OK或对应错误码)；5.空闲门控和FIFO门控交替生效，互不干扰；coverage check点：对空闲门控×FIFO门控×burst_len×lane_mode交叉覆盖率收集",
        None,
        ['TP_035', 'TP_036'],
        ['CHK_APLC_015']
    ),
    (
        "TC_APLC_075",
        "test_wr_burst_incr16_throughput",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；3.目标验证INCR16写burst吞吐量；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000, wdata随机16个32bit word)；2.测量从htrans_o首拍NONSEQ到末拍SEQ+hwdata_o完成的总周期数；3.计算吞吐量：16×4bytes/总周期数×clk_freq；4.重复10次取平均吞吐量；5.与理论最大吞吐量118MB/s@100MHz(INCR16写)对比；期望结果：1.INCR16写burst 16×4=64bytes在约18拍完成(16地址+16数据+2流水开销)；2.实测吞吐量接近118MB/s@100MHz(INCR16写理论值)；3.hwdata_o每拍输出4bytes，haddr_o每拍+4，beat间无间隔；4.hburst_o=INCR16(3'b111)全程稳定；5.吞吐量相比Single模式(4bytes/2拍≈200MB/s有效带宽但高开销)提升约7×；coverage check点：对INCR16写burst吞吐量测量收集功能覆盖率",
        None,
        ['TP_037'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_076",
        "test_rd_burst_incr16_throughput",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；3.目标验证INCR16读burst吞吐量；输入激励：1.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16, addr=0x10000000)；2.测量从htrans_o首拍NONSEQ到末拍hrdata_i采样的总周期数；3.计算吞吐量：16×4bytes/总周期数×clk_freq；4.重复10次取平均吞吐量；5.与理论最大吞吐量116MB/s@100MHz(INCR16读)对比；期望结果：1.INCR16读burst 16×4=64bytes在约17拍完成(16地址+1流水开销)；2.实测吞吐量接近116MB/s@100MHz(INCR16读理论值)；3.hrdata_i每拍返回4bytes，haddr_o每拍+4，beat间无间隔；4.hburst_o=INCR16(3'b111)全程稳定；5.写burst略高于读吞吐(118 vs 116 MB/s)因写流水额外1拍数据相；coverage check点：对INCR16读burst吞吐量测量收集功能覆盖率",
        None,
        ['TP_038'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_077",
        "test_throughput_1bit_burst16",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b00（1-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.配置lane_mode_i=2'b00（1-bit模式，bpc=1）；2.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000)；3.测量1-bit模式下Burst命令的总执行时间(RX 560拍+处理+1拍TX)；4.计算1-bit模式有效吞吐量：64bytes/(560+处理周期)×100MHz；5.与16-bit模式对比验证1-bit模式开销主要在串行传输阶段；期望结果：1.1-bit模式RX接收Burst header 48bit需48拍+payload 16×32=512bit需512拍=560拍；2.1-bit模式有效吞吐量远低于16-bit模式(受串行传输瓶颈限制)；3.AHB总线侧(后端)burst执行速度相同(16拍地址+数据)，瓶颈在前端串行接收；4.status=STS_OK(0x00)，所有数据正确传输；5.1-bit vs 16-bit吞吐差异主要来源：560拍 vs 35拍RX接收开销；coverage check点：对1-bit lane模式burst吞吐量收集功能覆盖率",
        None,
        ['TP_037'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_078",
        "test_throughput_4bit_burst16",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b01（4-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.配置lane_mode_i=2'b01（4-bit模式，bpc=4）；2.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000)；3.测量4-bit模式下Burst命令总执行时间(RX 140拍+处理+2拍TX)；4.计算4-bit模式有效吞吐量：64bytes/(140+处理周期)×100MHz；5.与16-bit模式对比验证4-bit模式吞吐约为16-bit的1/4(串行接收4倍慢)；期望结果：1.4-bit模式RX接收：header 48bit/4bpc=12拍+payload 512bit/4bpc=128拍=140拍；2.4-bit模式有效吞吐量约为16-bit模式的1/4(前端串行瓶颈)；3.AHB后端burst执行不受lane_mode影响，16拍完成16×4bytes；4.status=STS_OK(0x00)，数据正确传输；5.4-bit vs 16-bit：140拍 vs 35拍RX开销(4:1比例)；coverage check点：对4-bit lane模式burst吞吐量收集功能覆盖率",
        None,
        ['TP_037'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_079",
        "test_throughput_8bit_burst16",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b10（8-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.配置lane_mode_i=2'b10（8-bit模式，bpc=8）；2.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000)；3.测量8-bit模式下Burst命令总执行时间(RX 70拍+处理+1拍TX)；4.计算8-bit模式有效吞吐量：64bytes/(70+处理周期)×100MHz；5.与16-bit模式对比验证8-bit模式吞吐约为16-bit的1/2(串行接收2倍慢)；期望结果：1.8-bit模式RX接收：header 48bit/8bpc=6拍+payload 512bit/8bpc=64拍=70拍；2.8-bit模式有效吞吐量约为16-bit模式的1/2(前端串行瓶颈)；3.AHB后端不受lane_mode影响，吞吐相同；4.status=STS_OK(0x00)，数据正确；5.8-bit vs 16-bit：70拍 vs 35拍RX开销(2:1比例)；coverage check点：对8-bit lane模式burst吞吐量收集功能覆盖率",
        None,
        ['TP_037'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_080",
        "test_throughput_random",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.随机选择lane_mode(2'b00/01/10/11)和burst_len(1/4/8/16)；2.随机选择Burst命令类型(opcode=0x22写/0x23读)；3.对每种组合测量burst执行周期数和有效吞吐量；4.重复N≥50次随机组合，收集吞吐量分布；5.验证16-bit模式INCR16写burst达到≈118MB/s，INCR16读burst达到≈116MB/s；期望结果：1.16-bit INCR16写：≈118MB/s@100MHz；16-bit INCR16读：≈116MB/s@100MHz；2.Burst模式相比Single模式吞吐提升约7×(16×4bytes vs 1×4bytes per transaction)；3.lane_mode降低前端串行吞吐但不影响AHB后端吞吐；4.burst_len=1退化为Single(hburst=SINGLE, 3'b000)，吞吐最低；5.所有随机组合返回STS_OK(0x00)，数据正确；coverage check点：覆盖lane_mode×burst_len×读写×吞吐量交叉覆盖率",
        None,
        ['TP_037', 'TP_038'],
        ['CHK_APLC_016']
    ),
    (
        "TC_APLC_081",
        "test_opcode_success_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX统计计数器初始为0；输入激励：1.发送WR_CSR命令(opcode=0x10, reg_addr=0x04, wdata=0x01)，执行成功；2.通过DFX寄存器读取opcode_success_cnt[WR_CSR]计数器验证=1；3.依次执行RD_CSR/AHB_WR32/AHB_RD32/AHB_WR_BURST×4/AHB_RD_BURST×4各1次；4.每次执行后读取对应6路成功计数器验证递增；5.对同一opcode重复执行3次，验证计数器正确递增至3；期望结果：1.6路opcode成功计数器(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32/AHB_WR_BURST/AHB_RD_BURST)分别独立计数；2.每次成功命令后对应计数器+1，其他计数器不变；3.重复执行3次WR_CSR后cnt[WR_CSR]=3，cnt[RD_CSR]仍为1；4.计数器为saturation计数(达到最大值后不再递增，不溢出回绕)；5.所有成功命令返回STS_OK(0x00)；coverage check点：对6路opcode成功计数器收集功能覆盖率",
        None,
        ['TP_039'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_082",
        "test_error_code_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX错误计数器初始为0；输入激励：1.发送非法opcode(0xFF)触发STS_BAD_OPCODE(0x02)，读取error_code_cnt[BAD_OPCODE]验证=1；2.设置test_mode_i=0触发STS_NOT_IN_TEST(0x04)，读取error_code_cnt[NOT_IN_TEST]验证=1；3.设置en_i=0触发STS_DISABLED(0x08)，读取error_code_cnt[DISABLED]验证=1；4.发送越界CSR地址(0x40)触发STS_BAD_REG(0x10)，读取error_code_cnt[BAD_REG]验证=1；5.发送非对齐地址(addr[1:0]=01)触发STS_ALIGN_ERR(0x20)，读取error_code_cnt[ALIGN_ERR]验证=1；6.对STS_AHB_ERR(0x40)/STS_BAD_BURST(0x80)/STS_BURST_BOUND(0x81)/STS_FRAME_ERR(0x01)分别注入错误验证计数器；期望结果：1.8路错误码计数器(FRAME_ERR/BAD_OPCODE/NOT_IN_TEST/DISABLED/BAD_REG/ALIGN_ERR/AHB_ERR/BAD_BURST)分别独立计数；2.每次错误后对应计数器+1，其他计数器不变；3.BURST_BOUND(0x81)与BAD_BURST(0x80)共用BAD_BURST计数器或独立计数(按实现)；4.计数器saturation计数，不溢出回绕；5.错误计数器与成功计数器独立，不互相影响；coverage check点：对8路错误码计数器收集功能覆盖率",
        None,
        ['TP_039'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_083",
        "test_csr_ahb_access_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX CSR/AHB访问计数器初始为0；输入激励：1.发送WR_CSR命令(opcode=0x10)和RD_CSR命令(opcode=0x11)各1次，读取csr_access_cnt验证=2；2.发送AHB_WR32(opcode=0x20)和AHB_RD32(opcode=0x21)各1次，读取ahb_access_cnt验证=2；3.发送AHB_WR_BURST×4(opcode=0x22)1次，读取ahb_burst_cnt验证=1；4.混合执行CSR和AHB命令各5次，验证总计数器csr_total=5+ahb_total=6(5single+1burst)；5.验证DFX计数器通过CSR地址空间读取(不经过AHB map)；期望结果：1.CSR访问计数器累计所有WR_CSR+RD_CSR执行次数(WR+RD各1次→cnt=2)；2.AHB访问计数器累计所有AHB_WR32+AHB_RD32执行次数(各1次→cnt=2)；3.AHB burst计数器累计所有AHB_WR_BURST+AHB_RD_BURST执行次数(1次→cnt=1)；4.DFX计数器通过CSR地址空间0x14~0x3F区域读取，不进AHB map；5.所有计数器复位后归零；coverage check点：对CSR/AHB访问计数器收集功能覆盖率",
        None,
        ['TP_039'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_084",
        "test_fsm_observability",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX FSM可观测寄存器可读；输入激励：1.模块空闲态读取DFX FSM寄存器：验证front_state=IDLE(0), axi_state=AXI_IDLE(0), back_state=S_IDLE(0)；2.发送WR_CSR命令(opcode=0x10)期间读取DFX FSM寄存器：验证front_state经历IDLE→ISSUE→WAIT_RESP→TA→TX跳转；3.发送AHB_RD32命令(opcode=0x21)期间读取DFX FSM寄存器：验证axi_state经历AXI_IDLE→AXI_REQ→AXI_WAIT→AXI_DONE跳转；4.发送AHB_WR_BURST×4命令期间读取DFX FSM寄存器：验证back_state经历S_IDLE→S_LOAD→S_EXEC→S_WAIT_AHB→S_BURST_LOOP→S_BUILD→S_DONE跳转；5.在错误场景(AHB_ERR)读取DFX FSM寄存器验证axi_state=AXI_ERR(5)；期望结果：1.空闲态DFX FSM寄存器：front=0/axi=0/back=0；2.WR_CSR期间FSM跳转：front: IDLE(0)→ISSUE(1)→WAIT_RESP(2)→TA(3)→TX(4)→IDLE(0)；3.AHB_RD32期间FSM跳转：axi: AXI_IDLE(0)→AXI_REQ(1)→AXI_WAIT(3)→AXI_DONE(4)→AXI_IDLE(0)；4.AHB_WR_BURST期间back FSM经历7态完整跳转；5.AHB_ERR场景axi_state=AXI_ERR(5)可观测；coverage check点：对3组FSM所有状态和跳转收集功能覆盖率",
        None,
        ['TP_040'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_085",
        "test_burst_type_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX burst类型计数器初始为0；输入激励：1.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4)，读取burst_type_cnt[WR_INCR4]验证=1；2.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8)，读取burst_type_cnt[RD_INCR8]验证=1；3.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16)，读取burst_type_cnt[WR_INCR16]验证=1；4.发送AHB_RD_BURST×4命令(opcode=0x23, burst_len=4)，读取burst_type_cnt[RD_INCR4]验证=1；5.对6种burst类型(WR_INCR4/WR_INCR8/WR_INCR16/RD_INCR4/RD_INCR8/RD_INCR16)各执行1次验证全部计数器=1；期望结果：1.6路burst类型计数器(WR_INCR4/WR_INCR8/WR_INCR16/RD_INCR4/RD_INCR8/RD_INCR16)分别独立计数；2.每种burst类型执行后对应计数器+1；3.burst_len=1退化为SINGLE不计入burst类型计数器(或单独计数)；4.计数器saturation计数，不溢出回绕；5.所有burst命令返回STS_OK(0x00)；coverage check点：对6路burst类型计数器收集功能覆盖率",
        None,
        ['TP_041'],
        ['CHK_APLC_018']
    ),
    (
        "TC_APLC_086",
        "test_burst_beat_and_fifo_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，DFX burst beat计数器和FIFO计数器初始为0；输入激励：1.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4)，读取burst_beat_cnt验证=4；2.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8)，读取burst_beat_cnt累计验证=12(4+8)；3.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16)，读取burst_beat_cnt累计验证=28(12+16)；4.读取rxfifo_total_wr_cnt和txfifo_total_rd_cnt验证FIFO流量统计正确；5.验证beat计数器和FIFO计数器在复位后归零；期望结果：1.burst_beat_cnt累计所有burst传输的beat数：4+8+16=28；2.rxfifo_total_wr_cnt累计RXFIFO写入次数(对应AHB_WR_BURST payload word数)：4+16=20；3.txfifo_total_rd_cnt累计TXFIFO读出次数(对应AHB_RD_BURST rdata word数+status)：8+若干status beat；4.所有计数器复位后归零；5.计数器为saturation计数，不溢出回绕；coverage check点：对burst beat计数和FIFO流量计数收集功能覆盖率",
        None,
        ['TP_041'],
        ['CHK_APLC_018']
    ),
    (
        "TC_APLC_087",
        "test_fifo_backpressure_counters",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，RXFIFO 32×32bit，TXFIFO 32×33bit；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16)，注入rxfifo_full_o=1场景；2.读取rxfifo_backpressure_cnt计数器验证FIFO full事件被统计；3.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16)，注入txfifo_empty_o=1场景；4.读取txfifo_stall_cnt计数器验证FIFO empty事件被统计；5.验证背压计数器与实际FIFO水位一致：rxfifo_backpressure_cnt>0当且仅当rxfifo_full_o曾经为1；期望结果：1.rxfifo_backpressure_cnt在rxfifo_full_o=1时递增，统计FIFO full持续周期数或事件次数；2.txfifo_stall_cnt在txfifo_empty_o=1且需要读出时递增，统计FIFO empty stall事件；3.计数器统计值与实际观测到的背压/stall事件一致；4.复位后计数器归零；5.计数器saturation计数，不溢出；coverage check点：对FIFO背压/stall计数器收集功能覆盖率",
        None,
        ['TP_042'],
        ['CHK_APLC_018']
    ),
    (
        "TC_APLC_088",
        "test_dfx_random",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1；输入激励：1.随机选择命令序列(Single/Burst, 成功/失败混合)执行N≥100次；2.每次命令后读取DFX计数器(opcode_success_cnt/error_code_cnt/csr_ahb_cnt等)验证递增；3.随机读取DFX FSM可观测寄存器验证3组FSM状态跳转可观测；4.随机注入burst场景和FIFO背压，验证burst_beat_cnt和fifo_backpressure_cnt；5.最终汇总所有DFX计数器验证总和与实际执行命令数一致；期望结果：1.所有DFX计数器正确统计执行事件，无遗漏或重复计数；2.opcode_success_cnt总和 + error_code_cnt总和 = 总命令数；3.FSM可观测寄存器实时反映3组FSM状态；4.burst/FIFO计数器与实际burst/背压事件一致；5.所有DFX寄存器通过CSR地址空间读取(0x14~0x3F)，不进AHB map；coverage check点：覆盖DFX所有计数器×FSM可观测×FIFO统计交叉覆盖率",
        None,
        ['TP_039', 'TP_040', 'TP_041', 'TP_042'],
        ['CHK_APLC_017', 'CHK_APLC_018']
    ),
    (
        "TC_APLC_089",
        "test_csr_not_in_ahb_map",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，CSR地址空间0x00~0x3F，AHB地址空间独立；输入激励：1.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))，验证CSR访问通过csr_rd_en_o/csr_rdata_i通道；2.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)，验证AHB访问通过htrans_o/haddr_o/hrdata_i通道；3.确认CSR访问不产生htrans_o脉冲：在RD_CSR期间监测htrans_o=IDLE(2'b00)；4.确认AHB访问不产生csr_rd_en_o/csr_wr_en_o脉冲：在AHB_RD32期间监测CSR信号=0；5.验证CSR地址0x00~0x3F不会出现在haddr_o输出上；期望结果：1.CSR访问(opcode=0x10/0x11)仅通过CSR通道(csr_wr_en_o/csr_rd_en_o/csr_addr_o/csr_wdata_o/csr_rdata_i)；2.AHB访问(opcode=0x20/0x21/0x22/0x23)仅通过AHB通道(htrans_o/haddr_o/hwdata_o/hrdata_i)；3.CSR访问期间htrans_o=IDLE(2'b00)，haddr_o不更新；4.AHB访问期间csr_wr_en_o=0，csr_rd_en_o=0；5.CSR地址空间(0x00~0x3F)与AHB地址空间完全隔离，无地址重叠；coverage check点：对CSR通道vs AHB通道地址空间隔离收集功能覆盖率",
        None,
        ['TP_043'],
        ['CHK_APLC_019']
    ),
    (
        "TC_APLC_090",
        "test_ahb_access_address_range",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB地址空间可配置；输入激励：1.发送AHB_WR32命令(opcode=0x20, addr=0x00000000)，验证haddr_o=0x00000000；2.发送AHB_RD32命令(opcode=0x21, addr=0xFFFFFFFF)，验证haddr_o=0xFFFFFFFF(全地址范围)；3.发送AHB_WR32到多个地址(0x10000000/0x20000000/0x30000000/0x40000000)验证地址透传；4.确认haddr_o[31:0]直接反映命令中的addr字段，无地址变换或映射；5.验证DFX统计寄存器地址(0x14~0x3F)通过CSR通道访问，不在AHB haddr_o上出现；期望结果：1.AHB命令addr字段直接透传到haddr_o[31:0]，无地址变换；2.地址范围0x00000000~0xFFFFFFFF均可访问(AHB从端决定是否响应)；3.非对齐地址(addr[1:0]!=0)在前置检查阶段被拒绝(STS_ALIGN_ERR(0x20))，不输出到haddr_o；4.DFX寄存器通过CSR地址空间(0x14~0x3F)读取，不在AHB地址空间中；5.地址空间完全隔离：CSR 0x00~0x3F走CSR通道，其他走AHB通道；coverage check点：对AHB地址全范围和CSR/AHB地址隔离收集功能覆盖率",
        None,
        ['TP_043'],
        ['CHK_APLC_019']
    ),
    (
        "TC_APLC_091",
        "test_memmap_random",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1；输入激励：1.随机选择命令类型(CSR/AHB Single/AHB Burst)，随机生成addr或reg_addr；2.对CSR命令(opcode=0x10/0x11)：随机reg_addr在0x00~0x3F范围内为合法，>=0x40触发BAD_REG；3.对AHB命令(opcode=0x20/0x21/0x22/0x23)：随机addr，4-byte对齐为合法，非对齐触发ALIGN_ERR；4.重复N≥100次，覆盖CSR/AHB地址空间边界；5.验证CSR地址不出现在haddr_o上，AHB地址不出现在csr_addr_o上；期望结果：1.CSR合法地址(0x00~0x3F)通过CSR通道正确执行，非法地址(>=0x40)返回STS_BAD_REG(0x10)；2.AHB对齐地址通过AHB通道正确执行，非对齐地址返回STS_ALIGN_ERR(0x20)；3.CSR/AHB地址空间严格隔离，无交叉映射；4.DFX寄存器(0x14~0x3F)通过CSR通道读取；5.所有合法地址命令返回STS_OK(0x00)；coverage check点：覆盖CSR/AHB地址空间边界和隔离性交叉覆盖率",
        None,
        ['TP_043'],
        ['CHK_APLC_019']
    ),
    (
        "TC_APLC_092",
        "test_ahb_rd32_2phase",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)；2.观察AHB 2-phase流水：地址相htrans_o=NONSEQ(2'b10)+haddr_o=0x10000000+hwrite_o=0+hsize_o=3'b010(WORD)；3.下一拍数据相：hready_i=1时采样hrdata_i[31:0]，htrans_o回到IDLE(2'b00)；4.验证地址相与数据相严格错开1拍：haddr_o在N拍有效，hrdata_i在N+1拍有效；5.连续发送2次AHB_RD32验证2-phase流水时序一致；期望结果：1.AHB_RD32地址相：htrans_o=NONSEQ(2'b10), haddr_o=0x10000000, hwrite_o=0, hsize_o=3'b010；2.AHB_RD32数据相：hready_i=1时采样hrdata_i[31:0]，axi_state=AXI_WAIT→AXI_DONE；3.地址相与数据相严格错开1拍(2-phase流水)；4.hburst_o=SINGLE(3'b000)表示单拍传输；5.status=STS_OK(0x00)，rdata=hrdata_i值；coverage check点：对AHB 2-phase流水时序收集功能覆盖率",
        None,
        ['TP_044'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_093",
        "test_ahb_incr4_timing",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_RD_BURST×4命令(opcode=0x23, burst_len=4, addr=0x10000000)；2.观察AXI_REQ首拍：htrans_o=NONSEQ(2'b10)+hburst_o=INCR4(3'b011)+haddr_o=A+hwrite_o=0；3.观察AXI_BURST 3拍SEQ：htrans_o=SEQ(2'b11)+haddr每拍+4(A+4/A+8/A+C)；4.观察4拍hrdata_i(D0/D1/D2/D3)依次采样推入TXFIFO；5.验证NONSEQ+SEQ×3时序正确，hsize_o=3'b010(WORD)固定；期望结果：1.INCR4时序：NONSEQ(1拍)+SEQ(3拍)=4拍地址相，haddr=A/A+4/A+8/A+C；2.hburst_o=INCR4(3'b011)在AXI_REQ时设定，AXI_BURST期间保持不变；3.hrdata_i在hready_i=1时被采样，4个beat数据依次推入TXFIFO；4.hsize_o=3'b010(WORD)全程固定，hwrite_o=0全程固定；5.status=STS_OK(0x00)，4个rdata beat正确；coverage check点：对INCR4时序(NONSEQ+SEQ)收集功能覆盖率",
        None,
        ['TP_045'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_094",
        "test_ahb_incr16_wr_timing",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000, wdata随机16个32bit word)；2.观察AXI_REQ首拍：htrans_o=NONSEQ(2'b10)+hburst_o=INCR16(3'b111)+hwrite_o=1；3.观察AXI_BURST 15拍SEQ：htrans_o=SEQ(2'b11)+haddr每拍+4；4.观察hwdata_o每拍输出D0/D1/.../D15，从RXFIFO读出依次驱动；5.验证NONSEQ+SEQ×15时序正确，haddr_o每拍+4递增；期望结果：1.INCR16时序：NONSEQ(1拍)+SEQ(15拍)=16拍地址相，haddr每拍+4；2.hburst_o=INCR16(3'b111)全程稳定不翻转；3.hwdata_o从RXFIFO读出依次输出D0~D15，haddr_o与hwdata_o错开1拍(2-phase)；4.hsize_o=3'b010(WORD)固定，hwrite_o=1保持整个burst；5.status=STS_OK(0x00)；coverage check点：对INCR16写burst时序(NONSEQ+SEQ×15)收集功能覆盖率",
        None,
        ['TP_046'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_095",
        "test_ahb_incr8_rd_timing",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8, addr=0x20000000)；2.观察AXI_REQ首拍：htrans_o=NONSEQ(2'b10)+hburst_o=INCR8(3'b101)+hwrite_o=0；3.观察AXI_BURST 7拍SEQ：htrans_o=SEQ(2'b11)+haddr每拍+4；4.观察8拍hrdata_i(D0~D7)依次采样推入TXFIFO，resp_last在末beat置位；5.验证NONSEQ+SEQ×7时序正确，haddr=A/A+4/.../A+28；期望结果：1.INCR8读时序：NONSEQ(1拍)+SEQ(7拍)=8拍地址相；2.hburst_o=INCR8(3'b101)全程稳定不翻转；3.hrdata_i在hready_i=1时采样，8个beat数据推入TXFIFO；4.hsize_o=3'b010(WORD)固定，hwrite_o=0保持整个burst；5.resp_last在D7(第8个beat)采样时置位，标记burst末尾；coverage check点：对INCR8读burst时序(NONSEQ+SEQ×7)收集功能覆盖率",
        None,
        ['TP_045'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_096",
        "test_ahb_burst_addr_increment",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR32(opcode=0x20, addr=0x10000000)，验证haddr_o=0x10000000(单拍地址)；2.发送AHB_WR_BURST×4(opcode=0x22, addr=0x20000000)，验证haddr_o: 0x20000000/0x20000004/0x20000008/0x2000000C(每拍+4)；3.发送AHB_RD_BURST×8(opcode=0x23, addr=0x30000000)，验证haddr_o: 0x30000000/0x30000004/.../0x3000001C(每拍+4)；4.发送AHB_WR_BURST×16(opcode=0x22, addr=0x40000000)，验证haddr_o每拍+4递增16拍；5.验证所有burst长度(1/4/8/16)的haddr递增步长固定=4(WORD size)；期望结果：1.AHB Single: haddr_o=addr(1拍)，hburst_o=SINGLE(3'b000)；2.INCR4: haddr每拍+4，NONSEQ+SEQ×3=4拍；3.INCR8: haddr每拍+4，NONSEQ+SEQ×7=8拍；4.INCR16: haddr每拍+4，NONSEQ+SEQ×15=16拍；5.haddr递增步长固定=4(hsize_o=3'b010(WORD))，不受lane_mode影响；coverage check点：对所有burst长度haddr递增时序收集功能覆盖率",
        None,
        ['TP_044', 'TP_045', 'TP_046'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_097",
        "test_ahb_hwrite_persistent",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0xDEADBEEF)，验证hwrite_o=1在整个事务期间保持；2.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)，验证hwrite_o=0在整个事务期间保持；3.发送AHB_WR_BURST×4命令(opcode=0x22)，验证hwrite_o=1在整个burst期间(AXI_REQ+AXI_BURST)保持不变；4.发送AHB_RD_BURST×4命令(opcode=0x23)，验证hwrite_o=0在整个burst期间保持不变；5.验证hwrite_o在burst期间不翻转(不出现写→读或读→写切换)；期望结果：1.AHB_WR32/hwrite_o=1(地址相+数据相)；AHB_RD32/hwrite_o=0；2.AHB_WR_BURST/hwrite_o=1在整个burst(AXI_REQ+AXI_BURST)期间保持不变；3.AHB_RD_BURST/hwrite_o=0在整个burst期间保持不变；4.hwrite_o在AXI_IDLE态=0(默认)，在AXI_REQ首拍设定后整个事务期间保持不变；5.hwrite_o不出现中途翻转(不同于htrans_o在NONSEQ→SEQ变化)；coverage check点：对hwrite_o在Single/Burst/读写组合的持久性收集功能覆盖率",
        None,
        ['TP_044', 'TP_046'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_098",
        "test_ahb_hburst_stability",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i可配置延迟；输入激励：1.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4, addr=0x10000000)；2.在burst期间注入hready_i=0(延迟响应)，验证hburst_o=INCR4(3'b011)保持不翻转；3.发送AHB_RD_BURST×8命令(opcode=0x23, burst_len=8)，全程hready_i=1；4.验证hburst_o=INCR8(3'b101)在AXI_REQ设定后AXI_BURST全程保持不变；5.交替测试INCR4/INCR8/INCR16，验证hburst_o全程稳定性；期望结果：1.hburst_o在AXI_REQ首拍设定(INCR4=3'b011/INCR8=3'b101/INCR16=3'b111)，后续AXI_BURST/AXI_WAIT期间保持不变；2.hready_i=0(延迟)不导致hburst_o翻转或重新设定；3.hburst_o仅在AXI_IDLE→AXI_REQ转换时更新，其他状态保持；4.Single命令hburst_o=SINGLE(3'b000)，与burst命令编码明确区分；5.所有burst类型hburst_o全程稳定性验证通过；coverage check点：对hburst_o在所有burst类型+延迟场景稳定性收集功能覆盖率",
        None,
        ['TP_045', 'TP_046'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_099",
        "test_ahb_single_write",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR32命令(opcode=0x20, addr=0x10000000, wdata=0x12345678)；2.观察AXI_REQ：htrans_o=NONSEQ(2'b10)+haddr_o=0x10000000+hwrite_o=1+hsize_o=3'b010(WORD)+hburst_o=SINGLE(3'b000)；3.观察AXI_WAIT数据相：hwdata_o=0x12345678(haddr与hwdata错开1拍)；4.观察AXI_DONE→AXI_IDLE自动恢复；5.验证Single写与burst写的htrans_o差异：Single仅1拍NONSEQ，无SEQ拍；期望结果：1.Single写htrans_o仅在AXI_REQ态=NONSEQ(2'b10)1拍，后续回到IDLE；2.hburst_o=SINGLE(3'b000)标识单拍传输；3.hwdata_o在数据相有效(与haddr_o错开1拍，2-phase流水)；4.hsize_o=3'b010(WORD)固定，hwrite_o=1保持整个事务；5.status=STS_OK(0x00)，AHB写完成；coverage check点：对AHB Single写时序(htrans=NONSEQ仅1拍)收集功能覆盖率",
        None,
        ['TP_044'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_100",
        "test_ahb_unsupported_behavior",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1；输入激励：1.验证不支持的AHB行为：模块不发起BUSY(2'b01)传输，htrans_o仅取IDLE(2'b00)/NONSEQ(2'b10)/SEQ(2'b11)；2.验证模块不发起8/16-bit传输：hsize_o始终=3'b010(WORD)，不出现3'b000/3'b001；3.验证模块不发起WRAP4/WRAP8/WRAP16：hburst_o仅取SINGLE(3'b000)/INCR4(3'b011)/INCR8(3'b101)/INCR16(3'b111)；4.连续执行100次命令(混合Single+Burst)，监测htrans_o/hsize_o/hburst_o不出现不支持的编码；5.验证hresp_i=0(OKAY)为正常路径，hresp_i=1(ERROR)为异常路径，模块正确处理；期望结果：1.htrans_o仅出现IDLE(2'b00)/NONSEQ(2'b10)/SEQ(2'b11)，不出现BUSY(2'b01)；2.hsize_o始终=3'b010(WORD=32bit)，不出现BYTE/HALFWORD编码；3.hburst_o仅出现SINGLE(3'b000)/INCR4(3'b011)/INCR8(3'b101)/INCR16(3'b111)，不出现WRAP编码；4.100次命令期间htrans_o/hsize_o/hburst_o均不出现不支持编码；5.hresp_i=0正常完成，hresp_i=1触发STS_AHB_ERR(0x40)；coverage check点：对htrans_o/hsize_o/hburst_o合法编码收集功能覆盖率",
        None,
        ['TP_044', 'TP_045'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_101",
        "test_ahb_random_burst",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.随机选择burst_len(1/4/8/16)和读写类型(WR_BURST/RD_BURST)；2.随机选择addr(4-byte对齐，不跨1KB边界)；3.随机选择lane_mode(2'b00/01/10/11)；4.发送对应AHB burst命令，验证htrans_o/hburst_o/haddr_o时序正确；5.重复N≥50次随机组合；期望结果：1.burst_len=1: hburst_o=SINGLE(3'b000), htrans_o仅1拍NONSEQ；2.burst_len=4: hburst_o=INCR4(3'b011), NONSEQ+SEQ×3；3.burst_len=8: hburst_o=INCR8(3'b101), NONSEQ+SEQ×7；4.burst_len=16: hburst_o=INCR16(3'b111), NONSEQ+SEQ×15；5.所有随机组合返回STS_OK(0x00)，haddr每拍+4递增；coverage check点：覆盖burst_len×读写×lane_mode×hburst编码交叉覆盖率",
        None,
        ['TP_044', 'TP_045', 'TP_046'],
        ['CHK_APLC_020']
    ),
    (
        "TC_APLC_102",
        "test_cross_lane_opcode_all",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1；2.使用嵌套循环遍历所有lane_mode×opcode组合；输入激励：1.for lane_mode in [2'b00,2'b01,2'b10,2'b11]：for opcode in [0x10,0x11,0x20,0x21,0x22,0x23]：执行命令；2.对Burst命令(opcode=0x22/0x23)使用burst_len=4作为代表；3.对每种组合验证命令正确执行，status=STS_OK(0x00)；4.验证帧接收拍数=bpc步进正确(1/4/8/16 bpc)；5.共24种组合全部覆盖；期望结果：1.4种lane_mode×6种opcode=24种组合全部正确执行，返回STS_OK(0x00)；2.1-bit模式bpc=1(48拍RX/WR_CSR)，4-bit模式bpc=4(12拍)，8-bit模式bpc=8(6拍)，16-bit模式bpc=16(3拍)；3.CSR命令(opcode=0x10/0x11)在所有lane_mode下均走CSR通道；4.AHB命令(opcode=0x20~0x23)在所有lane_mode下均走AHB通道；5.lane_mode×opcode交叉覆盖率100%；coverage check点：覆盖lane_mode×opcode全部24种组合交叉覆盖率100%",
        None,
        ['TP_010', 'TP_011', 'TP_012', 'TP_013', 'TP_023'],
        ['CHK_APLC_005', 'CHK_APLC_009']
    ),
    (
        "TC_APLC_103",
        "test_cross_lane_opcode_burst",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1；2.使用嵌套循环遍历所有lane_mode×burst命令组合；输入激励：1.for lane_mode in [2'b00,2'b01,2'b10,2'b11]：for burst_opcode in [0x22,0x23]：for burst_len in [4,8,16]：执行burst命令；2.验证每种组合的hburst_o编码：4→INCR4(3'b011), 8→INCR8(3'b101), 16→INCR16(3'b111)；3.验证haddr每拍+4递增，NONSEQ+SEQ时序正确；4.验证TXFIFO/RXFIFO在burst期间的推入/读出时序；5.共4×2×3=24种组合全部覆盖；期望结果：1.4种lane_mode×2种burst opcode×3种burst_len=24种组合全部正确；2.AHB_WR_BURST: payload通过RXFIFO→hwdata_o，所有数据正确；3.AHB_RD_BURST: hrdata_i→TXFIFO→pdo_o输出，所有数据正确；3.hburst编码与burst_len一致：4→INCR4, 8→INCR8, 16→INCR16；5.lane_mode×burst_opcode×burst_len交叉覆盖率100%；coverage check点：覆盖lane_mode×burst_opcode×burst_len交叉覆盖率100%",
        None,
        ['TP_019', 'TP_020', 'TP_021', 'TP_045', 'TP_046'],
        ['CHK_APLC_005', 'CHK_APLC_008', 'CHK_APLC_020']
    ),
    (
        "TC_APLC_104",
        "test_cross_opcode_status_all",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.使用嵌套循环遍历所有opcode×status_code组合；输入激励：1.for opcode in [0x10,0x11,0x20,0x21,0x22,0x23]：for error_type in [success,frame_err,bad_opcode,not_in_test,disabled,bad_reg,align_err,ahb_err,bad_burst,burst_bound]：2.对合法opcode注入对应错误条件，验证返回正确status_code；3.对成功场景验证返回STS_OK(0x00)；4.对每种opcode×status_code组合验证前置/执行期错误分类；5.共6×10=60种组合覆盖；期望结果：1.所有6种opcode均能触发STS_OK(0x00)成功路径；2.前置错误(FRAME_ERR/BAD_OPCODE/NOT_IN_TEST/DISABLED/BAD_REG/ALIGN_ERR/BAD_BURST/BURST_BOUND)适用于所有opcode；3.AHB_ERR(0x40)仅适用于AHB命令(opcode=0x20~0x23)，CSR命令(0x10/0x11)不触发AHB_ERR；4.BURST相关错误(BAD_BURST/BURST_BOUND)仅适用于Burst命令(opcode=0x22/0x23)；5.opcode×status_code交叉覆盖率100%；coverage check点：覆盖opcode×status_code交叉覆盖率，验证前置/执行期错误分类",
        None,
        ['TP_022', 'TP_023', 'TP_027', 'TP_028', 'TP_029', 'TP_030', 'TP_031', 'TP_032', 'TP_033', 'TP_034'],
        ['CHK_APLC_009', 'CHK_APLC_012', 'CHK_APLC_013', 'CHK_APLC_014']
    ),
    (
        "TC_APLC_105",
        "test_cross_burst_len_hburst",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR_BURST×4命令(burst_len=4)，验证hburst_o=INCR4(3'b011)；2.发送AHB_RD_BURST×8命令(burst_len=8)，验证hburst_o=INCR8(3'b101)；3.发送AHB_WR_BURST×16命令(burst_len=16)，验证hburst_o=INCR16(3'b111)；4.发送burst_len=1命令，验证hburst_o=SINGLE(3'b000)退化为Single；5.验证burst_len与hburst_o映射关系：1→SINGLE, 4→INCR4, 8→INCR8, 16→INCR16，无其他映射；期望结果：1.burst_len=1→hburst_o=SINGLE(3'b000), 仅1拍NONSEQ地址；2.burst_len=4→hburst_o=INCR4(3'b011), NONSEQ+SEQ×3；3.burst_len=8→hburst_o=INCR8(3'b101), NONSEQ+SEQ×7；4.burst_len=16→hburst_o=INCR16(3'b111), NONSEQ+SEQ×15；5.burst_len与hburst_o映射一一对应，无歧义编码；coverage check点：覆盖burst_len×hburst_o映射全部4种组合交叉覆盖率100%",
        None,
        ['TP_019', 'TP_020', 'TP_021', 'TP_044', 'TP_045', 'TP_046'],
        ['CHK_APLC_008', 'CHK_APLC_020']
    ),
    (
        "TC_APLC_106",
        "test_cross_fsm_state_transition",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1；输入激励：1.执行WR_CSR命令触发front_state: IDLE→ISSUE→WAIT_RESP→TA→TX→IDLE完整跳转；2.执行AHB_RD32命令触发front_state+axi_state联合跳转：front: IDLE→ISSUE→WAIT_RESP→TA→TX_BURST→TX→IDLE；axi: AXI_IDLE→AXI_REQ→AXI_WAIT→AXI_DONE→AXI_IDLE；3.执行AHB_WR_BURST×4命令触发front+axi+back三组FSM联合跳转；4.注入hresp_i=1错误触发axi_state: AXI_WAIT→AXI_ERR→AXI_IDLE跳转；5.通过DFX FSM可观测寄存器实时读取3组FSM状态，验证所有状态和跳转至少触发1次；期望结果：1.front_state 6态全部可达：IDLE(0)/ISSUE(1)/WAIT_RESP(2)/TA(3)/TX(4)/TX_BURST(5)；2.axi_state 6态全部可达：AXI_IDLE(0)/AXI_REQ(1)/AXI_BURST(2)/AXI_WAIT(3)/AXI_DONE(4)/AXI_ERR(5)；3.front_state×axi_state交叉跳转覆盖：重点覆盖(ISSUE,AXI_REQ)/(TX,AXI_DONE)/(TX_BURST,AXI_BURST)组合；4.AXI_ERR态仅通过hresp_i=1或超时触发，自动恢复AXI_IDLE；5.所有FSM状态和跳转至少被触发1次，FSM覆盖率100%；coverage check点：覆盖front_fsm×axi_fsm交叉覆盖率，所有状态和跳转至少触发1次",
        None,
        ['TP_040'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_107",
        "test_cross_back_fsm_state",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1；输入激励：1.执行AHB_WR_BURST×4命令触发back_state: S_IDLE→S_LOAD→S_EXEC→S_WAIT_AHB→S_BURST_LOOP→S_BUILD→S_DONE完整7态跳转；2.执行AHB_RD_BURST×8命令验证back_state在Burst读路径跳转(S_LOAD→S_EXEC→S_BURST_LOOP→S_BUILD)；3.执行WR_CSR命令验证back_state走CSR路径(S_LOAD→S_EXEC→S_BUILD→S_DONE，跳过S_WAIT_AHB和S_BURST_LOOP)；4.执行AHB_WR32命令验证back_state走AHB Single路径(S_LOAD→S_EXEC→S_WAIT_AHB→S_BUILD→S_DONE)；5.通过DFX FSM可观测寄存器验证back_state 7态全部可达；期望结果：1.back_state 7态全部可达：S_IDLE(0)/S_LOAD(1)/S_EXEC(2)/S_WAIT_AHB(3)/S_BURST_LOOP(4)/S_BUILD(5)/S_DONE(6)；2.CSR路径跳过S_WAIT_AHB和S_BURST_LOOP(无需AHB访问和burst循环)；3.AHB Single路径经过S_WAIT_AHB(单拍等待)但不经过S_BURST_LOOP；4.AHB Burst路径经过S_BURST_LOOP(burst循环)和S_WAIT_AHB(每beat等待)；5.back FSM覆盖率100%，所有状态和跳转至少触发1次；coverage check点：覆盖back_fsm 7态所有跳转路径收集功能覆盖率",
        None,
        ['TP_040'],
        ['CHK_APLC_017']
    ),
    (
        "TC_APLC_108",
        "test_cross_lane_burst_len_data",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1；2.使用嵌套循环遍历lane_mode×burst_len×数据模式；输入激励：1.for lane_mode in [2'b00,2'b01,2'b10,2'b11]：for burst_len in [4,8,16]：for burst_opcode in [0x22,0x23]：2.对AHB_WR_BURST：生成随机wdata(burst_len个32bit word)，验证RXFIFO→hwdata_o数据正确；3.对AHB_RD_BURST：验证hrdata_i→TXFIFO→pdo_o数据正确；4.数据模式：全0(0x00000000)/全1(0xFFFFFFFF)/walking-1/随机数据；5.共4×3×2×4=96种组合覆盖；期望结果：1.所有lane_mode下burst数据传输正确，无数据丢失或错位；2.RXFIFO写入和读出时序正确：wdata通过pdi_i串行接收→RXFIFO→hwdata_o并行输出；3.TXFIFO写入和读出时序正确：hrdata_i并行输入→TXFIFO→pdo_o串行输出；4.全0/全1/walking-1/随机数据模式均正确传输；5.lane_mode×burst_len×burst_opcode×数据模式交叉覆盖率100%；coverage check点：覆盖lane_mode×burst_len×数据模式交叉覆盖率100%",
        None,
        ['TP_010', 'TP_011', 'TP_012', 'TP_013', 'TP_019', 'TP_020', 'TP_021'],
        ['CHK_APLC_005', 'CHK_APLC_008']
    ),
    (
        "TC_APLC_109",
        "test_boundary_burst_len_max",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB从端hready_i=1(无延迟)；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16, addr=0x10000000)，验证最大burst长度正确执行；2.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16, addr=0x20000000)，验证最大burst读正确执行；3.验证INCR16时序：htrans_o=NONSEQ(1拍)+SEQ(15拍)，haddr每拍+4；4.验证吞吐量：16×4=64bytes在16拍+流水开销完成；5.验证RXFIFO/TXFIFO在最大burst期间不溢出(burst_len=16<32=FIFO深度)；期望结果：1.burst_len=16(INCR16)正确执行，16拍地址相+16拍数据相(写)或16拍地址+数据重叠(读)；2.hburst_o=INCR16(3'b111)全程稳定，haddr每拍+4递增；3.RXFIFO在burst_len=16时最大占用16×32bit(16<32不溢出)；4.TXFIFO在burst_len=16时最大占用16×33bit(16<32不溢出)；5.吞吐量达到最大：16-bit模式≈118MB/s写/116MB/s读@100MHz；coverage check点：对burst_len=16最大值场景收集功能覆盖率",
        None,
        ['TP_019', 'TP_020', 'TP_021', 'TP_037', 'TP_038'],
        ['CHK_APLC_008', 'CHK_APLC_016']
    ),
    (
        "TC_APLC_110",
        "test_boundary_addr_align_edge",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1；输入激励：1.发送AHB_WR32命令(opcode=0x20, addr=0x10000000)，addr[1:0]=2'b00(对齐)，验证返回STS_OK(0x00)；2.发送AHB_WR32命令(opcode=0x20, addr=0x10000001)，addr[1:0]=2'b01(非对齐)，验证返回STS_ALIGN_ERR(0x20)；3.发送AHB_RD32命令(opcode=0x21, addr=0x10000002)，addr[1:0]=2'b10(非对齐)，验证返回STS_ALIGN_ERR(0x20)；4.发送AHB_WR32命令(opcode=0x20, addr=0x10000003)，addr[1:0]=2'b11(非对齐)，验证返回STS_ALIGN_ERR(0x20)；5.发送AHB_WR_BURST×4命令(addr=0x10000FFC)，验证跨1KB边界返回STS_BURST_BOUND(0x81)；期望结果：1.addr[1:0]=2'b00(4-byte对齐)：返回STS_OK(0x00)，正常执行AHB访问；2.addr[1:0]=2'b01/2'b10/2'b11(非对齐)：返回STS_ALIGN_ERR(0x20)，不发起AHB访问(htrans_o=IDLE)；3.非对齐地址在前置检查阶段拒绝，不产生htrans_o脉冲；4.跨1KB边界：返回STS_BURST_BOUND(0x81)，不发起AHB访问；5.LAST_ERR依次更新为0x20/0x20/0x20/0x81(sticky)；coverage check点：对addr[1:0] 4种对齐值和1KB边界场景收集功能覆盖率",
        None,
        ['TP_028', 'TP_033'],
        ['CHK_APLC_012', 'CHK_APLC_014']
    ),
    (
        "TC_APLC_111",
        "test_boundary_fifo_depth",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，RXFIFO 32×32bit，TXFIFO 32×33bit；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16)，推入16个32bit word到RXFIFO；2.验证rxfifo_cnt_q=16，rxfifo_full_o=0(FIFO未满，16<32)；3.发送第2个AHB_WR_BURST×16命令，继续推入数据直至rxfifo_cnt_q=32，rxfifo_full_o=1(FIFO满)；4.验证FIFO满时接收暂停，后端drain后恢复；5.对TXFIFO执行类似操作：AHB_RD_BURST×16产生16个32bit+status推入TXFIFO，验证txfifo_cnt_q和txfifo_empty_o；期望结果：1.RXFIFO深度32：rxfifo_cnt_q=0时empty_o=1，=32时full_o=1，1~31时均不触发；2.TXFIFO深度32：txfifo_cnt_q=0时empty_o=1，=32时full_o=1；3.FIFO满时接收暂停但不丢失数据，drain后恢复；4.FIFO空时发送暂停(stall)，pdo_oe_o保持高但不输出新数据；5.FIFO边界(depth=32)行为正确，不溢出/不欠读；coverage check点：对rxfifo_cnt_q/txfifo_cnt_q level(0/1~15/16~30/31/32)收集功能覆盖率",
        None,
        ['TP_047', 'TP_048'],
        ['CHK_APLC_006']
    ),
    (
        "TC_APLC_112",
        "test_boundary_csr_addr_edge",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，CSR地址范围0x00~0x3F；输入激励：1.发送RD_CSR命令(opcode=0x11, reg_addr=0x00(VERSION))，验证合法地址返回STS_OK(0x00)；2.发送RD_CSR命令(opcode=0x11, reg_addr=0x3F)，验证合法地址上界返回STS_OK(0x00)或对应寄存器值；3.发送RD_CSR命令(opcode=0x11, reg_addr=0x40)，验证越界地址返回STS_BAD_REG(0x10)；4.发送RD_CSR命令(opcode=0x11, reg_addr=0xFF)，验证越界地址返回STS_BAD_REG(0x10)；5.发送RD_CSR命令(opcode=0x11, reg_addr=0x7F)，验证越界地址返回STS_BAD_REG(0x10)；期望结果：1.reg_addr=0x00(VERSION)：合法，返回STS_OK(0x00)+rdata=VERSION常量；2.reg_addr=0x3F：合法上界，返回STS_OK(0x00)+rdata=DFX寄存器值；3.reg_addr=0x40：非法(>=0x40)，返回STS_BAD_REG(0x10)，不发起CSR访问(csr_rd_en_o=0)；4.reg_addr=0xFF/0x7F：非法，返回STS_BAD_REG(0x10)；5.CSR地址边界：合法[0x00,0x3F]，非法[0x40,0xFF]，严格检查无遗漏；coverage check点：对CSR地址边界(0x3F/0x40)收集功能覆盖率",
        None,
        ['TP_006'],
        ['CHK_APLC_003']
    ),
    (
        "TC_APLC_113",
        "test_boundary_timeout_255",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，BUS_TIMEOUT_CYCLES=256，hready_i可配置；输入激励：1.发送AHB_RD32命令(opcode=0x21, addr=0x10000000)，注入hready_i=0持续255个周期；2.验证255周期不触发超时(计数器0→254)，恢复hready_i=1后命令正常完成；3.发送AHB_RD32命令，注入hready_i=0持续256个周期；4.验证256周期触发超时(计数器0→255)，返回STS_AHB_ERR(0x40)；5.对比255和256边界：255不超时/256超时，边界行为严格正确；期望结果：1.hready_i=0持续255周期：计数器0→254(未达255阈值)，恢复后命令正常完成，status=STS_OK(0x00)；2.hready_i=0持续256周期：计数器0→255(达到阈值)，触发超时，返回STS_AHB_ERR(0x40)；3.超时边界精确：255不超时/256超时，无灰色地带；4.超时后AXI_ERR→AXI_IDLE自动恢复，FIFO drain；5.LAST_ERR=0x40(sticky)仅超时时更新；coverage check点：对BUS_TIMEOUT边界(255/256周期)收集功能覆盖率",
        None,
        ['TP_031'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_114",
        "test_boundary_burst_len_illegal",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，burst_len合法集合={1,4,8,16}；输入激励：1.发送AHB_WR_BURST命令(opcode=0x22)，burst_len=0，验证返回STS_BAD_BURST(0x80)；2.发送AHB_RD_BURST命令(opcode=0x23)，burst_len=2，验证返回STS_BAD_BURST(0x80)；3.发送burst_len=3,5,6,7,9,10,11,12,13,14,15依次测试所有非法值；4.发送burst_len=1,4,8,16验证所有合法值正常执行；5.对比合法/非法边界：burst_len=1(合法) vs burst_len=0(非法)，burst_len=4(合法) vs burst_len=3(非法)；期望结果：1.burst_len=0: 返回STS_BAD_BURST(0x80)，不发起AHB访问(htrans_o=IDLE)；2.burst_len=2,3,5~15: 均返回STS_BAD_BURST(0x80)；3.burst_len=1,4,8,16: 正常执行返回STS_OK(0x00)，hburst_o编码正确；4.非法burst_len在前置检查阶段拒绝，不产生htrans_o脉冲；5.LAST_ERR在非法burst_len时更新为0x80(sticky)；coverage check点：对burst_len全空间(0~16)合法/非法边界收集功能覆盖率",
        None,
        ['TP_032'],
        ['CHK_APLC_014']
    ),
    (
        "TC_APLC_115",
        "test_boundary_1kb_boundary",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，AHB 1KB地址边界对齐检查；输入激励：1.发送AHB_WR_BURST×4命令(opcode=0x22, burst_len=4, addr=0x10000FF0)，addr+4×4=0x10001000跨1KB边界(0x10000C00~0x10001000)，验证返回STS_BURST_BOUND(0x81)；2.发送AHB_WR_BURST×4命令(addr=0x10000BF0)，addr+4×4=0x10000C00刚好在1KB边界内(0x10000800~0x10000BFF+4beat=0x10000BFC+0x10=不跨)，验证返回STS_OK(0x00)；3.发送AHB_RD_BURST×16命令(addr=0x10000FC0)，addr+4×16=0x10001000跨1KB边界，验证返回STS_BURST_BOUND(0x81)；4.发送AHB_WR32命令(addr=0x10000FFC)，burst_len=1不跨1KB(addr+4=0x10001000刚好不跨beat，但1beat不检查)，验证返回STS_OK(0x00)；5.验证1KB边界检查公式：addr[11:0]+4×burst_len需≤addr[11:0]所在1KB子块的末尾(即(addr[11:0]>>10+1)<<10)；期望结果：1.addr跨1KB边界：返回STS_BURST_BOUND(0x81)，不发起AHB访问(htrans_o=IDLE)；2.addr刚好在1KB边界内：返回STS_OK(0x00)，正常执行；3.INCR16跨1KB边界：同样返回STS_BURST_BOUND(0x81)；4.Single(burst_len=1)：不触发1KB边界检查，正常执行；5.1KB边界检查精确：跨/不跨边界判断严格正确；coverage check点：对1KB地址边界(跨/不跨)场景收集功能覆盖率",
        None,
        ['TP_033'],
        ['CHK_APLC_014']
    ),
    (
        "TC_APLC_116",
        "test_random_full_scenario",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，覆盖所有48个TP和20个Checker；输入激励：1.随机选择lane_mode(2'b00/01/10/11)×opcode(6种)×burst_len(1/4/8/16)×成功/失败场景；2.成功路径：正常WR_CSR/RD_CSR/AHB_WR32/AHB_RD32/AHB_WR_BURST/AHB_RD_BURST，验证STS_OK(0x00)；3.失败路径：随机注入9种错误(frame_err/bad_opcode/not_in_test/disabled/bad_reg/align_err/ahb_err/bad_burst/burst_bound)，验证对应错误码；4.随机配置test_mode_i(0/1)和en_i(0/1)验证门控拒绝；5.重复执行N≥500次，每次随机参数组合，确保覆盖所有功能场景；期望结果：1.所有成功路径返回STS_OK(0x00)，CSR/AHB通道正确执行；2.所有失败路径返回对应错误码，优先级链0x01>0x02>0x04>0x08>0x10>0x20>0x80>0x81正确；3.AHB_ERR(0x40)与前置错误互斥，仅在前置检查通过后AHB执行期产生；4.所有lane_mode×opcode组合正确执行，帧时序(bpc步进/turnaround)正确；5.覆盖所有48个TP的验证场景，功能覆盖率接近100%；coverage check点：覆盖lane_mode×opcode×burst_len×成功/失败×门控条件全交叉覆盖率",
        None,
        ['TP_001', 'TP_002', 'TP_003', 'TP_004', 'TP_005', 'TP_006', 'TP_007', 'TP_008', 'TP_009', 'TP_010', 'TP_011', 'TP_012', 'TP_013', 'TP_014', 'TP_015', 'TP_016', 'TP_017', 'TP_018', 'TP_019', 'TP_020', 'TP_021', 'TP_022', 'TP_023', 'TP_024', 'TP_025', 'TP_026', 'TP_027', 'TP_028', 'TP_029', 'TP_030', 'TP_031', 'TP_032', 'TP_033', 'TP_034', 'TP_035', 'TP_036', 'TP_037', 'TP_038', 'TP_039', 'TP_040', 'TP_041', 'TP_042', 'TP_043', 'TP_044', 'TP_045', 'TP_046', 'TP_047', 'TP_048'],
        ['CHK_APLC_001', 'CHK_APLC_002', 'CHK_APLC_003', 'CHK_APLC_004', 'CHK_APLC_005', 'CHK_APLC_006', 'CHK_APLC_007', 'CHK_APLC_008', 'CHK_APLC_009', 'CHK_APLC_010', 'CHK_APLC_011', 'CHK_APLC_012', 'CHK_APLC_013', 'CHK_APLC_014', 'CHK_APLC_015', 'CHK_APLC_016', 'CHK_APLC_017', 'CHK_APLC_018', 'CHK_APLC_019', 'CHK_APLC_020']
    ),
    (
        "TC_APLC_117",
        "test_random_error_priority_chain",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1；输入激励：1.随机选择2-4个前置错误条件同时满足，验证仅返回最高优先级错误码；2.优先级链：FRAME_ERR(0x01)>BAD_OPCODE(0x02)>NOT_IN_TEST(0x04)>DISABLED(0x08)>BAD_REG(0x10)>ALIGN_ERR(0x20)>BAD_BURST(0x80)>BURST_BOUND(0x81)；3.随机注入hresp_i=1或hready_i=0(超时)触发AHB_ERR(0x40)，验证0x40与前置错误互斥；4.每次错误后验证LAST_ERR更新为最高优先级错误码(sticky)；5.重复N≥100次随机多条件组合，验证优先级链在所有随机场景下正确；期望结果：1.多条件重叠时返回优先级链中最高级别错误码，低优先级不覆盖；2.FRAME_ERR(0x01)始终最高，帧中止场景一律返回0x01；3.BAD_OPCODE(0x02)第二优先级，opcode非法时跳过后续地址/寄存器检查；4.AHB_ERR(0x40)仅在前置检查全通过后AHB执行期产生，与前置错误互斥；5.100次随机场景优先级链验证全部通过；coverage check点：覆盖错误优先级链所有级别组合×随机参数交叉覆盖率",
        None,
        ['TP_027'],
        ['CHK_APLC_012']
    ),
    (
        "TC_APLC_118",
        "test_random_burst_error_recovery",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，AHB从端hresp_i和hready_i可配置；输入激励：1.随机选择burst命令(AHB_WR_BURST/AHB_RD_BURST)和burst_len(4/8/16)；2.在burst执行中途(随机选择beat位置)注入hresp_i=1(ERROR)触发burst中止；3.验证已完成beat数据正确，中止beat不写入，TXFIFO/RXFIFO drain；4.随机注入hready_i=0超时(256+周期)触发超时错误，验证burst中止和恢复；5.重复N≥50次随机burst错误场景，验证所有burst_len和错误位置组合；期望结果：1.burst中途hresp_i=1：已完成beat数据保留(写入TXFIFO/RXFIFO)，中止beat不写入；2.burst超时：hready_i=0持续256周期触发超时，返回STS_AHB_ERR(0x40)；3.AHB错误恢复：AXI_ERR→AXI_IDLE自动恢复，FIFO强制drain，后续命令可正常执行；4.所有burst_len(4/8/16)和错误位置(首拍/中间/末拍)组合验证通过；5.模块从burst错误中恢复不需要复位，仅AXI_ERR→AXI_IDLE自动恢复；coverage check点：覆盖burst_len×错误类型×错误位置交叉覆盖率",
        None,
        ['TP_030', 'TP_031', 'TP_034'],
        ['CHK_APLC_013']
    ),
    (
        "TC_APLC_119",
        "test_random_backpressure_timing",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i=2'b11（16-bit模式）；2.CTRL.EN=1，RXFIFO 32×32bit，TXFIFO 32×33bit；输入激励：1.发送AHB_WR_BURST×16命令(opcode=0x22, burst_len=16)，注入后端处理延迟使rxfifo_full_o=1；2.观察rxfifo_full_o=1→0时序：接收暂停/恢复的时间点，验证无数据丢失；3.发送AHB_RD_BURST×16命令(opcode=0x23, burst_len=16)，注入TXFIFO空延迟使txfifo_empty_o=1；4.观察txfifo_empty_o=1→0时序：TX暂停/恢复的时间点，验证pdo_oe_o保持高+pdo_o保持上一拍数据；5.重复N≥30次随机背压和stall时机组合，验证FIFO流控时序正确；期望结果：1.rxfifo_full_o=1时SLC_CAXIS暂停接收(rx_shift_en=0)，rxfifo_full_o=0后立即恢复；2.txfifo_empty_o=1时SLC_SAXIS暂停移位，pdo_oe_o=1(保持方向)，pdo_o保持上一拍数据；3.txfifo_empty_o=0后SLC_SAXIS立即恢复移位输出，无额外延迟；4.背压/stall期间hburst_o保持稳定不翻转；5.所有背压/stall场景不丢失数据，命令最终返回STS_OK(0x00)；coverage check点：覆盖rxfifo_full/txfifo_empty时序×burst_len交叉覆盖率",
        None,
        ['TP_047', 'TP_048'],
        ['CHK_APLC_006']
    ),
    (
        "TC_APLC_120",
        "test_random_full_regression",
        "配置条件：1.模块复位完成，test_mode_i=1，en_i=1，lane_mode_i随机；2.CTRL.EN=1，覆盖所有48个TP和20个Checker，全场景回归测试；输入激励：1.阶段1-时钟复位：随机复位时机(空闲/事务中/burst中途)，验证复位状态正确；2.阶段2-CSR寄存器：随机CSR读写序列，验证RW/RO/WC属性和时序；3.阶段3-AHB Single/Burst：随机lane_mode×opcode×burst_len组合，验证AHB协议时序；4.阶段4-错误注入：随机注入9种错误类型，验证优先级链和恢复；5.阶段5-全场景交叉：随机组合所有维度(lane_mode×opcode×burst_len×成功/失败×门控条件×背压×DFX统计)，N≥1000次回归；期望结果：1.所有阶段命令返回正确status_code(STS_OK或对应错误码)；2.优先级链在所有随机场景下正确：0x01>0x02>0x04>0x08>0x10>0x20>0x80>0x81，0x40与前置互斥；3.DFX统计计数器总和与实际执行命令数一致；4.所有48个TP的验证场景被覆盖，功能覆盖率和代码覆盖率接近100%；5.1000次回归测试全部通过，无随机失败；coverage check点：覆盖所有功能覆盖率维度和交叉覆盖组，目标功能覆盖率100%",
        None,
        ['TP_001', 'TP_002', 'TP_003', 'TP_004', 'TP_005', 'TP_006', 'TP_007', 'TP_008', 'TP_009', 'TP_010', 'TP_011', 'TP_012', 'TP_013', 'TP_014', 'TP_015', 'TP_016', 'TP_017', 'TP_018', 'TP_019', 'TP_020', 'TP_021', 'TP_022', 'TP_023', 'TP_024', 'TP_025', 'TP_026', 'TP_027', 'TP_028', 'TP_029', 'TP_030', 'TP_031', 'TP_032', 'TP_033', 'TP_034', 'TP_035', 'TP_036', 'TP_037', 'TP_038', 'TP_039', 'TP_040', 'TP_041', 'TP_042', 'TP_043', 'TP_044', 'TP_045', 'TP_046', 'TP_047', 'TP_048'],
        ['CHK_APLC_001', 'CHK_APLC_002', 'CHK_APLC_003', 'CHK_APLC_004', 'CHK_APLC_005', 'CHK_APLC_006', 'CHK_APLC_007', 'CHK_APLC_008', 'CHK_APLC_009', 'CHK_APLC_010', 'CHK_APLC_011', 'CHK_APLC_012', 'CHK_APLC_013', 'CHK_APLC_014', 'CHK_APLC_015', 'CHK_APLC_016', 'CHK_APLC_017', 'CHK_APLC_018', 'CHK_APLC_019', 'CHK_APLC_020']
    ),
]


# ============================================================
# Functional Coverage Model
# ============================================================

FUNCTIONAL_COVERAGE_MODEL = """
covergroup aplc_lite_functional_cg;
    //=== Dimension 1: Configuration Coverage ===
    lane_mode_cp: coverpoint lane_mode_i {
        bins lane_1bit  = {2'b00};
        bins lane_4bit  = {2'b01};
        bins lane_8bit  = {2'b10};
        bins lane_16bit = {2'b11};
    }

    ctrl_en_cp: coverpoint ctrl_en {
        bins en_on  = {1'b1};
        bins en_off = {1'b0};
    }

    test_mode_cp: coverpoint test_mode_i {
        bins test_on  = {1'b1};
        bins test_off = {1'b0};
    }

    //=== Dimension 2: Command/Opcode Coverage ===
    opcode_cp: coverpoint opcode_latched_q {
        bins wr_csr      = {8'h10};
        bins rd_csr      = {8'h11};
        bins ahb_wr32    = {8'h20};
        bins ahb_rd32    = {8'h21};
        bins ahb_wr_burst = {8'h22};
        bins ahb_rd_burst = {8'h23};
        bins illegal     = default;
    }

    burst_len_cp: coverpoint burst_len_latched_q {
        bins single = {1};
        bins incr4  = {4};
        bins incr8  = {8};
        bins incr16 = {16};
        bins illegal = default;
    }

    hburst_cp: coverpoint hburst_o {
        bins single = {3'b000};
        bins incr4  = {3'b011};
        bins incr8  = {3'b101};
        bins incr16 = {3'b111};
    }

    //=== Dimension 3: Status Code Coverage ===
    status_cp: coverpoint resp_status {
        bins ok          = {8'h00};
        bins frame_err   = {8'h01};
        bins bad_opcode  = {8'h02};
        bins not_in_test = {8'h04};
        bins disabled    = {8'h08};
        bins bad_reg     = {8'h10};
        bins align_err   = {8'h20};
        bins ahb_err     = {8'h40};
        bins bad_burst   = {8'h80};
        bins burst_bound = {8'h81};
    }

    //=== Dimension 4: FSM State Coverage ===
    front_fsm_cp: coverpoint front_state_q {
        bins idle      = {3'd0};
        bins issue     = {3'd1};
        bins wait_resp = {3'd2};
        bins ta        = {3'd3};
        bins tx        = {3'd4};
        bins tx_burst  = {3'd5};
    }

    axi_fsm_cp: coverpoint axi_state_q {
        bins axi_idle  = {3'd0};
        bins axi_req   = {3'd1};
        bins axi_burst = {3'd2};
        bins axi_wait  = {3'd3};
        bins axi_done  = {3'd4};
        bins axi_err   = {3'd5};
    }

    back_fsm_cp: coverpoint back_state_q {
        bins s_idle       = {3'd0};
        bins s_load       = {3'd1};
        bins s_exec       = {3'd2};
        bins s_wait_ahb   = {3'd3};
        bins s_burst_loop = {3'd4};
        bins s_build      = {3'd5};
        bins s_done       = {3'd6};
    }

    //=== Dimension 5: FIFO & Boundary Coverage ===
    rxfifo_level_cp: coverpoint rxfifo_cnt_q {
        bins empty       = {0};
        bins low         = {[1:15]};
        bins mid         = {[16:30]};
        bins full        = {32};
    }

    txfifo_level_cp: coverpoint txfifo_cnt_q {
        bins empty       = {0};
        bins low         = {[1:15]};
        bins mid         = {[16:30]};
        bins full        = {32};
    }

    addr_align_cp: coverpoint ahb_addr[1:0] {
        bins aligned   = {2'b00};
        bins misalign1 = {2'b01};
        bins misalign2 = {2'b10};
        bins misalign3 = {2'b11};
    }

    //=== Cross Coverage Groups ===
    lane_opcode_cross:    cross lane_mode_cp, opcode_cp;
    lane_burst_cross:     cross lane_mode_cp, burst_len_cp;
    opcode_status_cross:  cross opcode_cp, status_cp;
    burst_hburst_cross:   cross burst_len_cp, hburst_cp;
    front_axi_cross:      cross front_fsm_cp, axi_fsm_cp;
    lane_fifo_cross:      cross lane_mode_cp, rxfifo_level_cp;
    mode_gate_cross:      cross test_mode_cp, ctrl_en_cp, opcode_cp;
    burst_err_cross:      cross burst_len_cp, status_cp;
endcovergroup
"""


# ============================================================
# TP to Checker/Testcase Linking
# ============================================================

def build_tp_links(checkers, testcases):
    """Build tp_id -> (checker_ids, testcase_ids) mapping."""
    tp_map = {}

    for chk_id, _, _, _, tp_ids in checkers:
        for tp_id in tp_ids:
            tp_map.setdefault(tp_id, {"chk": set(), "tc": set()})
            tp_map[tp_id]["chk"].add(chk_id)

    for tc_id, _, _, _, tp_ids, chk_ids in testcases:
        for tp_id in tp_ids:
            tp_map.setdefault(tp_id, {"chk": set(), "tc": set()})
            tp_map[tp_id]["tc"].add(tc_id)

    return tp_map


def link_all_tps(wb, checkers, testcases):
    """Link TPs to their checker and testcase IDs in FL-TP sheet."""
    tp_map = build_tp_links(checkers, testcases)

    for tp_id, links in tp_map.items():
        checker_str = ",".join(sorted(links["chk"]))
        testcase_str = ",".join(sorted(links["tc"]))
        link_tp_to_checker_testcase(wb, tp_id, checker_str, testcase_str)

    # Verify all 48 TPs are covered
    all_tps = {f"TP_{i:03d}" for i in range(1, 49)}
    covered = set(tp_map.keys())
    uncovered = all_tps - covered
    if uncovered:
        print(f"WARNING: Uncovered TPs: {uncovered}")
    else:
        print(f"All {len(all_tps)} TPs covered with checkers and testcases.")


# ============================================================
# Main Function
# ============================================================

def main():
    input_file = "RTM_AI_FLTP.xlsx"
    output_file = "RTM_AI_FLTP_generated.xlsx"

    print(f"Loading input RTM: {input_file}")
    wb = openpyxl.load_workbook(input_file)

    # 1. Add all checkers
    print(f"Adding {len(CHECKERS)} checkers...")
    for chk_id, chk_name, chk_desc, note, tp_ids in CHECKERS:
        add_checker_to_rtm(wb, chk_id, chk_name, chk_desc, note)
    print(f"  Done: {len(CHECKERS)} checkers added.")

    # 2. Add all testcases
    print(f"Adding {len(TESTCASES)} testcases...")
    for tc_id, tc_name, tc_desc, note, tp_ids, chk_ids in TESTCASES:
        add_testcase_to_rtm(wb, tc_id, tc_name, tc_desc, note)
    print(f"  Done: {len(TESTCASES)} testcases added.")

    # 3. Link TPs to checkers and testcases
    print("Linking TPs to checkers and testcases...")
    link_all_tps(wb, CHECKERS, TESTCASES)

    # 4. Save output
    print(f"Saving output RTM: {output_file}")
    save_rtm(wb, output_file)
    print("RTM generation complete!")

    # 5. Print summary
    print(f"\n=== Summary ===")
    print(f"Checkers: {len(CHECKERS)}")
    print(f"Testcases: {len(TESTCASES)}")
    tp_map = build_tp_links(CHECKERS, TESTCASES)
    print(f"TPs covered: {len(tp_map)}/48")
    print(f"Functional coverage model: aplc_lite_functional_cg")

    # Print functional coverage model
    print(f"\n=== Functional Coverage Model ===")
    print(FUNCTIONAL_COVERAGE_MODEL)


if __name__ == '__main__':
    main()

