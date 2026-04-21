#!/usr/bin/env python3
"""Generate complete RTM file from LRS and RTM template."""

import sys
import shutil
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from copy import copy

sys.path.insert(0, '.claude/skills/RTM_TP2TC_skills/scripts')
from rtm_utils import add_checker_to_rtm, add_testcase_to_rtm, link_tp_to_checker_testcase, save_rtm

TEMPLATE = 'TBUS_RTM.xlsx'
OUTPUT = 'TBUS_RTM_Generated.xlsx'

# ============================================================
# Checker definitions: (chk_id, chk_name, chk_description, [tp_ids])
# ============================================================
CHECKERS = [
    ('CHK_001', 'clk_freq_checker',
     '对于时钟，检查clk_i频率稳定性和目标频率约束：\n'
     '1、频率值检查：连续采集clk_i上升沿和下降沿，计算实际周期，判断是否处于100MHz目标频率的允许误差范围内（±1%）；\n'
     '2、时钟稳定性检查：通过连续采样clk_i周期，对比相邻两个周期的频率偏差是否在3%内；\n'
     '3、单时钟域验证：确认协议接收（pdi_i采样）、状态机控制（front_state/back_state跳转）和AHB-Lite主接口（haddr_o/htrans_o驱动）均在clk_i上升沿同步，无跨时钟域问题。',
     ['TP_001', 'TP_002']),

    ('CHK_002', 'reset_checker',
     '对于复位，检查rst_n_i异步复位与同步释放行为及复位后状态：\n'
     '1、异步复位触发检查：rst_n_i下降沿立即触发复位，无需等待clk_i上升沿；\n'
     '2、同步释放检查：rst_n_i释放时在clk_i上升沿同步退出复位；\n'
     '3、FSM状态恢复检查：复位后front_state=IDLE(3\'d0)，back_state=S_IDLE(3\'d0)；\n'
     '4、输出默认值检查：复位后pdo_oe_o=0，htrans_o=2\'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0，pdo_o=4\'b0；\n'
     '5、寄存器默认值检查：CTRL.EN=0，CTRL.LANE_MODE=2\'b00(1-bit默认模式)，所有协议/响应上下文清空，错误状态清除。',
     ['TP_003', 'TP_004', 'TP_005']),

    ('CHK_003', 'csr_write_checker',
     '对于CSR写操作，检查WR_CSR(0x10)命令的写时序和数据正确性：\n'
     '1、写使能脉冲检查：csr_wr_en_o脉冲持续1个clk_i周期，同周期csr_addr_o和csr_wdata_o有效；\n'
     '2、地址范围检查：csr_addr_o有效范围为0x00~0x3F，对应VERSION(0x00)、CTRL(0x04)、STATUS(0x08)、LAST_ERR(0x0C)；\n'
     '3、写数据检查：外部CSR File在csr_wr_en_o=1的同周期采样csr_addr_o/csr_wdata_o并写入；\n'
     '4、响应检查：写操作完成后返回STS_OK(0x00)状态码。',
     ['TP_006']),

    ('CHK_004', 'csr_read_checker',
     '对于CSR读操作，检查RD_CSR(0x11)命令的读时序和数据正确性：\n'
     '1、读使能脉冲检查：csr_rd_en_o脉冲持续1个clk_i周期；\n'
     '2、1周期读延迟检查：外部CSR File在csr_rd_en_o脉冲后的下一个clk_i周期将读数据稳定在csr_rdata_i[31:0]上；\n'
     '3、读数据正确性检查：模块正确采样csr_rdata_i，响应帧中RDATA[31:0]与CSR File返回值一致；\n'
     '4、响应检查：读操作完成后返回STS_OK(0x00)+RDATA[31:0]。',
     ['TP_007']),

    ('CHK_005', 'csr_bad_reg_checker',
     '对于CSR非法地址检测，检查reg_addr>=0x40时的前置拒绝行为：\n'
     '1、非法地址检测检查：当WR_CSR(0x10)或RD_CSR(0x11)命令的reg_addr>=0x40(CSR_ADDR_MAX=0x3F)时，前置检查拒绝访问；\n'
     '2、状态码检查：返回STS_BAD_REG(0x10)；\n'
     '3、不发起访问检查：csr_rd_en_o=0，csr_wr_en_o=0，不发起CSR读/写操作。',
     ['TP_008', 'TP_034']),

    ('CHK_006', 'mode_gate_checker',
     '对于工作模式，检查test_mode_i和en_i的前置门控以及lane模式切换：\n'
     '1、test_mode_i门控检查：test_mode_i=0时，任何命令均返回STS_NOT_IN_TEST(0x04)，不发起CSR/AHB访问；\n'
     '2、en_i门控检查：test_mode_i=1且en_i=0时，任何命令均返回STS_DISABLED(0x08)，不发起CSR/AHB访问；\n'
     '3、正常模式检查：test_mode_i=1且en_i=1时，前置检查通过，正常执行命令并返回正确状态码和数据；\n'
     '4、1-bit模式检查：lane_mode_i=2\'b00时，每拍仅pdi_i[0]有效，帧接收周期为帧长bit数；\n'
     '5、4-bit模式检查：lane_mode_i=2\'b01时，每拍pdi_i[3:0]均有效，帧接收周期为帧长/4。',
     ['TP_009', 'TP_010', 'TP_011', 'TP_012', 'TP_013']),

    ('CHK_007', 'frame_io_checker',
     '对于数据接口，检查类SPI帧协议的时序和数据正确性：\n'
     '1、帧边界检查：pcs_n_i=1时模块空闲；pcs_n_i拉低时开启帧接收；pcs_n_i拉高时结束事务；\n'
     '2、输入数据检查：1-bit模式仅pdi_i[0]有效；4-bit模式pdi_i[3:0]均有效；所有数据MSB-first顺序传输；\n'
     '3、输出方向检查：响应阶段pdo_oe_o=1，模块驱动pdo_o[3:0]输出数据；非发送阶段pdo_oe_o=0，pdo_o值无意义；\n'
     '4、帧长度检查：WR_CSR(0x10)接收48bit(opcode8+reg_addr8+wdata32)；RD_CSR(0x11)接收16bit(opcode8+reg_addr8)；AHB_WR32(0x20)接收72bit(opcode8+addr32+wdata32)；AHB_RD32(0x21)接收40bit(opcode8+addr32)；\n'
     '5、响应格式检查：写类命令响应8bit状态码；读类命令响应40bit(8bit状态+32bit读数据)；\n'
     '6、帧中止检查：帧接收未完成时pcs_n_i提前拉高，产生frame_abort，返回STS_FRAME_ERR(0x01)，不发起CSR/AHB访问；\n'
     '7、turnaround检查：请求阶段与响应阶段之间固定插入1个clk_i周期turnaround；turnaround期间pdo_oe_o=0；TX阶段pdo_oe_o=1。',
     ['TP_014', 'TP_015', 'TP_016', 'TP_017', 'TP_018', 'TP_019', 'TP_020', 'TP_021', 'TP_022']),

    ('CHK_008', 'opcode_checker',
     '对于opcode解析，检查合法与非法opcode的处理：\n'
     '1、合法opcode检查：前端收满8bit后锁存opcode，根据opcode确定expected_rx_bits——0x10(WR_CSR)对应48bit、0x11(RD_CSR)对应16bit、0x20(AHB_WR32)对应72bit、0x21(AHB_RD32)对应40bit；正确发起对应类型任务；\n'
     '2、非法opcode检查：opcode不在{0x10,0x11,0x20,0x21}中时，前置检查返回STS_BAD_OPCODE(0x02)，不发起CSR/AHB访问。',
     ['TP_023', 'TP_024', 'TP_031']),

    ('CHK_009', 'ctrl_reg_checker',
     '对于CTRL寄存器配置，检查EN/LANE_MODE/SOFT_RST字段功能：\n'
     '1、EN字段检查：CTRL.EN=1时模块使能，CTRL.EN=0时返回STS_DISABLED(0x08)；\n'
     '2、LANE_MODE字段检查：CTRL.LANE_MODE=2\'b00对应1-bit模式，2\'b01对应4-bit模式，其他值为非法（MVP不支持）；\n'
     '3、SOFT_RST字段检查：CTRL.SOFT_RST写1触发协议上下文清零并恢复默认lane模式（1-bit）；\n'
     '4、事务期间lane切换检查：pcs_n_i=0(事务执行期间)lane_mode_i变化时，移位宽度bpc立即改变，帧数据错位，模块不检测此违规，可能误触发STS_BAD_OPCODE(0x02)或STS_FRAME_ERR(0x01)；\n'
     '5、空闲态lane切换检查：pcs_n_i=1(空闲态)切换lane_mode_i后，新事务使用更新后的lane模式，帧数据正确。',
     ['TP_025', 'TP_026', 'TP_027']),

    ('CHK_010', 'status_polling_checker',
     '对于中断与状态查询，检查MVP无中断输出和轮询机制：\n'
     '1、无中断输出检查：MVP版本不实现独立中断输出，无IRQ信号拉高；\n'
     '2、STATUS寄存器检查：错误与完成状态通过STATUS寄存器查询，busy指示正确；\n'
     '3、LAST_ERR寄存器检查：最近错误类型通过LAST_ERR寄存器查询，值与状态码对应；\n'
     '4、轮询覆盖检查：连续发送多条错误命令时，每次错误状态通过响应帧8bit状态码直接返回给ATE，前一条错误信息被新命令覆盖。',
     ['TP_028', 'TP_029']),

    ('CHK_011', 'error_priority_checker',
     '对于前置错误优先级，检查固定优先级链和多错误同时发生时的行为：\n'
     '1、优先级链检查：前置检查按固定优先级返回错误——STS_FRAME_ERR(0x01) > STS_BAD_OPCODE(0x02) > STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08) > STS_BAD_REG(0x10) > STS_ALIGN_ERR(0x20)；\n'
     '2、多错误场景检查：同时满足多个前置错误条件时，仅报告最高优先级错误，仅返回一个状态码；\n'
     '3、前置收敛检查：任何前置错误均在发起CSR/AHB访问前收敛，不产生副作用。',
     ['TP_030', 'TP_032', 'TP_033', 'TP_038']),

    ('CHK_012', 'ahb_align_checker',
     '对于AHB地址对齐，检查addr[1:0]!=2\'b00时的前置拒绝行为：\n'
     '1、对齐检测检查：AHB_WR32(0x20)或AHB_RD32(0x21)命令的addr[1:0]!=2\'b00时，前置检查拒绝访问；\n'
     '2、状态码检查：返回STS_ALIGN_ERR(0x20)；\n'
     '3、不发起AHB访问检查：htrans_o保持IDLE(2\'b00)，不发起AHB总线事务。',
     ['TP_035']),

    ('CHK_013', 'ahb_error_checker',
     '对于AHB执行期错误，检查hresp_i错误和超时两种情况：\n'
     '1、hresp_i错误检查：AHB从设备返回hresp_i=1时，STATE_WAIT检测到后转STATE_ERR，返回STS_AHB_ERR(0x40)；\n'
     '2、超时检查：9-bit计数器在STATE_WAIT每拍+1，达BUS_TIMEOUT_CYCLES-1(默认255)触发STATE_ERR，返回STS_AHB_ERR(0x40)；\n'
     '3、超时计数器复位检查：STATE_REQ时计数器清零；\n'
     '4、AHB错误与前置错误互斥检查：前置检查通过后才可能发生AHB错误，STATE_ERR下一拍自动转STATE_IDLE，AHB输出恢复htrans=IDLE、haddr=0。',
     ['TP_036', 'TP_037', 'TP_039']),

    ('CHK_014', 'lowpower_checker',
     '对于低功耗，检查空闲态下寄存器/计数器不更新和AHB输出保持IDLE：\n'
     '1、移位寄存器检查：空闲态(pcs_n_i=1)下接收/发送移位寄存器不更新、不翻转；\n'
     '2、AHB输出检查：test_mode_i=0或无有效任务时，htrans_o保持IDLE(2\'b00)，无AHB总线翻转；\n'
     '3、超时计数器检查：仅在STATE_WAIT期间超时计数器递增，STATE_REQ时清零，IDLE态不工作。',
     ['TP_040', 'TP_041', 'TP_042']),

    ('CHK_015', 'latency_checker',
     '对于性能时延，检查端到端延时和超时阈值：\n'
     '1、4-bit AHB_RD32时延检查：请求接收10cyc + 译码1~2cyc + AHB返回1~N cyc + turnaround 1cyc + 响应发送10cyc ≈ 23~24 cycles最小延时；\n'
     '2、4-bit AHB_WR32时延检查：请求接收18cyc + 执行2cyc + turnaround 1cyc + 响应发送2cyc ≈ 23 cycles最小延时；\n'
     '3、1-bit AHB_RD32时延检查：请求接收40cyc + 译码1~2cyc + AHB返回1~N cyc + turnaround 1cyc + 响应发送40cyc ≈ 83~84 cycles最小延时；\n'
     '4、1-bit WR_CSR时延检查：请求接收48cyc + 执行~6cyc + turnaround 1cyc + 响应发送8cyc ≈ 63 cycles最小延时；\n'
     '5、超时阈值检查：9-bit计数器在STATE_WAIT递增，达BUS_TIMEOUT_CYCLES-1(默认255)触发STATE_ERR，超时阈值为256周期。',
     ['TP_043', 'TP_044', 'TP_045', 'TP_046', 'TP_047']),

    ('CHK_016', 'dfx_checker',
     '对于DFX可观测性，检查内部调试点信号是否可观测：\n'
     '1、FSM状态可观测检查：front_state和back_state可被外部观测；\n'
     '2、协议字段可观测检查：opcode、addr、wdata、rdata、status_code可被外部读取；\n'
     '3、计数器可观测检查：rx_count和tx_count可被外部读取；\n'
     '4、配置可观测检查：lane_mode信号可被外部观测。',
     ['TP_048']),

    ('CHK_017', 'ahb_proto_checker',
     '对于AHB-Lite协议，检查2-phase流水时序、固定属性和错误恢复：\n'
     '1、2-phase写时序检查：T1(STATE_REQ)驱动haddr_o/hwrite_o=1/htrans_o=NONSEQ(2\'b10)；T2(STATE_WAIT)htrans_o回到IDLE(2\'b00)，驱动hwdata_o；haddr_o与hwdata_o错开1拍；\n'
     '2、2-phase读时序检查：T1(STATE_REQ)驱动haddr_o/htrans_o=NONSEQ(2\'b10)；T2(STATE_WAIT)htrans_o=IDLE(2\'b00)，hready_i=1时采样hrdata_i；\n'
     '3、固定属性检查：hsize_o固定输出3\'b010(WORD)，hburst_o固定输出3\'b000(SINGLE)；\n'
     '4、htrans_o状态检查：仅在STATE_REQ(地址相)驱动NONSEQ(2\'b10)持续1周期，其余时刻均为IDLE(2\'b00)；\n'
     '5、错误恢复检查：STATE_ERR下一拍自动转STATE_IDLE，AHB输出恢复htrans=IDLE、haddr=0，模块可立即接受新请求；\n'
     '6、CSR访问方式检查：模块CSR不进入SoC AHB memory map，仅通过协议命令WR_CSR(0x10)/RD_CSR(0x11)访问；\n'
     '7、AHB地址空间检查：AHB Master采用32bit地址空间和word(32-bit)访问粒度，haddr_o必须4-byte对齐。',
     ['TP_049', 'TP_050', 'TP_051', 'TP_052', 'TP_053', 'TP_054', 'TP_055']),
]

# ============================================================
# Testcase definitions: (tc_id, tc_name, tc_description, [tp_ids])
# ============================================================
TESTCASES = [
    ('TC_001', 'aplc_clk_freq_test',
     'TC场景：验证clk_i时钟频率和单时钟域工作\n'
     '配置条件：\n'
     '1.配置clk_i为100MHz连续时钟；\n'
     '2.配置lane_mode_i=2\'b01(4-bit模式)，test_mode_i=1，en_i=1。\n'
     '输入激励：\n'
     '1.驱动clk_i持续运行，依次发送WR_CSR(0x10)/RD_CSR(0x11)/AHB_WR32(0x20)/AHB_RD32(0x21)命令帧；\n'
     '2.使用频率计测量clk_i实际频率。\n'
     '期望结果：\n'
     '1.所有内部逻辑在clk_i上升沿正确同步，协议接收、状态机控制和AHB-Lite主接口同域工作，无跨时钟域问题；\n'
     '2.模块在100MHz目标频率下正常工作，所有时序满足约束。\n'
     'coverage check点：\n'
     '直接用例覆盖，不收功能覆盖率',
     ['TP_001', 'TP_002']),

    ('TC_002', 'aplc_reset_test',
     'TC场景：验证rst_n_i异步复位与同步释放及复位后状态\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，lane_mode_i=2\'b01，test_mode_i=1，en_i=1；\n'
     '2.模块处于正常工作状态（已发送若干命令）。\n'
     '输入激励：\n'
     '1.在任意工作状态下拉低rst_n_i触发异步复位；\n'
     '2.释放rst_n_i（同步释放）；\n'
     '3.检查front_state、back_state及所有输出端口。\n'
     '期望结果：\n'
     '1.rst_n_i下降沿立即触发复位；释放时在clk_i上升沿同步退出复位；\n'
     '2.复位后front_state=IDLE(3\'d0)，back_state=S_IDLE(3\'d0)；\n'
     '3.pdo_oe_o=0，htrans_o=2\'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0，pdo_o=4\'b0；LANE_MODE恢复默认1-bit模式。\n'
     'coverage check点：\n'
     '直接用例覆盖，不收功能覆盖率',
     ['TP_003', 'TP_004', 'TP_005']),

    ('TC_003', 'aplc_csr_write_test',
     'TC场景：验证WR_CSR(0x10)命令写CSR寄存器功能\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.模块解复位，进入正常工作状态。\n'
     '输入激励：\n'
     '1.依次发送WR_CSR(0x10)命令写VERSION(0x00)、CTRL(0x04)、STATUS(0x08)、LAST_ERR(0x0C)，写入随机数据；\n'
     '2.观测csr_wr_en_o、csr_addr_o、csr_wdata_o信号。\n'
     '期望结果：\n'
     '1.csr_wr_en_o脉冲持续1周期；同周期csr_addr_o和csr_wdata_o有效；\n'
     '2.外部CSR File采样写入数据；写操作返回STS_OK(0x00)。\n'
     'coverage check点：\n'
     '对CSR写地址(0x00/0x04/0x08/0x0C)和写数据位宽收集功能覆盖率',
     ['TP_006']),

    ('TC_004', 'aplc_csr_read_test',
     'TC场景：验证RD_CSR(0x11)命令读CSR寄存器功能\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.先通过WR_CSR(0x10)写入已知数据到VERSION(0x00)、CTRL(0x04)。\n'
     '输入激励：\n'
     '1.发送RD_CSR(0x11)命令读VERSION(0x00)、CTRL(0x04)；\n'
     '2.观测csr_rd_en_o、csr_rdata_i和响应帧RDATA。\n'
     '期望结果：\n'
     '1.csr_rd_en_o脉冲持续1周期；下一周期外部CSR File将读数据稳定在csr_rdata_i上；\n'
     '2.模块正确采样csr_rdata_i；读操作返回STS_OK(0x00)+RDATA[31:0]，RDATA与写入值一致。\n'
     'coverage check点：\n'
     '对CSR读地址和1周期读延迟时序收集功能覆盖率',
     ['TP_007']),

    ('TC_005', 'aplc_csr_bad_addr_test',
     'TC场景：验证非法CSR地址(>=0x40)的前置拒绝\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送WR_CSR(0x10)命令，reg_addr随机取0x40、0x5F、0xFF等>=0x40的地址；\n'
     '2.发送RD_CSR(0x11)命令，reg_addr随机取0x40、0x7F、0xFF等>=0x40的地址；\n'
     '3.观测csr_wr_en_o、csr_rd_en_o信号。\n'
     '期望结果：\n'
     '1.所有非法地址命令返回STS_BAD_REG(0x10)；\n'
     '2.csr_wr_en_o=0，csr_rd_en_o=0，不发起CSR访问。\n'
     'coverage check点：\n'
     '对reg_addr>=0x40的地址边界值收集功能覆盖率',
     ['TP_008']),

    ('TC_006', 'aplc_mode_gate_test',
     'TC场景：验证test_mode_i和en_i前置门控行为\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.test_mode_i=0, en_i=1时，发送RD_CSR(0x11)有效命令帧；\n'
     '2.test_mode_i=1, en_i=0时，发送WR_CSR(0x10)有效命令帧；\n'
     '3.test_mode_i=1, en_i=1时，发送WR_CSR(0x10)/RD_CSR(0x11)/AHB_WR32(0x20)/AHB_RD32(0x21)四类命令。\n'
     '期望结果：\n'
     '1.test_mode_i=0时返回STS_NOT_IN_TEST(0x04)，不发起CSR/AHB访问；\n'
     '2.en_i=0时返回STS_DISABLED(0x08)，不发起CSR/AHB访问；\n'
     '3.test_mode_i=1且en_i=1时，前置检查通过，正常执行命令并返回正确状态码和数据。\n'
     'coverage check点：\n'
     '对test_mode_i和en_i的0/1组合收集功能覆盖率',
     ['TP_009', 'TP_010', 'TP_011']),

    ('TC_007', 'aplc_lane_mode_test',
     'TC场景：验证1-bit和4-bit通道模式切换\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1。\n'
     '输入激励：\n'
     '1.lane_mode_i=2\'b00(1-bit模式)时，发送WR_CSR(0x10)和AHB_RD32(0x21)命令；\n'
     '2.lane_mode_i=2\'b01(4-bit模式)时，发送WR_CSR(0x10)和AHB_RD32(0x21)命令；\n'
     '3.对比两种模式的帧接收周期。\n'
     '期望结果：\n'
     '1.1-bit模式每拍收发1bit(pdi_i[0])，帧接收周期为帧长bit数；\n'
     '2.4-bit模式每拍收发4bit(pdi_i[3:0])，帧接收周期为帧长/4；\n'
     '3.两种模式命令执行结果一致。\n'
     'coverage check点：\n'
     '对lane_mode_i的2\'b00和2\'b01配置收集功能覆盖率',
     ['TP_012', 'TP_013']),

    ('TC_008', 'aplc_frame_recv_test',
     'TC场景：验证四类命令帧的完整接收和响应格式\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送WR_CSR(0x10)命令帧(48bit: opcode8+reg_addr8+wdata32)；\n'
     '2.发送RD_CSR(0x11)命令帧(16bit: opcode8+reg_addr8)；\n'
     '3.发送AHB_WR32(0x20)命令帧(72bit: opcode8+addr32+wdata32)；\n'
     '4.发送AHB_RD32(0x21)命令帧(40bit: opcode8+addr32)；\n'
     '5.在1-bit模式下重复上述命令。\n'
     '期望结果：\n'
     '1.每类命令帧接收完成后产生frame_valid；\n'
     '2.WR_CSR/AHB_WR32响应8bit状态码；RD_CSR/AHB_RD32响应40bit(8bit状态+32bit读数据)；\n'
     '3.pcs_n_i=1时空闲；pcs_n_i=0时开启帧接收；pcs_n_i拉高时结束事务；\n'
     '4.1-bit模式仅pdi_i[0]有效；4-bit模式pdi_i[3:0]均有效；MSB-first顺序传输；\n'
     '5.响应阶段pdo_oe_o=1驱动pdo_o；非发送阶段pdo_oe_o=0。\n'
     'coverage check点：\n'
     '对四类opcode(0x10/0x11/0x20/0x21)和两种lane模式收集功能覆盖率',
     ['TP_014', 'TP_015', 'TP_016', 'TP_017', 'TP_018', 'TP_019', 'TP_020']),

    ('TC_009', 'aplc_frame_abort_test',
     'TC场景：验证帧中止(frame_abort)行为\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送WR_CSR(0x10)帧，在rx_count<expected_rx_bits时提前将pcs_n_i拉高；\n'
     '2.发送AHB_WR32(0x20)帧，仅发送部分opcode后提前将pcs_n_i拉高；\n'
     '3.在1-bit模式下重复帧中止场景。\n'
     '期望结果：\n'
     '1.产生frame_abort，返回STS_FRAME_ERR(0x01)；\n'
     '2.不发起CSR/AHB访问。\n'
     'coverage check点：\n'
     '对帧中止时的rx_count值范围收集功能覆盖率',
     ['TP_021']),

    ('TC_010', 'aplc_turnaround_test',
     'TC场景：验证请求-响应之间的turnaround周期\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送WR_CSR(0x10)命令，观测请求阶段结束到响应阶段开始的时序；\n'
     '2.发送RD_CSR(0x11)命令，观测turnaround周期；\n'
     '3.发送AHB_WR32(0x20)/AHB_RD32(0x21)命令，观测turnaround周期。\n'
     '期望结果：\n'
     '1.请求阶段与响应阶段之间固定插入1个clk_i周期turnaround；\n'
     '2.turnaround期间pdo_oe_o=0；TX阶段pdo_oe_o=1。\n'
     'coverage check点：\n'
     '直接用例覆盖，不收功能覆盖率',
     ['TP_022']),

    ('TC_011', 'aplc_opcode_valid_test',
     'TC场景：验证合法opcode解析和帧长度确定\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.依次发送opcode为0x10(WR_CSR)、0x11(RD_CSR)、0x20(AHB_WR32)、0x21(AHB_RD32)的完整命令帧；\n'
     '2.观测前端FSM状态和expected_rx_bits值。\n'
     '期望结果：\n'
     '1.前端收满8bit后锁存opcode；\n'
     '2.0x10对应48bit、0x11对应16bit、0x20对应72bit、0x21对应40bit；\n'
     '3.正确发起对应类型任务。\n'
     'coverage check点：\n'
     '对四类合法opcode收集功能覆盖率',
     ['TP_023']),

    ('TC_012', 'aplc_opcode_invalid_test',
     'TC场景：验证非法opcode检测\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送opcode为0x00、0xFF、0x30、0x12等不在{0x10,0x11,0x20,0x21}中的完整帧；\n'
     '2.发送opcode为0x10/0x11/0x20/0x21的部分位翻转值。\n'
     '期望结果：\n'
     '1.前置检查检测到非法opcode，返回STS_BAD_OPCODE(0x02)；\n'
     '2.不发起CSR/AHB访问。\n'
     'coverage check点：\n'
     '对非法opcode的取值范围收集功能覆盖率',
     ['TP_024', 'TP_031']),

    ('TC_013', 'aplc_ctrl_config_test',
     'TC场景：验证CTRL寄存器EN/LANE_MODE/SOFT_RST配置和lane切换行为\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1。\n'
     '输入激励：\n'
     '1.通过WR_CSR(0x10)写CTRL(0x04)，配置EN=1，LANE_MODE=2\'b00(1-bit)；\n'
     '2.通过WR_CSR(0x10)写CTRL(0x04)，配置EN=1，LANE_MODE=2\'b01(4-bit)；\n'
     '3.通过WR_CSR(0x10)写CTRL(0x04)，配置SOFT_RST=1，观测协议上下文清零；\n'
     '4.pcs_n_i=0(事务期间)改变lane_mode_i，观察帧数据错位；\n'
     '5.pcs_n_i=1(空闲态)改变lane_mode_i，然后发起新事务。\n'
     '期望结果：\n'
     '1.LANE_MODE=2\'b00对应1-bit模式，2\'b01对应4-bit模式；\n'
     '2.SOFT_RST写1触发协议上下文清零并恢复默认lane模式；\n'
     '3.事务期间切换lane_mode_i导致移位宽度变化、帧数据错位；\n'
     '4.空闲态切换后新事务使用更新后的lane模式，帧数据正确。\n'
     'coverage check点：\n'
     '对CTRL.EN/LANE_MODE/SOFT_RST字段的配置组合收集功能覆盖率',
     ['TP_025', 'TP_026', 'TP_027']),

    ('TC_014', 'aplc_status_polling_test',
     'TC场景：验证MVP无中断输出和STATUS/LAST_ERR轮询机制\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.触发各类错误事件（帧中止、非法opcode、AHB错误等）；\n'
     '2.通过RD_CSR(0x11)读STATUS(0x08)和LAST_ERR(0x0C)；\n'
     '3.连续发送多条错误命令，每次读取STATUS和LAST_ERR。\n'
     '期望结果：\n'
     '1.无IRQ信号拉高，MVP不实现独立中断输出；\n'
     '2.错误信息通过STATUS和LAST_ERR寄存器查询；\n'
     '3.每次错误状态通过响应帧8bit状态码直接返回，前一条错误被新命令覆盖。\n'
     'coverage check点：\n'
     '对STATUS和LAST_ERR寄存器值的变化收集功能覆盖率',
     ['TP_028', 'TP_029']),

    ('TC_015', 'aplc_error_priority_test',
     'TC场景：验证前置错误优先级链和单错误返回\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.4-bit模式下发送WR_CSR帧，pcs_n_i在rx_count<expected_rx_bits时提前拉高(opcode已锁存)→触发STS_FRAME_ERR(0x01)；\n'
     '2.test_mode_i=0, en_i=1时发送有效命令→触发STS_NOT_IN_TEST(0x04)；\n'
     '3.test_mode_i=1, en_i=0时发送有效命令→触发STS_DISABLED(0x08)；\n'
     '4.发送WR_CSR/RD_CSR命令，reg_addr>=0x40→触发STS_BAD_REG(0x10)；\n'
     '5.发送AHB_WR32/AHB_RD32命令，addr[1:0]!=2\'b00→触发STS_ALIGN_ERR(0x20)。\n'
     '期望结果：\n'
     '1.各前置错误返回对应状态码，不发起CSR/AHB访问；\n'
     '2.优先级链正确：FRAME_ERR(0x01)>BAD_OPCODE(0x02)>NOT_IN_TEST(0x04)>DISABLED(0x08)>BAD_REG(0x10)>ALIGN_ERR(0x20)。\n'
     'coverage check点：\n'
     '对前置错误的6种类型收集功能覆盖率',
     ['TP_030', 'TP_032', 'TP_033', 'TP_034', 'TP_035']),

    ('TC_016', 'aplc_multi_error_test',
     'TC场景：验证多错误同时发生时仅返回最高优先级错误\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.test_mode_i=0, en_i=0时发送非对齐地址的AHB命令（同时满足NOT_IN_TEST+DISABLED+ALIGN_ERR）；\n'
     '2.test_mode_i=0, en_i=1时发送reg_addr>=0x40的RD_CSR命令（同时满足NOT_IN_TEST+BAD_REG）；\n'
     '3.帧中止+非法opcode组合（发送部分帧后提前拉高pcs_n_i，且opcode非法）。\n'
     '期望结果：\n'
     '1.按固定优先级链仅报告最高优先级错误，仅返回一个状态码；\n'
     '2.任何前置错误均在发起CSR/AHB访问前收敛，不产生副作用。\n'
     'coverage check点：\n'
     '对多错误组合的优先级仲裁结果收集功能覆盖率',
     ['TP_038']),

    ('TC_017', 'aplc_ahb_error_test',
     'TC场景：验证AHB执行期hresp_i=1错误处理\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.AHB从设备配置为返回hresp_i=1。\n'
     '输入激励：\n'
     '1.发送AHB_WR32(0x20)命令，从设备返回hresp_i=1；\n'
     '2.发送AHB_RD32(0x21)命令，从设备返回hresp_i=1；\n'
     '3.观测FSM状态恢复。\n'
     '期望结果：\n'
     '1.STATE_WAIT检测到hresp_i=1后转STATE_ERR；返回STS_AHB_ERR(0x40)；\n'
     '2.前置错误与AHB错误互斥，前置检查通过后才可能发生AHB错误；\n'
     '3.STATE_ERR下一拍自动转STATE_IDLE，AHB输出恢复htrans=IDLE、haddr=0。\n'
     'coverage check点：\n'
     '对AHB写/读操作返回hresp_i=1的场景收集功能覆盖率',
     ['TP_036', 'TP_039']),

    ('TC_018', 'aplc_ahb_timeout_test',
     'TC场景：验证AHB超时256周期检测\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.AHB从设备配置为持续返回hready_i=0超过256周期。\n'
     '输入激励：\n'
     '1.发送AHB_WR32(0x20)命令，hready_i持续为0超过256周期；\n'
     '2.发送AHB_RD32(0x21)命令，hready_i持续为0超过256周期；\n'
     '3.观测9-bit超时计数器行为。\n'
     '期望结果：\n'
     '1.9-bit计数器在STATE_WAIT递增，达BUS_TIMEOUT_CYCLES-1(默认255)触发STATE_ERR；\n'
     '2.返回STS_AHB_ERR(0x40)；\n'
     '3.超时阈值为256周期。\n'
     'coverage check点：\n'
     '对AHB超时计数器边界值(254/255/256)收集功能覆盖率',
     ['TP_037', 'TP_047']),

    ('TC_019', 'aplc_lowpower_test',
     'TC场景：验证空闲态低功耗行为\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.模块空闲态(pcs_n_i=1)下，观测接收/发送移位寄存器和超时计数器；\n'
     '2.test_mode_i=0或无有效任务时，观测AHB输出端口；\n'
     '3.模块处于STATE_WAIT(AHB等待态)时，观测超时计数器。\n'
     '期望结果：\n'
     '1.空闲态下接收/发送移位寄存器不更新、不翻转；\n'
     '2.htrans_o保持IDLE(2\'b00)，无AHB总线翻转；\n'
     '3.仅在STATE_WAIT期间超时计数器递增，STATE_REQ时清零，IDLE态不工作。\n'
     'coverage check点：\n'
     '直接用例覆盖，不收功能覆盖率',
     ['TP_040', 'TP_041', 'TP_042']),

    ('TC_020', 'aplc_latency_test',
     'TC场景：验证端到端时延测量\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1；\n'
     '2.AHB从设备配置为hready_i=1(零等待)。\n'
     '输入激励：\n'
     '1.4-bit模式下发送AHB_RD32(0x21)命令，测量端到端延时；\n'
     '2.4-bit模式下发送AHB_WR32(0x20)命令，测量端到端延时；\n'
     '3.1-bit模式下发送AHB_RD32(0x21)命令，测量端到端延时；\n'
     '4.1-bit模式下发送WR_CSR(0x10)命令，测量端到端延时。\n'
     '期望结果：\n'
     '1.4-bit AHB_RD32: 请求10cyc+译码1~2cyc+AHB 1~N cyc+turnaround 1cyc+响应10cyc ≈ 23~24 cycles最小延时；\n'
     '2.4-bit AHB_WR32: 请求18cyc+执行2cyc+turnaround 1cyc+响应2cyc ≈ 23 cycles最小延时；\n'
     '3.1-bit AHB_RD32: 请求40cyc+译码1~2cyc+AHB 1~N cyc+turnaround 1cyc+响应40cyc ≈ 83~84 cycles最小延时；\n'
     '4.1-bit WR_CSR: 请求48cyc+执行~6cyc+turnaround 1cyc+响应8cyc ≈ 63 cycles最小延时。\n'
     'coverage check点：\n'
     '对1-bit/4-bit模式与四类opcode的时延组合收集功能覆盖率',
     ['TP_043', 'TP_044', 'TP_045', 'TP_046']),

    ('TC_021', 'aplc_dfx_test',
     'TC场景：验证DFX内部调试点可观测性\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.仿真/调试环境。\n'
     '输入激励：\n'
     '1.运行各类命令（WR_CSR/RD_CSR/AHB_WR32/AHB_RD32），观测内部调试点；\n'
     '2.触发各类错误事件，观测错误状态调试点。\n'
     '期望结果：\n'
     '1.可观测front_state、back_state、opcode、addr、wdata、rdata、status_code、rx_count、tx_count、lane_mode等信号；\n'
     '2.便于波形定位和故障复现。\n'
     'coverage check点：\n'
     '直接用例覆盖，不收功能覆盖率',
     ['TP_048']),

    ('TC_022', 'aplc_memmap_test',
     'TC场景：验证CSR不进入AHB memory map和AHB地址空间约束\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)；\n'
     '2.SoC集成环境。\n'
     '输入激励：\n'
     '1.检查模块CSR是否出现在AHB memory map中；\n'
     '2.发起AHB_WR32(0x20)/AHB_RD32(0x21)命令访问不同地址。\n'
     '期望结果：\n'
     '1.模块CSR不进入SoC AHB memory map，仅通过协议命令WR_CSR(0x10)/RD_CSR(0x11)访问；\n'
     '2.AHB Master采用32bit地址空间和word(32-bit)访问粒度，haddr_o必须4-byte对齐。\n'
     'coverage check点：\n'
     '对AHB访问地址范围和4-byte对齐约束收集功能覆盖率',
     ['TP_049', 'TP_050']),

    ('TC_023', 'aplc_ahb_2phase_test',
     'TC场景：验证AHB-Lite 2-phase流水时序、固定属性和错误恢复\n'
     '配置条件：\n'
     '1.配置clk_i=100MHz，test_mode_i=1，en_i=1，lane_mode_i=2\'b01(4-bit模式)。\n'
     '输入激励：\n'
     '1.发送AHB_WR32(0x20)命令，观测AHB 2-phase写流水时序（haddr_o/hwrite_o/htrans_o/hwdata_o）；\n'
     '2.发送AHB_RD32(0x21)命令，观测AHB 2-phase读流水时序（haddr_o/htrans_o/hrdata_i/hready_i）；\n'
     '3.检查hsize_o和hburst_o输出；\n'
     '4.观测htrans_o在不同FSM状态下的值；\n'
     '5.触发AHB错误(STATE_ERR)后观测FSM状态恢复。\n'
     '期望结果：\n'
     '1.T1(STATE_REQ)驱动haddr_o/hwrite_o=1/htrans_o=NONSEQ(2\'b10)；T2(STATE_WAIT)htrans_o回到IDLE(2\'b00)，写驱动hwdata_o，读在hready_i=1时采样hrdata_i；haddr与hwdata错开1拍；\n'
     '2.hsize_o固定输出3\'b010(WORD)，hburst_o固定输出3\'b000(SINGLE)；\n'
     '3.htrans_o仅在STATE_REQ驱动NONSEQ(2\'b10)持续1周期，其余时刻均为IDLE(2\'b00)；\n'
     '4.STATE_ERR下一拍自动转STATE_IDLE，AHB输出恢复htrans=IDLE、haddr=0。\n'
     'coverage check点：\n'
     '对AHB写/读2-phase流水时序和htrans_o状态收集功能覆盖率',
     ['TP_051', 'TP_052', 'TP_053', 'TP_054', 'TP_055']),
]

# ============================================================
# TP-to-Checker/Testcase mapping
# ============================================================
TP_CHECKER_MAP = {}
TP_TESTCASE_MAP = {}

for chk_id, chk_name, chk_desc, tp_ids in CHECKERS:
    for tp_id in tp_ids:
        if tp_id in TP_CHECKER_MAP:
            TP_CHECKER_MAP[tp_id] = TP_CHECKER_MAP[tp_id] + ',' + chk_id
        else:
            TP_CHECKER_MAP[tp_id] = chk_id

for tc_id, tc_name, tc_desc, tp_ids in TESTCASES:
    for tp_id in tp_ids:
        if tp_id in TP_TESTCASE_MAP:
            TP_TESTCASE_MAP[tp_id] = TP_TESTCASE_MAP[tp_id] + ',' + tc_id
        else:
            TP_TESTCASE_MAP[tp_id] = tc_id


def apply_cell_format(src_cell, dst_cell):
    """Copy format from source cell to destination cell."""
    dst_cell.font = copy(src_cell.font)
    dst_cell.alignment = copy(src_cell.alignment)
    dst_cell.border = copy(src_cell.border)
    dst_cell.fill = copy(src_cell.fill)
    dst_cell.number_format = src_cell.number_format


def main():
    # Copy template to output
    shutil.copy2(TEMPLATE, OUTPUT)
    print(f'Copied {TEMPLATE} -> {OUTPUT}')

    # Load workbook
    wb = openpyxl.load_workbook(OUTPUT)

    # ---- Add Checkers ----
    print('Adding Checkers...')
    for chk_id, chk_name, chk_desc, _ in CHECKERS:
        add_checker_to_rtm(wb, chk_id, chk_name, chk_desc)
        print(f'  {chk_id}: {chk_name}')

    # ---- Add Testcases ----
    print('Adding Testcases...')
    for tc_id, tc_name, tc_desc, _ in TESTCASES:
        add_testcase_to_rtm(wb, tc_id, tc_name, tc_desc)
        print(f'  {tc_id}: {tc_name}')

    # ---- Link TPs ----
    print('Linking TPs...')
    all_tps = sorted(set(TP_CHECKER_MAP.keys()) | set(TP_TESTCASE_MAP.keys()),
                     key=lambda x: int(x.split('_')[1]))
    for tp_id in all_tps:
        checker_id = TP_CHECKER_MAP.get(tp_id, '')
        testcase_id = TP_TESTCASE_MAP.get(tp_id, '')
        link_tp_to_checker_testcase(wb, tp_id, checker_id, testcase_id)
        print(f'  {tp_id} -> CHK: {checker_id}, TC: {testcase_id}')

    # ---- Apply formatting to Checker List and DV Testcase List ----
    print('Applying formatting...')

    thin = Side(style='thin')
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
    font_cn = Font(name='宋体', size=11)
    align_wrap = Alignment(wrap_text=True, vertical='center')

    for sheet_name in ['Checker List', 'DV Testcase List']:
        ws = wb[sheet_name]
        for row in range(3, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                if cell.value is not None:
                    cell.font = font_cn
                    cell.border = border_all
                    cell.alignment = align_wrap

    # ---- Save ----
    save_rtm(wb, OUTPUT)
    print(f'Saved to {OUTPUT}')

    # ---- Verification ----
    print('\n=== Verification ===')
    from rtm_utils import read_rtm_structure
    result = read_rtm_structure(OUTPUT)
    print(f'Checkers: {len(result["checkers"])}')
    print(f'Testcases: {len(result["testcases"])}')
    print(f'FL-TP entries: {len(result["fl_tp"])}')

    uncovered_tps = [tp['tp_id'] for tp in result['fl_tp']
                     if not tp['checker_id'] or not tp['testcase_id']]
    if uncovered_tps:
        print(f'WARNING: Uncovered TPs: {uncovered_tps}')
    else:
        print('All TPs covered by Checker and Testcase!')


if __name__ == '__main__':
    main()
