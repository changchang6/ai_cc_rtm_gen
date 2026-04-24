#!/usr/bin/env python3
"""
RTM Generator Script
Generate Checkers and Testcases for APLC-Lite MVP version
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, Border, Side
import shutil

# ============================================================
# Checker Definitions (14 Checkers)
# ============================================================

CHECKERS = [
    {
        'chk_id': 'CHK_001',
        'chk_name': 'clk_reset_checker',
        'chk_description': '''检查时钟clk_i频率稳定性与rst_ni异步复位同步释放后模块状态正确性：
1. clk_i目标频率100MHz，连续运行1000+周期频率偏差<3%，无时钟毛刺或异常跳变；
2. rst_ni异步复位（下降沿触发）：所有触发器立即清零，FSM强制进入IDLE/S_IDLE/AXI_IDLE态；
3. rst_ni同步释放（与clk_i上升沿对齐）：释放后首个上升沿开始正常工作，无亚稳态；
4. 复位后输出deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0，pdo_o[15:0]=16'b0；
5. 复位后RX/TX上下文清空：协议状态清零，错误状态清零，CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)。'''
    },
    {
        'chk_id': 'CHK_002',
        'chk_name': 'csr_access_checker',
        'chk_description': '''检查CSR接口读写时序正确性与地址范围合法性：
1. CSR写操作：csr_wr_en_o为单周期脉冲，同一周期内csr_addr_o[7:0]与csr_wdata_o[31:0]有效，外部CSR File在该上升沿采样完成写入；
2. CSR读操作：csr_rd_en_o为单周期脉冲，外部CSR File在下一周期将读数据稳定在csr_rdata_i[31:0]，模块在该周期采样（1 cycle读延迟）；
3. CSR有效地址范围0x00~0x3F：reg_addr>=0x40的访问在前置检查阶段即被拒绝，返回STS_BAD_REG(0x10)，不产生csr_rd_en_o/csr_wr_en_o脉冲；
4. 寄存器属性正确：VERSION(0x00)为RO只读，CTRL(0x04)为RW读写，STATUS(0x08)为RO只读，LAST_ERR(0x0C)为RO只读，软件通过轮询STATUS获取状态。'''
    },
    {
        'chk_id': 'CHK_003',
        'chk_name': 'test_mode_en_checker',
        'chk_description': '''检查test_mode_i与en_i信号对命令的拒绝行为与错误优先级正确性：
1. test_mode_i=0时：所有命令被前置检查拒绝，返回STS_NOT_IN_TEST(0x04)，不发起任何CSR/AHB访问（csr_wr_en_o=0，csr_rd_en_o=0，htrans_o=IDLE）；
2. en_i=0时：所有命令被前置检查拒绝，返回STS_DISABLED(0x08)，不发起任何CSR/AHB访问；
3. 错误优先级：当test_mode_i=0且en_i=0同时成立时，返回STS_NOT_IN_TEST(0x04)（优先级高于STS_DISABLED）；
4. 检查时刻：test_mode_i与en_i在frame_valid时刻被前置检查器组合采样，帧接收期间不检查。'''
    },
    {
        'chk_id': 'CHK_004',
        'chk_name': 'lane_mode_checker',
        'chk_description': '''检查lane_mode_i对应的通道宽度与数据信号使用正确性（MVP仅支持1-bit与4-bit）：
1. lane_mode_i=2'b00(1-bit模式)：仅使用pdi_i[0]/pdo_o[0]，pdi_i[15:1]忽略，pdo_o[15:1]驱动为0；RD_CSR帧16bit需16个周期接收；
2. lane_mode_i=2'b01(4-bit模式)：使用pdi_i[3:0]/pdo_o[3:0]，按高nibble优先发送；RD_CSR帧16bit需4个周期接收；
3. lane_mode_i在接收器(SLC_CAXIS)和发送器(SLC_SAXIS)中被连续组合采样，用于计算每拍移位宽度bpc(bits per clock)；
4. 事务边界约束：lane_mode_i在pcs_n_i=0期间必须保持稳定，事务中途切换导致移位宽度变化、帧数据错位，可能触发STS_BAD_OPCODE或STS_FRAME_ERR。'''
    },
    {
        'chk_id': 'CHK_005',
        'chk_name': 'frame_protocol_checker',
        'chk_description': '''检查pcs_n_i帧边界协议与pdo_oe_o方向控制正确性：
1. 帧边界定义：pcs_n_i=1为空闲态，pcs_n_i下降沿开启一次事务（帧接收→执行→响应发送），pcs_n_i上升沿结束事务；
2. 请求阶段：pcs_n_i=0期间ATE驱动pdi_i输入数据，模块接收移位锁存；
3. Turnaround：请求与响应之间固定插入1个clk_i周期，pdo_oe_o=0保持高阻态，避免总线冲突；
4. 响应阶段：pdo_oe_o=1表示模块驱动pdo_o输出，响应帧按MSB-first顺序串行发送；
5. 帧中止行为：若pcs_n_i在接收中途提前拉高且opcode已锁存，产生frame_abort，返回STS_FRAME_ERR(0x01)。'''
    },
    {
        'chk_id': 'CHK_006',
        'chk_name': 'frame_length_checker',
        'chk_description': '''检查各类命令帧长度与响应帧长度符合协议规范：
1. 命令帧长度（MSB-first）：
   - WR_CSR(opcode=0x10)：48-bit = opcode(8) + reg_addr(8) + wdata(32)
   - RD_CSR(opcode=0x11)：16-bit = opcode(8) + reg_addr(8)
   - AHB_WR32(opcode=0x20)：72-bit = opcode(8) + addr(32) + wdata(32)
   - AHB_RD32(opcode=0x21)：40-bit = opcode(8) + addr(32)
2. 响应帧长度：
   - 写命令响应：8-bit status_code
   - 读命令响应：40-bit = status(8) + rdata(32)
3. 各lane_mode下的接收周期数：
   - 1-bit模式：WR_CSR需48周期，RD_CSR需16周期
   - 4-bit模式：WR_CSR需12周期，RD_CSR需4周期。'''
    },
    {
        'chk_id': 'CHK_007',
        'chk_name': 'opcode_decode_checker',
        'chk_description': '''检查opcode译码正确性与非法opcode检测：
1. 有效opcode译码（帧接收满8bit后锁存opcode_latched_q）：
   - 0x10译码为WR_CSR：CSR写路径，发起csr_wr_en_o脉冲
   - 0x11译码为RD_CSR：CSR读路径，发起csr_rd_en_o脉冲
   - 0x20译码为AHB_WR32：AHB单次写，发起htrans=NONSEQ+hwrite=1
   - 0x21译码为AHB_RD32：AHB单次读，发起htrans=NONSEQ+hwrite=0
2. 非法opcode检测：opcode不在{0x10, 0x11, 0x20, 0x21}中时，前置检查返回STS_BAD_OPCODE(0x02)；
3. 错误优先级：STS_BAD_OPCODE(0x02)优先级低于STS_FRAME_ERR(0x01)，高于STS_NOT_IN_TEST(0x04)。'''
    },
    {
        'chk_id': 'CHK_008',
        'chk_name': 'ctrl_register_checker',
        'chk_description': '''检查CTRL寄存器配置生效与lane_mode切换约束：
1. CTRL.EN(bit0)：写1使能模块功能，写0禁用（等同于en_i=0效果，但通过命令配置）；
2. CTRL.LANE_MODE(bit[2:1])：写入00/01配置lane模式，镜像lane_mode_i端口值；
3. CTRL.SOFT_RST(bit3)：写1触发协议上下文软复位，清空RX/TX状态，恢复LANE_MODE为默认值(1-bit)；
4. 配置生效时机：WR_CSR命令执行后配置立即生效，下一帧接收使用新配置；
5. 事务期间lane_mode稳定：lane_mode_i在pcs_n_i=0期间不得切换，否则导致帧数据损坏（模块不检测此违规）。'''
    },
    {
        'chk_id': 'CHK_009',
        'chk_name': 'status_report_checker',
        'chk_description': '''检查STATUS寄存器与LAST_ERR寄存器的状态报告正确性：
1. STATUS[0](BUSY)：当前有事务执行时为1，空闲时为0；
2. STATUS[1](RESP_VALID)：最近响应有效时为1；
3. STATUS[2](CMD_ERR)：命令错误sticky位，有错误发生时置1，软件写1清零；
4. STATUS[3](BUS_ERR)：总线错误sticky位，AHB错误时置1；
5. STATUS[4](FRAME_ERR)：帧错误sticky位；
6. STATUS[5](IN_TEST_MODE)：镜像test_mode_i端口值；
7. STATUS[6](OUT_EN)：镜像pdo_oe_o信号；
8. LAST_ERR[7:0]：存储最近一次错误的状态码，新命令开始后被覆盖；
9. MVP版本无独立中断输出：所有状态通过寄存器轮询获取。'''
    },
    {
        'chk_id': 'CHK_010',
        'chk_name': 'error_priority_checker',
        'chk_description': '''检查错误优先级链与执行期错误检测正确性：
1. 前置检查错误按固定优先级链返回（高→低）：
   STS_FRAME_ERR(0x01) > STS_BAD_OPCODE(0x02) > STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08) > STS_BAD_REG(0x10) > STS_ALIGN_ERR(0x20)；
2. 任何前置错误均在发起CSR/AHB访问前收敛，不产生csr_wr_en_o/csr_rd_en_o/htrans_o脉冲；
3. STS_AHB_ERR(0x40)不在前置优先级链中：仅在前置检查全部通过后、AHB事务实际执行期间发生，与前置错误互斥；
4. AHB执行期错误：hresp_i=1时返回STS_AHB_ERR(0x40)；hready_i持续为0超过BUS_TIMEOUT_CYCLES(256)周期触发超时，返回STS_AHB_ERR(0x40)；
5. 多错误并发：仅报告最高优先级错误，不累积多错误。'''
    },
    {
        'chk_id': 'CHK_011',
        'chk_name': 'low_power_checker',
        'chk_description': '''检查空闲态低功耗行为与门控条件正确性：
1. pcs_n_i=1空闲态：接收移位寄存器(rx_shift_q)不更新，发送移位寄存器(tx_shift_q)不翻转；
2. 超时计数器：仅在AXI_WAIT状态工作，其他状态不计数不翻转；
3. test_mode_i=0时：AHB输出保持空闲（htrans_o=2'b00 IDLE，hburst_o=3'b000 SINGLE，haddr_o=0）；
4. 门控时钟条件：RX移位逻辑门控条件为pcs_n_i=1，TX移位逻辑门控条件为非TX态，超时计数器门控条件为state!=AXI_WAIT；
5. 空闲态触发器翻转率目标：<工作态的5%。'''
    },
    {
        'chk_id': 'CHK_012',
        'chk_name': 'performance_checker',
        'chk_description': '''检查端到端延时符合预期与地址对齐检查：
1. 4-bit模式延时估计：
   - AHB_RD32：RX(10周期)+译码(2)+AHB(2)+TA(1)+TX(10)≈23~24周期
   - AHB_WR32：RX(18)+译码(2)+AHB(2)+TA(1)+TX(2)≈23周期
   - WR_CSR：RX(12)+执行(1)+TA(1)+TX(2)≈16周期
2. 1-bit模式延时：约为4-bit的4倍（因帧长×4）
3. 地址对齐检查：AHB命令addr[1:0]!=2'b00返回STS_ALIGN_ERR(0x20)，对齐地址正常发起AHB访问；
4. hsize_o固定3'b010(WORD)，hburst_o固定3'b000(SINGLE)。'''
    },
    {
        'chk_id': 'CHK_013',
        'chk_name': 'dfx_observability_checker',
        'chk_description': '''检查内部调试观测点可正确反映状态：
1. FSM状态观测：front_state_q(IDLE/ISSUE/WAIT_RESP/TA/TX)、back_state_q、axi_state_q(AXI_IDLE/AXI_REQ/AXI_WAIT/AXI_DONE/AXI_ERR)；
2. 命令信息观测：opcode_latched_q[7:0]、burst_len、addr暂存值、wdata暂存值、rdata暂存值；
3. 状态码观测：status_code[7:0]、错误优先级判定结果；
4. 计数器观测：rx_count_q、tx_count_q、timeout_cnt；
5. 观测用途：仿真通过XMR直接观察，硅后通过DFT扫描链抽出或外部CSR镜像。'''
    },
    {
        'chk_id': 'CHK_014',
        'chk_name': 'ahb_master_checker',
        'chk_description': '''检查AHB-Lite Master协议符合性与2-phase流水正确性：
1. 2-phase流水：
   - T1地址相：驱动haddr_o[31:0]、hwrite_o、htrans_o=2'b10(NONSEQ)、hsize_o=3'b010、hburst_o=3'b000
   - T2数据相：写操作驱动hwdata_o[31:0]，读操作采样hrdata_i[31:0]
   - haddr与hwdata/hrdata必然错开1拍
2. 固定参数：hsize_o=3'b010(WORD)、hburst_o=3'b000(SINGLE)，不支持byte/halfword/Burst；
3. AHB错误响应：hresp_i=1时FSM进入AXI_ERR，返回STS_AHB_ERR(0x40)，AHB输出恢复IDLE；
4. 超时检测：hready_i=0持续256周期触发超时，进入AXI_ERR；
5. CSR不进入AHB memory map：CSR通过WR_CSR/RD_CSR命令访问，不产生AHB事务。'''
    }
]

# ============================================================
# Testcase Definitions (45 Testcases)
# ============================================================

TESTCASES = [
    # TP_001 (时钟) - 2 TCs
    {
        'tc_id': 'TC_001',
        'tc_name': 'test_clock_stability',
        'tc_description': '''配置条件：
1.模块上电复位完成，clk_i配置为100MHz目标频率；
2.test_mode_i=1，en_i=1，lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.持续运行模块超过1000个时钟周期，观察clk_i波形稳定性；
2.通过ATE接口连续发送10条RD_CSR命令（opcode=0x11，reg_addr=0x00读取VERSION寄存器）；
3.记录每条命令的响应周期数和status_code；
4.在不同lane_mode下（1-bit和4-bit）重复测试；

期望结果：
1.时钟波形稳定，无毛刺或异常跳变，周期偏差<3%；
2.所有RD_CSR命令响应正常，status_code=STS_OK(0x00)；
3.rdata返回VERSION寄存器固定值；
4.无时钟相关的协议错误或超时；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    {
        'tc_id': 'TC_002',
        'tc_name': 'test_clock_frequency',
        'tc_description': '''配置条件：
1.模块上电复位完成，clk_i运行；
2.test_mode_i=1，en_i=1；

输入激励：
1.配置lane_mode_i=2'b00（1-bit模式）；
2.发送RD_CSR命令测量帧接收时间，计算等效周期数；
3.配置lane_mode_i=2'b01（4-bit模式）；
4.发送RD_CSR命令测量帧接收时间，验证周期数为1-bit的1/4；
5.多次测量取平均值；

期望结果：
1.1-bit模式下RD_CSR帧(16bit)需16周期接收；
2.4-bit模式下RD_CSR帧(16bit)需4周期接收；
3.频率偏差<3%，无异常；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    # TP_002 (复位) - 3 TCs
    {
        'tc_id': 'TC_003',
        'tc_name': 'test_reset_behavior',
        'tc_description': '''配置条件：
1.模块上电，clk_i稳定运行100MHz；
2.初始配置test_mode_i=1，en_i=1，lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.拉低rst_ni触发异步复位，持续至少2个clk_i周期；
2.释放rst_ni（同步释放，与clk_i上升沿对齐）；
3.检查复位后状态：读取STATUS寄存器验证BUSY=0；
4.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）验证模块恢复工作；

期望结果：
1.复位后所有状态机回到IDLE态：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；
2.输出信号deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0；
3.pdo_o[15:0]=16'b0，协议上下文清空；
4.复位释放后RD_CSR命令正常响应status_code=STS_OK(0x00)；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    {
        'tc_id': 'TC_004',
        'tc_name': 'test_reset_recovery',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送WR_CSR命令（opcode=0x10，reg_addr=0x04(CTRL)，wdata=0x00000001）配置CTRL.EN=1；
2.发送RD_CSR命令（opcode=0x11，reg_addr=0x04）验证写入；
3.触发复位：拉低rst_ni至少2周期后释放；
4.复位后再次发送RD_CSR命令验证功能恢复；
5.检查CTRL.EN复位后是否变为0；

期望结果：
1.WR_CSR执行成功，status_code=STS_OK(0x00)；
2.RD_CSR读回CTRL=0x00000001；
3.复位后CTRL.EN=0，LANE_MODE=2'b00（默认值）；
4.复位释放后模块接受新命令并正常响应；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    {
        'tc_id': 'TC_005',
        'tc_name': 'test_reset_during_transaction',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.开始发送AHB_WR32命令（opcode=0x20，addr=0x10000000，wdata=0xDEADBEEF）；
2.在帧接收中途（如收到24bit后）触发rst_ni复位；
3.释放复位后检查状态机状态和输出；
4.发送新的RD_CSR命令验证恢复；

期望结果：
1.复位立即生效，FSM强制回到IDLE态；
2.输出deassert：pdo_oe_o=0，htrans_o=IDLE；
3.事务中止，不产生AHB访问；
4.复位释放后新命令正常响应；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    # TP_003 (寄存器) - 4 TCs
    {
        'tc_id': 'TC_006',
        'tc_name': 'test_csr_write',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送WR_CSR命令（opcode=0x10，reg_addr=0x04(CTRL)，wdata=0x00000001）写入CTRL.EN=1；
2.观察csr_wr_en_o脉冲时序：单周期脉冲，同周期采样csr_addr_o=0x04、csr_wdata_o=0x01；
3.发送RD_CSR命令（opcode=0x11，reg_addr=0x04）读回验证写入；
4.写VERSION寄存器（reg_addr=0x00，RO）：发送WR_CSR命令验证写被忽略；

期望结果：
1.WR_CSR执行成功：csr_wr_en_o脉冲持续1周期，响应status_code=STS_OK(0x00)；
2.RD_CSR读回CTRL=0x00000001，验证写入生效；
3.写VERSION(RO)寄存器不改变其值，响应status_code=STS_OK(0x00)；

coverage check点：
对CSR地址范围0x00~0x03采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_007',
        'tc_name': 'test_csr_read',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送RD_CSR命令（opcode=0x11，reg_addr=0x00(VERSION)）读取版本寄存器；
2.观察csr_rd_en_o脉冲时序：单周期脉冲，下一周期采样csr_rdata_i；
3.发送RD_CSR命令（opcode=0x11，reg_addr=0x08(STATUS)）读取状态寄存器；
4.检查响应帧格式：status(8bit)+rdata(32bit)=40bit；

期望结果：
1.RD_CSR(VERSION)：csr_rd_en_o脉冲后下一周期采样csr_rdata_i，响应status_code=STS_OK(0x00)+rdata；
2.RD_CSR(STATUS)：读取STATUS寄存器，BUSY=0（空闲态），IN_TEST_MODE=1；
3.读延迟固定1周期，无额外等待；

coverage check点：
对CSR读时序csr_rd_en_o→csr_rdata_i延迟采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_008',
        'tc_name': 'test_csr_address_error',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送RD_CSR命令（opcode=0x11，reg_addr=0x40）验证地址越界；
2.发送RD_CSR命令（opcode=0x11，reg_addr=0x3F）验证边界地址（有效）；
3.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）验证最小地址（有效）；
4.发送WR_CSR命令（opcode=0x10，reg_addr=0x50，wdata=0x12345678）验证越界写；

期望结果：
1.reg_addr=0x40（越界）：返回STS_BAD_REG(0x10)，不发起csr_rd_en_o脉冲；
2.reg_addr=0x3F（边界）：正常响应（若该地址预留可能返回其他状态）；
3.reg_addr=0x00（最小）：正常响应status_code=STS_OK(0x00)；
4.reg_addr=0x50（越界写）：返回STS_BAD_REG(0x10)，不发起csr_wr_en_o脉冲；

coverage check点：
对CSR地址范围边界采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_009',
        'tc_name': 'test_csr_all_registers',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i随机选择（1-bit或4-bit）；

输入激励：
1.遍历所有CSR寄存器地址：VERSION(0x00)、CTRL(0x04)、STATUS(0x08)、LAST_ERR(0x0C)；
2.对每个寄存器执行RD_CSR读取；
3.对每个寄存器尝试WR_CSR写入，验证RO/RW属性；
4.检查写入是否生效或被忽略（RO寄存器）；
5.重复执行N次（N≥10），每次随机lane_mode；

期望结果：
1.VERSION(0x00) RO：读返回版本值，写被忽略；
2.CTRL(0x04) RW：读写均生效，写入值可读回；
3.STATUS(0x08) RO：读返回状态，写被忽略；
4.LAST_ERR(0x0C) RO：读返回最近错误码；
5.所有读写命令status_code=STS_OK(0x00)；

coverage check点：
随机测试，覆盖lane_mode×CSR寄存器的功能覆盖率'''
    },
    # TP_004 (工作模式) - 3 TCs
    {
        'tc_id': 'TC_010',
        'tc_name': 'test_test_mode_rejection',
        'tc_description': '''配置条件：
1.模块复位完成，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.设置test_mode_i=0；
2.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
3.检查响应帧status_code；
4.检查是否产生csr_rd_en_o脉冲；
5.发送AHB_WR32命令验证同样被拒绝；
6.恢复test_mode_i=1，验证命令正常执行；

期望结果：
1.test_mode_i=0时：返回STS_NOT_IN_TEST(0x04)；
2.不发起CSR访问：csr_rd_en_o=0；
3.不发起AHB访问：htrans_o=IDLE；
4.test_mode_i=1恢复后命令正常响应STS_OK(0x00)；

coverage check点：
对test_mode_i状态采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_011',
        'tc_name': 'test_en_rejection',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.设置en_i=0；
2.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
3.检查响应帧status_code；
4.检查是否产生csr_rd_en_o脉冲；
5.发送AHB_RD32命令验证同样被拒绝；
6.恢复en_i=1，验证命令正常执行；

期望结果：
1.en_i=0时：返回STS_DISABLED(0x08)；
2.不发起CSR访问：csr_rd_en_o=0，csr_wr_en_o=0；
3.不发起AHB访问：htrans_o=2'b00(IDLE)；
4.en_i=1恢复后命令正常响应STS_OK(0x00)；

coverage check点：
对en_i状态采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_012',
        'tc_name': 'test_mode_priority',
        'tc_description': '''配置条件：
1.模块复位完成；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.设置test_mode_i=0，en_i=0（两个条件同时不满足）；
2.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
3.检查返回的status_code优先级；
4.设置test_mode_i=0，en_i=1；
5.发送命令检查返回STS_NOT_IN_TEST；
6.设置test_mode_i=1，en_i=0；
7.发送命令检查返回STS_DISABLED；

期望结果：
1.test_mode_i=0且en_i=0时：返回STS_NOT_IN_TEST(0x04)，优先级高于STS_DISABLED(0x08)；
2.test_mode_i=0，en_i=1时：返回STS_NOT_IN_TEST(0x04)；
3.test_mode_i=1，en_i=0时：返回STS_DISABLED(0x08)；
4.所有拒绝场景下无CSR/AHB访问；

coverage check点：
验证错误优先级链：STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08)'''
    },
    # TP_005 (Lane Mode) - 3 TCs
    {
        'tc_id': 'TC_013',
        'tc_name': 'test_1bit_lane_mode',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b00（1-bit模式）；

输入激励：
1.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
2.通过pdi_i[0]按MSB-first方式逐bit发送帧数据，记录接收周期数；
3.验证仅pdi_i[0]有效，pdi_i[15:1]被忽略；
4.响应阶段检查pdo_o[0]输出，pdo_o[15:1]=0；
5.发送WR_CSR命令验证48-bit帧需48周期接收；

期望结果：
1.RD_CSR帧(16bit)：需16个周期接收（每周期1bit）；
2.WR_CSR帧(48bit)：需48个周期接收；
3.pdi_i[15:1]值不影响接收结果；
4.pdo_o[15:1]保持为0；
5.status_code=STS_OK(0x00)；

coverage check点：
对1-bit lane模式采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_014',
        'tc_name': 'test_4bit_lane_mode',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
2.通过pdi_i[3:0]按MSB-first方式发送帧数据，每周期4bit，记录接收周期数；
3.验证使用pdi_i[3:0]，按高nibble优先发送；
4.响应阶段检查pdo_o[3:0]输出；
5.发送WR_CSR命令验证12周期接收；

期望结果：
1.RD_CSR帧(16bit)：需4个周期接收（每周期4bit）；
2.WR_CSR帧(48bit)：需12个周期接收；
3.按高nibble优先顺序接收；
4.pdo_o[15:4]保持为0；
5.status_code=STS_OK(0x00)；

coverage check点：
对4-bit lane模式采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_015',
        'tc_name': 'test_lane_mode_switching',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；

输入激励：
1.在pcs_n_i=1空闲期间切换lane_mode_i从2'b00到2'b01；
2.等待≥2周期同步后拉低pcs_n_i开始新帧；
3.验证帧接收使用新lane_mode（4周期@4-bit）；
4.违规测试：在pcs_n_i=0事务期间中途切换lane_mode_i；
5.继续发送命令，检查帧数据错位或错误状态；

期望结果：
1.pcs_n_i=1期间切换：下次事务正常，使用新lane_mode；
2.pcs_n_i=0期间切换：帧数据损坏，可能导致opcode错误（STS_BAD_OPCODE）或帧中止（STS_FRAME_ERR）；
3.模块不检测此违规，由集成方保证；

coverage check点：
随机测试，覆盖lane_mode切换场景的功能覆盖率'''
    },
    # TP_006 (数据接口-协议) - 3 TCs
    {
        'tc_id': 'TC_016',
        'tc_name': 'test_frame_transmission',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式），pcs_n_i初始为高电平；

输入激励：
1.ATE拉低pcs_n_i开始帧传输；
2.按MSB-first顺序通过pdi_i[3:0]发送RD_CSR帧：opcode=0x11 + reg_addr=0x00；
3.帧接收完成后等待1个turnaround周期；
4.检查pdo_oe_o拉高，模块驱动pdo_o[3:0]输出响应；
5.响应帧发送完成后pdo_oe_o拉低，pcs_n_i拉高结束事务；

期望结果：
1.请求阶段：pcs_n_i=0期间接收数据，pdo_oe_o=0；
2.turnaround：固定1周期，pdo_oe_o保持0；
3.响应阶段：pdo_oe_o=1，模块驱动pdo_o；
4.status_code=STS_OK(0x00)；
5.帧边界正确，无总线冲突；

coverage check点：
对帧边界和turnaround采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_017',
        'tc_name': 'test_frame_abort',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
场景1：opcode已锁存后中止
1.发送WR_CSR命令（opcode=0x10 + reg_addr + wdata）；
2.在接收第5周期（收到20bit，opcode已锁存8bit）后提前拉高pcs_n_i；
3.检查返回STS_FRAME_ERR(0x01)；

场景2：opcode未锁存时中止
4.发送命令但在接收第1周期（收到4bit，opcode未锁存）后拉高pcs_n_i；
5.检查不产生frame_abort，静默复位；

期望结果：
1.场景1：返回STS_FRAME_ERR(0x01)，pdo_oe_o拉高后输出状态码；
2.场景2：接收状态静默复位，不产生响应输出；
3.两种场景均不发起CSR/AHB访问；

coverage check点：
对帧中止时机（opcode已锁存/未锁存）采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_018',
        'tc_name': 'test_turnaround',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送RD_CSR命令（opcode=0x11，reg_addr=0x00）；
2.帧接收完成后观察FSM状态：WAIT_RESP→TA→TX；
3.在TA态检查pdo_oe_o=0（高阻态）；
4.进入TX态后检查pdo_oe_o=1（驱动态）；
5.测量TA持续时间是否为1周期；

期望结果：
1.帧接收完成→进入WAIT_RESP等待后端响应；
2.WAIT_RESP→TA：pdo_oe_o=0保持，总线高阻态；
3.TA→TX：pdo_oe_o由0变1，开始输出响应；
4.TA持续时间固定1周期；
5.无总线冲突；

coverage check点：
对turnaround时长采集功能覆盖率'''
    },
    # TP_007 (数据接口-帧长) - 3 TCs
    {
        'tc_id': 'TC_019',
        'tc_name': 'test_all_command_frames',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送WR_CSR命令：opcode=0x10 + reg_addr=0x04 + wdata=0x12345678（48-bit帧，12周期@4-bit）；
2.发送RD_CSR命令：opcode=0x11 + reg_addr=0x00（16-bit帧，4周期@4-bit）；
3.发送AHB_WR32命令：opcode=0x20 + addr=0x10000000 + wdata=0xDEADBEEF（72-bit帧，18周期@4-bit）；
4.发送AHB_RD32命令：opcode=0x21 + addr=0x20000000（40-bit帧，10周期@4-bit）；
5.验证每种命令的接收周期数；

期望结果：
1.WR_CSR帧：接收48-bit需12周期（4-bit模式）；
2.RD_CSR帧：接收16-bit需4周期；
3.AHB_WR32帧：接收72-bit需18周期；
4.AHB_RD32帧：接收40-bit需10周期；
5.所有命令status_code=STS_OK(0x00)；

coverage check点：
对所有opcode帧格式采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_020',
        'tc_name': 'test_response_frames',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送WR_CSR命令（写命令），验证响应帧仅8-bit status_code；
2.发送RD_CSR命令（读命令），验证响应帧40-bit：status(8)+rdata(32)；
3.发送AHB_WR32命令（写命令），验证响应帧8-bit；
4.发送AHB_RD32命令（读命令），验证响应帧40-bit；
5.检查响应格式的MSB-first顺序；

期望结果：
1.写命令响应：pdo_o输出status(8bit)，4-bit模式下需2周期；
2.读命令响应：pdo_o输出status(8bit)+rdata(32bit)=40bit，4-bit模式下需10周期；
3.响应按MSB-first顺序；
4.所有status_code=STS_OK(0x00)；

coverage check点：
对响应帧格式采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_021',
        'tc_name': 'test_frame_length_boundary',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.随机选择lane_mode（1-bit或4-bit）；

输入激励：
1.随机选择命令类型（WR_CSR/RD_CSR/AHB_WR32/AHB_RD32）；
2.在选定的lane_mode下发送命令，记录接收周期数；
3.验证接收周期数=帧长度(bit)/lane_width(bit)；
4.重复执行N次（N≥20），覆盖所有命令×lane_mode组合；
5.检查响应帧周期数同样符合预期；

期望结果：
1.各lane_mode下帧接收周期数正确：
   - 1-bit：WR_CSR需48周期，RD_CSR需16周期，AHB_WR32需72周期，AHB_RD32需40周期
   - 4-bit：WR_CSR需12周期，RD_CSR需4周期，AHB_WR32需18周期，AHB_RD32需10周期
2.响应周期数同样正确；
3.所有命令正常响应；

coverage check点：
随机测试，覆盖lane_mode×opcode组合的功能覆盖率'''
    },
    # TP_008 (控制接口) - 3 TCs
    {
        'tc_id': 'TC_022',
        'tc_name': 'test_valid_opcodes',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送opcode=0x10命令，验证WR_CSR路径：产生csr_wr_en_o脉冲；
2.发送opcode=0x11命令，验证RD_CSR路径：产生csr_rd_en_o脉冲；
3.发送opcode=0x20命令，验证AHB_WR32路径：产生htrans=NONSEQ+hwrite=1；
4.发送opcode=0x21命令，验证AHB_RD32路径：产生htrans=NONSEQ+hwrite=0；
5.检查每种opcode的内部译码结果正确；

期望结果：
1.0x10→WR_CSR：cmd_type指示CSR写，csr_wr_en_o脉冲；
2.0x11→RD_CSR：cmd_type指示CSR读，csr_rd_en_o脉冲；
3.0x20→AHB_WR32：cmd_type指示AHB写，htrans_o=2'b10(NONSEQ)，hwrite_o=1；
4.0x21→AHB_RD32：cmd_type指示AHB读，htrans_o=2'b10，hwrite_o=0；
5.所有命令status_code=STS_OK(0x00)；

coverage check点：
对所有有效opcode采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_023',
        'tc_name': 'test_illegal_opcode',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送opcode=0x00（非法），验证返回STS_BAD_OPCODE(0x02)；
2.发送opcode=0x0F（非法边界），验证返回STS_BAD_OPCODE；
3.发送opcode=0x12（非法，在0x11和0x20之间），验证返回STS_BAD_OPCODE；
4.发送opcode=0xFF（非法边界），验证返回STS_BAD_OPCODE；
5.随机选择N个（N≥10）非法opcode（0x00~0x0F，0x12~0x1F，0x22~0xFF）验证；
6.检查不发起CSR/AHB访问；

期望结果：
1.所有非法opcode返回STS_BAD_OPCODE(0x02)；
2.opcode检查在前置检查阶段，不发起任何CSR/AHB访问；
3.csr_wr_en_o=0，csr_rd_en_o=0，htrans_o=IDLE；
4.错误优先级正确；

coverage check点：
随机测试，覆盖非法opcode范围的功能覆盖率'''
    },
    {
        'tc_id': 'TC_024',
        'tc_name': 'test_opcode_boundary',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送opcode=0x0F（非法，与有效0x10相邻）验证返回STS_BAD_OPCODE；
2.发送opcode=0x10（有效边界）验证正常译码为WR_CSR；
3.发送opcode=0x11（有效）验证正常译码为RD_CSR；
4.发送opcode=0x12（非法，与有效0x11相邻）验证返回STS_BAD_OPCODE；
5.发送opcode=0x1F（非法）验证返回STS_BAD_OPCODE；
6.发送opcode=0x20（有效边界）验证正常译码为AHB_WR32；

期望结果：
1.opcode边界值正确区分有效/非法：
   - 有效：0x10(WR_CSR)、0x11(RD_CSR)、0x20(AHB_WR32)、0x21(AHB_RD32)
   - 非法：其他所有值
2.有效opcode正常执行，非法返回STS_BAD_OPCODE(0x02)；

coverage check点：
对opcode边界值采集功能覆盖率'''
    },
    # TP_009 (配置接口) - 3 TCs
    {
        'tc_id': 'TC_025',
        'tc_name': 'test_lane_mode_config',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i初始为2'b00（1-bit）；

输入激励：
1.通过WR_CSR命令配置CTRL.LANE_MODE=2'b01（4-bit模式）；
2.发送RD_CSR命令读取CTRL验证配置；
3.发送RD_CSR命令测试帧接收，验证使用4-bit模式（4周期接收16bit）；
4.通过WR_CSR命令配置CTRL.LANE_MODE=2'b00（1-bit）；
5.再次发送命令验证使用1-bit模式（16周期接收16bit）；

期望结果：
1.CTRL.LANE_MODE写入成功，可读回；
2.配置后帧收发使用新lane模式；
3.LANE_MODE仅支持00(1-bit)和01(4-bit)，MVP不支持10/11；
4.帧接收周期数符合lane模式；

coverage check点：
对LANE_MODE配置切换采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_026',
        'tc_name': 'test_soft_reset',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.发送WR_CSR命令配置CTRL.EN=1，LANE_MODE=01；
2.发送RD_CSR命令验证配置；
3.发送WR_CSR命令写入CTRL.SOFT_RST=1触发软复位；
4.检查协议上下文是否清零；
5.读取CTRL验证LANE_MODE恢复默认值2'b00；
6.发送RD_CSR命令验证模块正常工作；

期望结果：
1.SOFT_RST=1后：协议上下文清空，LANE_MODE恢复2'b00（1-bit默认）；
2.FSM状态回到IDLE；
3.软复位不影响CTRL.EN（由硬件端口en_i控制）；
4.复位后模块正常接受新命令；

coverage check点：
对SOFT_RST触发采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_027',
        'tc_name': 'test_config_timing',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.pcs_n_i=1（空闲态）；

输入激励：
1.在pcs_n_i=1期间切换lane_mode_i从2'b00到2'b01；
2.等待≥2个clk_i周期做同步；
3.拉低pcs_n_i开始新帧，验证使用新lane_mode；
4.测试不等足够周期（如只等1周期）就开始新帧，检查行为；
5.测试在pcs_n_i=0期间切换lane_mode（违规）；

期望结果：
1.pcs_n_i=1期间切换并等待≥2周期后新帧正常；
2.不等足够周期可能导致lane_mode未同步，帧数据错位；
3.pcs_n_i=0期间切换导致帧损坏（模块不检测）；
4.lane_mode需在事务边界切换；

coverage check点：
对lane_mode切换时序采集功能覆盖率'''
    },
    # TP_010 (中断) - 1 TC
    {
        'tc_id': 'TC_028',
        'tc_name': 'test_status_polling',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；

输入激励：
1.检查模块无独立中断输出端口（IRQ）；
2.发送命令（成功/失败）；
3.通过RD_CSR读取STATUS寄存器获取状态；
4.通过RD_CSR读取LAST_ERR寄存器获取最近错误码；
5.测试sticky位的清除（写1清零，WC属性）；

期望结果：
1.MVP版本无独立中断输出；
2.STATUS寄存器反映当前状态：BUSY、RESP_VALID、CMD_ERR等位；
3.LAST_ERR存储最近错误码，新命令开始后覆盖；
4.所有状态通过寄存器轮询获取；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    # TP_011 (异常) - 5 TCs
    {
        'tc_id': 'TC_029',
        'tc_name': 'test_error_priority_chain',
        'tc_description': '''配置条件：
1.模块复位完成；
2.lane_mode_i=2'b01；

输入激励：
1.构造多错误并发场景：发送非法opcode(0xFF)且test_mode_i=0且en_i=0；
   → 验证返回STS_FRAME_ERR(0x01)（最高优先级，因帧结构损坏优先判断）；
   注：实际上frame_abort来自pcs_n_i提前释放，此处改为：
   设置pcs_n_i提前拉高触发frame_abort + 其他错误条件；
2.发送非法opcode(0xFF)且test_mode_i=1且en_i=1；
   → 返回STS_BAD_OPCODE(0x02)；
3.test_mode_i=0且en_i=0；
   → 返回STS_NOT_IN_TEST(0x04)（优先于STS_DISABLED）；
4.test_mode_i=1且en_i=0；
   → 返回STS_DISABLED(0x08)；
5.发送CSR命令reg_addr=0x40；
   → 返回STS_BAD_REG(0x10)；
6.发送AHB命令addr=0x00000001（非对齐）；
   → 返回STS_ALIGN_ERR(0x20)；

期望结果：
1.错误优先级链：0x01>0x02>0x04>0x08>0x10>0x20；
2.仅返回最高优先级错误，不累积；
3.前置错误均不发起CSR/AHB访问；

coverage check点：
对错误优先级链采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_030',
        'tc_name': 'test_ahb_error_response',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；
3.AHB Slave配置为返回错误响应；

输入激励：
1.发送AHB_RD32命令（opcode=0x21，addr=0x10000000）；
2.配置AHB Slave在数据相返回hresp_i=1；
3.检查模块返回STS_AHB_ERR(0x40)；
4.检查AXI FSM进入AXI_ERR状态；
5.检查AHB输出恢复空闲（htrans_o=IDLE）；
6.恢复Slave正常响应，发送新命令验证恢复；

期望结果：
1.hresp_i=1时返回STS_AHB_ERR(0x40)；
2.AXI FSM：AXI_WAIT→AXI_ERR→AXI_IDLE；
3.错误响应后AHB输出空闲，可接受新请求；
4.新命令正常响应；

coverage check点：
对hresp_i错误响应采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_031',
        'tc_name': 'test_ahb_timeout',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；
3.AHB Slave配置为持续不响应；

输入激励：
1.发送AHB_WR32命令（opcode=0x20，addr=0x10000000，wdata=0x12345678）；
2.配置AHB Slave保持hready_i=0，不返回响应；
3.等待超过BUS_TIMEOUT_CYCLES(256)周期；
4.检查模块返回STS_AHB_ERR(0x40)；
5.检查超时计数器达到阈值后触发AXI_ERR；
6.恢复Slave响应，发送新命令验证；

期望结果：
1.hready_i=0持续256周期后触发超时；
2.返回STS_AHB_ERR(0x40)，与hresp_i错误使用相同状态码；
3.timeout_cnt从0计数到255后触发AXI_ERR；
4.AHB输出恢复空闲；

coverage check点：
对AHB超时采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_032',
        'tc_name': 'test_frame_error',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；

输入激励：
帧中止(FRAME_ERR)场景：
1.发送WR_CSR命令，在接收中途（如收到24bit）提前拉高pcs_n_i；
2.检查返回STS_FRAME_ERR(0x01)；
3.检查不发起CSR访问；

非对齐地址(ALIGN_ERR)场景：
4.发送AHB_WR32命令addr=0x10000001（addr[1:0]!=0）；
5.检查返回STS_ALIGN_ERR(0x20)；
6.检查不发起AHB访问；

期望结果：
1.帧中止：返回STS_FRAME_ERR(0x01)，pdo_oe_o拉高后输出状态码；
2.非对齐地址：返回STS_ALIGN_ERR(0x20)，不发起AHB事务；
3.两种错误均为前置检查，不产生总线访问；

coverage check点：
对FRAME_ERR和ALIGN_ERR采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_033',
        'tc_name': 'test_random_error_injection',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.随机选择lane_mode；

输入激励：
随机注入以下错误类型之一：
1.非法opcode：随机选择0x00~0x0F或0x12~0x1F或0x22~0xFF；
   → 期望返回STS_BAD_OPCODE(0x02)
2.非对齐地址：随机设置addr[1:0]!=0；
   → 期望返回STS_ALIGN_ERR(0x20)
3.CSR地址越界：随机reg_addr>=0x40；
   → 期望返回STS_BAD_REG(0x10)
4.AHB错误响应：配置hresp_i=1；
   → 期望返回STS_AHB_ERR(0x40)
5.AHB超时：配置hready_i=0持续>256周期；
   → 期望返回STS_AHB_ERR(0x40)

每种错误类型重复执行N次（N≥10）；

期望结果：
1.每种错误返回对应的状态码；
2.前置错误不发起总线访问；
3.执行期错误正确处理并恢复；

coverage check点：
随机测试，覆盖所有错误类型的场景功能覆盖率'''
    },
    # TP_012 (低功耗) - 2 TCs
    {
        'tc_id': 'TC_034',
        'tc_name': 'test_idle_power',
        'tc_description': '''配置条件：
1.模块复位完成；
2.pcs_n_i=1保持空闲态；

输入激励：
1.保持pcs_n_i=1超过100个时钟周期；
2.检查RX移位寄存器rx_shift_q不更新；
3.检查TX移位寄存器tx_shift_q不翻转；
4.检查超时计数器timeout_cnt不工作（非AXI_WAIT状态）；
5.检查关键寄存器无多余翻转；
6.发送一条命令唤醒，验证正常工作；

期望结果：
1.空闲态：rx_shift_q、tx_shift_q保持，不翻转；
2.超时计数器仅在AXI_WAIT计数；
3.test_mode_i=0时AHB输出保持IDLE；
4.唤醒后模块正常响应命令；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    {
        'tc_id': 'TC_035',
        'tc_name': 'test_clock_gating',
        'tc_description': '''配置条件：
1.模块复位完成；
2.lane_mode_i=2'b01；

输入激励：
1.设置test_mode_i=0；
2.检查htrans_o保持2'b00(IDLE)；
3.检查hburst_o=3'b000(SINGLE)；
4.检查haddr_o=0或保持上一值；
5.检查超时计数器仅在AXI_WAIT状态工作；
6.发送命令验证被拒绝；

期望结果：
1.test_mode_i=0时：AHB输出保持空闲；
2.超时计数器门控条件：state!=AXI_WAIT；
3.RX门控条件：pcs_n_i=1；
4.TX门控条件：非TX态；
5.低功耗设计正确生效；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    # TP_013 (性能) - 3 TCs
    {
        'tc_id': 'TC_036',
        'tc_name': 'test_latency_measurement',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01（4-bit模式）；
3.clk_i=100MHz；

输入激励：
1.发送AHB_RD32命令，测量从pcs_n_i拉低到响应完成的周期数；
   计算：RX(10)+译码(2)+AHB(2)+TA(1)+TX(10)≈23~24周期；
2.发送AHB_WR32命令，测量端到端延时；
   计算：RX(18)+译码(2)+AHB(2)+TA(1)+TX(2)≈23周期；
3.发送WR_CSR命令，测量延时；
   计算：RX(12)+执行(1)+TA(1)+TX(2)≈16周期；
4.切换到1-bit模式重复测量；

期望结果：
1.4-bit模式AHB_RD32最小延时约23~24周期；
2.4-bit模式AHB_WR32最小延时约23周期；
3.4-bit模式WR_CSR最小延时约16周期；
4.1-bit模式延时约为4-bit的4倍；

coverage check点：
对端到端延时采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_037',
        'tc_name': 'test_address_alignment',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；

输入激励：
1.发送AHB_WR32命令addr=0x10000000（对齐，addr[1:0]=00）；
2.验证正常执行，返回STS_OK(0x00)；
3.发送AHB_WR32命令addr=0x10000001（非对齐，addr[1:0]=01）；
4.验证返回STS_ALIGN_ERR(0x20)；
5.发送AHB_RD32命令addr=0x10000002（非对齐）验证；
6.发送AHB_RD32命令addr=0x10000003（非对齐）验证；
7.检查非对齐地址不发起AHB事务；

期望结果：
1.对齐地址(addr[1:0]=00)：正常访问，status_code=STS_OK；
2.非对齐地址(addr[1:0]!=00)：返回STS_ALIGN_ERR(0x20)；
3.非对齐地址不发起AHB访问：htrans_o保持IDLE；
4.hsize_o固定为WORD(3'b010)，不支持byte/halfword；

coverage check点：
对地址对齐检查采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_038',
        'tc_name': 'test_random_config_throughput',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.随机lane_mode（1-bit或4-bit）；

输入激励：
1.随机选择lane_mode：2'b00(1-bit)或2'b01(4-bit)；
2.随机选择opcode：0x10/0x11/0x20/0x21；
3.发送命令，测量端到端延时；
4.记录延时值并与理论值对比；
5.重复执行N次（N≥20），覆盖lane_mode×opcode所有组合；
6.计算实际吞吐率；

期望结果：
1.各组合延时符合理论预期；
2.4-bit模式：RD_CSR≈6周期，WR_CSR≈16周期，AHB_RD32≈24周期，AHB_WR32≈23周期；
3.1-bit模式：各命令延时约为4-bit的4倍；
4.吞吐率：4-bit约30MB/s，1-bit约7.5MB/s；

coverage check点：
随机测试，覆盖lane_mode×opcode组合的延时功能覆盖率'''
    },
    # TP_014 (DFX) - 2 TCs
    {
        'tc_id': 'TC_039',
        'tc_name': 'test_debug_observability',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；

输入激励：
1.发送WR_CSR命令（opcode=0x10，reg_addr=0x04，wdata=0x01）；
2.检查内部可观测点：
   - front_state：观察IDLE→ISSUE→WAIT_RESP→TA→TX状态变化
   - opcode_latched_q：锁存值=0x10
   - addr暂存值：N/A（CSR命令）
   - wdata暂存值：0x00000001
   - status_code：STS_OK(0x00)
3.发送AHB_RD32命令；
4.观察：
   - axi_state：AXI_IDLE→AXI_REQ→AXI_WAIT→AXI_DONE
   - haddr_o：验证地址值
   - hrdata_i：验证读数据
   - status_code

期望结果：
1.所有状态机状态变化可观测；
2.opcode、addr、wdata、rdata、status_code正确反映；
3.错误场景下LAST_ERR可观测到错误码；
4.DFX可观测点覆盖关键内部状态；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    {
        'tc_id': 'TC_040',
        'tc_name': 'test_random_debug_observability',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.随机lane_mode；

输入激励：
1.随机选择命令类型（WR_CSR/RD_CSR/AHB_WR32/AHB_RD32）；
2.随机选择成功或失败场景：
   - 成功：正常参数
   - 失败：注入错误（非法opcode、非对齐地址等）
3.执行命令，记录内部观测点状态；
4.验证观测点状态与命令执行一致；
5.重复执行N次（N≥15）；

期望结果：
1.成功场景：观测到正常状态流，status_code=STS_OK；
2.失败场景：观测到错误状态，status_code=对应错误码；
3.ERR状态机观测：前置错误不进入AXI FSM；
4.状态观测与实际执行一致；

coverage check点：
随机测试，覆盖各种场景的DFX可观测性功能覆盖率'''
    },
    # TP_015 (Memory Map) - 1 TC
    {
        'tc_id': 'TC_041',
        'tc_name': 'test_memory_map',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；

输入激励：
1.通过WR_CSR/RD_CSR访问模块CSR（opcode=0x10/0x11）；
   验证CSR不产生AHB事务，无htrans_o脉冲；
2.通过AHB_WR32/AHB_RD32访问SoC AHB fabric；
   验证产生htrans_o=NONSEQ；
3.检查AHB Master地址空间：
   - 使用32-bit地址
   - WORD访问粒度（hsize=3'b010）
4.验证CSR地址(0x00~0x3F)与AHB地址空间独立；

期望结果：
1.CSR通过协议命令访问，不进入AHB memory map；
2.AHB Master使用32-bit地址访问SoC；
3.CSR访问不产生htrans_o脉冲；
4.Memory map分离正确；

coverage check点：
直接用例覆盖，不收功能覆盖率'''
    },
    # TP_016 (总线接口) - 4 TCs
    {
        'tc_id': 'TC_042',
        'tc_name': 'test_ahb_write',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；
3.AHB Slave配置正常响应；

输入激励：
1.发送AHB_WR32命令（opcode=0x20，addr=0x10000000，wdata=0xDEADBEEF）；
2.观察AHB 2-phase流水：
   - T1（地址相）：htrans_o=2'b10(NONSEQ)，haddr_o=0x10000000，hwrite_o=1，hsize_o=3'b010，hburst_o=3'b000
   - T2（数据相）：hwdata_o=0xDEADBEEF有效，htrans_o回到IDLE
3.检查haddr与hwdata错开1拍；
4.检查在hready_i=1时一拍完成；
5.检查响应status_code=STS_OK(0x00)；

期望结果：
1.地址相：htrans=NONSEQ，驱动haddr+hwrite+hsize+hburst；
2.数据相：驱动hwdata，htrans回到IDLE；
3.haddr与hwdata必然错开1拍；
4.hsize=3'b010(WORD)，hburst=3'b000(SINGLE)固定；
5.写操作成功，status_code=0x00；

coverage check点：
对AHB写时序采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_043',
        'tc_name': 'test_ahb_read',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；
3.AHB Slave配置正常响应并提供读数据；

输入激励：
1.发送AHB_RD32命令（opcode=0x21，addr=0x20000000）；
2.观察AHB 2-phase流水：
   - T1（地址相）：htrans_o=NONSEQ，haddr_o=0x20000000，hwrite_o=0
   - T2（数据相）：采样hrdata_i，htrans_o=IDLE
3.检查haddr与hrdata错开1拍；
4.验证Slave在数据相提供hrdata；
5.检查响应帧包含正确rdata；

期望结果：
1.地址相：htrans=NONSEQ，驱动haddr，hwrite=0；
2.数据相：采样hrdata，htrans=IDLE；
3.haddr与hrdata错开1拍；
4.rdata正确返回在响应帧中；
5.status_code=STS_OK(0x00)；

coverage check点：
对AHB读时序采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_044',
        'tc_name': 'test_ahb_2phase_pipeline',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i=2'b01；

输入激励：
1.连续发送AHB_WR32和AHB_RD32命令；
2.观察每个命令的AHB 2-phase流水；
3.检查固定参数：
   - hsize_o=3'b010(WORD)
   - hburst_o=3'b000(SINGLE)
   - 不支持BUSY传输类型
4.验证地址相与数据相overlap 1拍；
5.验证hready_i等待扩展数据相；

期望结果：
1.每个AHB事务为独立的SINGLE传输；
2.hsize固定WORD，hburst固定SINGLE；
3.地址相(htrans=NONSEQ)与数据相(hwdata/hrdata)错开1拍；
4.hready_i=0时数据相扩展等待；
5.MVP不支持连续Burst，每事务独立；

coverage check点：
对AHB 2-phase流水的固定参数采集功能覆盖率'''
    },
    {
        'tc_id': 'TC_045',
        'tc_name': 'test_ahb_error_recovery',
        'tc_description': '''配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.lane_mode_i随机选择（1-bit或4-bit）；

输入激励：
1.发送AHB_RD32命令；
2.配置Slave返回hresp_i=1触发错误；
3.观察AXI FSM：AXI_WAIT→AXI_ERR→AXI_IDLE；
4.检查status_code=STS_AHB_ERR(0x40)；
5.恢复Slave正常响应；
6.发送新命令（随机类型）验证模块恢复；
7.重复执行N次（N≥10），覆盖各种lane_mode和命令类型；

期望结果：
1.hresp_i=1后FSM正确进入AXI_ERR状态；
2.AHB输出恢复空闲：htrans=IDLE；
3.错误恢复后新命令正常响应；
4.恢复机制可靠；

coverage check点：
随机测试，覆盖AHB错误恢复场景的功能覆盖率'''
    }
]

# ============================================================
# FL-TP Links (TP -> Checker -> Testcase)
# ============================================================

FL_TP_LINKS = [
    {'tp_id': 'TP_001', 'checker_id': 'CHK_001', 'testcase_id': 'TC_001, TC_002'},
    {'tp_id': 'TP_002', 'checker_id': 'CHK_001', 'testcase_id': 'TC_003, TC_004, TC_005'},
    {'tp_id': 'TP_003', 'checker_id': 'CHK_002', 'testcase_id': 'TC_006, TC_007, TC_008, TC_009'},
    {'tp_id': 'TP_004', 'checker_id': 'CHK_003', 'testcase_id': 'TC_010, TC_011, TC_012'},
    {'tp_id': 'TP_005', 'checker_id': 'CHK_004', 'testcase_id': 'TC_013, TC_014, TC_015'},
    {'tp_id': 'TP_006', 'checker_id': 'CHK_005', 'testcase_id': 'TC_016, TC_017, TC_018'},
    {'tp_id': 'TP_007', 'checker_id': 'CHK_006', 'testcase_id': 'TC_019, TC_020, TC_021'},
    {'tp_id': 'TP_008', 'checker_id': 'CHK_007', 'testcase_id': 'TC_022, TC_023, TC_024'},
    {'tp_id': 'TP_009', 'checker_id': 'CHK_008', 'testcase_id': 'TC_025, TC_026, TC_027'},
    {'tp_id': 'TP_010', 'checker_id': 'CHK_009', 'testcase_id': 'TC_028'},
    {'tp_id': 'TP_011', 'checker_id': 'CHK_010', 'testcase_id': 'TC_029, TC_030, TC_031, TC_032, TC_033'},
    {'tp_id': 'TP_012', 'checker_id': 'CHK_011', 'testcase_id': 'TC_034, TC_035'},
    {'tp_id': 'TP_013', 'checker_id': 'CHK_012', 'testcase_id': 'TC_036, TC_037, TC_038'},
    {'tp_id': 'TP_014', 'checker_id': 'CHK_013', 'testcase_id': 'TC_039, TC_040'},
    {'tp_id': 'TP_015', 'checker_id': 'CHK_014', 'testcase_id': 'TC_041'},
    {'tp_id': 'TP_016', 'checker_id': 'CHK_014', 'testcase_id': 'TC_042, TC_043, TC_044, TC_045'},
]

# ============================================================
# Main Generation Function
# ============================================================

def generate_rtm(input_file, output_file):
    """Generate new RTM with Checkers and Testcases"""

    # Copy input file to output
    shutil.copy(input_file, output_file)

    # Load workbook
    wb = load_workbook(output_file)

    # Add Checkers
    ws_checker = wb['Checker List']
    next_row = 3
    for checker in CHECKERS:
        ws_checker.cell(row=next_row, column=1, value=checker['chk_id'])
        ws_checker.cell(row=next_row, column=2, value=checker['chk_name'])
        ws_checker.cell(row=next_row, column=3, value=checker['chk_description'])
        next_row += 1

    # Add Testcases
    ws_tc = wb['DV Testcase List']
    next_row = 3
    for tc in TESTCASES:
        ws_tc.cell(row=next_row, column=1, value=tc['tc_id'])
        ws_tc.cell(row=next_row, column=2, value=tc['tc_name'])
        ws_tc.cell(row=next_row, column=3, value=tc['tc_description'])
        next_row += 1

    # Update FL-TP links
    ws_fltp = wb['FL-TP']
    for row in range(3, ws_fltp.max_row + 1):
        tp_id = ws_fltp.cell(row=row, column=3).value
        if tp_id:
            for link in FL_TP_LINKS:
                if link['tp_id'] == tp_id:
                    ws_fltp.cell(row=row, column=5, value=link['checker_id'])
                    ws_fltp.cell(row=row, column=6, value=link['testcase_id'])
                    break

    # Save workbook
    wb.save(output_file)
    print(f"Generated RTM: {output_file}")
    print(f"  Checkers: {len(CHECKERS)}")
    print(f"  Testcases: {len(TESTCASES)}")

    wb.close()

if __name__ == '__main__':
    input_file = '/home/xingchangchang/ai_evaluation/claude_code/rtm_gen/ai_cc_rtm_gen/TBUS_RTM.xlsx'
    output_file = '/home/xingchangchang/ai_evaluation/claude_code/rtm_gen/ai_cc_rtm_gen/TBUS_RTM_new.xlsx'
    generate_rtm(input_file, output_file)
