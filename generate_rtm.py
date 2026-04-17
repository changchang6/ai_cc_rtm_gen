#!/usr/bin/env python3
"""
RTM Generator - Generate Checker List and DV Testcase List for APLC-Lite
Based on RTM_AI.xlsx and TBUS_LRS_v1.1.docx
"""

import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from copy import copy
import os

# Checker definitions - passive, monitoring type
CHECKERS = [
    {
        "chk_id": "CHK_001",
        "chk_name": "clk_freq_checker",
        "chk_description": """检查clk_i时钟频率和稳定性：
1.频率检查：连续采集clk_i上升沿和下降沿，计算实际频率/周期，判断是否处于目标频率100MHz的允许误差范围内（±1%）；
2.稳定性检查：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内；
3.时钟域同步：验证协议采样、状态机控制和AHB-Lite主接口均在clk_i上升沿同步工作。""",
        "note": "覆盖TP_001"
    },
    {
        "chk_id": "CHK_002",
        "chk_name": "reset_checker",
        "chk_description": """检查rst_ni复位行为正确性：
1.复位有效检查：rst_ni为低时，状态机应处于IDLE状态；
2.复位释放检查：rst_ni释放后，验证内部同步释放机制；
3.默认值检查：复位后CTRL.EN=0，CTRL.LANE_MODE=00(1-bit模式)；
4.状态清零检查：复位后STATUS寄存器和LAST_ERR寄存器清零，协议上下文和错误状态已清空。""",
        "note": "覆盖TP_002"
    },
    {
        "chk_id": "CHK_003",
        "chk_name": "csr_reg_checker",
        "chk_description": """检查CSR寄存器读写正确性：
1.VERSION寄存器：读取值应返回预期版本号；
2.CTRL寄存器：EN、LANE_MODE、SOFT_RST字段读写正确，写入配置后读取值与写入一致；
3.STATUS寄存器：busy位和sticky位反映正确状态；
4.LAST_ERR寄存器：正确记录最近发生的错误码。""",
        "note": "覆盖TP_003"
    },
    {
        "chk_id": "CHK_004",
        "chk_name": "work_mode_checker",
        "chk_description": """检查工作模式和lane模式配置正确性：
1.使能检查：test_mode_i=1且CTRL.EN=1时，模块允许执行功能命令；
2.lane模式检查：LANE_MODE=00时使用1-bit模式(pdi_i[0]/pdo_o[0])，LANE_MODE=01时使用4-bit模式(pdi_i[3:0]/pdo_o[3:0])；
3.半双工检查：请求阶段由主机驱动pdi_i，响应阶段由模块驱动pdo_o，pdo_oe_o正确指示方向切换；
4.不支持功能检查：验证Burst和AXI后端功能确认不可用。""",
        "note": "覆盖TP_004, TP_005"
    },
    {
        "chk_id": "CHK_005",
        "chk_name": "data_interface_checker",
        "chk_description": """检查数据接口时序和格式正确性：
1.帧边界检查：pcs_n_i=1表示空闲，pcs_n_i拉低开启事务，pcs_n_i拉高结束事务；
2.数据顺序检查：协议字段按MSB first传输；
3.lane模式检查：1-bit模式使用bit0，4-bit模式按高nibble优先发送；
4.turnaround检查：请求阶段与响应阶段之间固定插入1个clk_i周期的turnaround；
5.方向控制检查：响应期间pdo_oe_o=1，非响应期间pdo_oe_o=0。""",
        "note": "覆盖TP_006, TP_007"
    },
    {
        "chk_id": "CHK_006",
        "chk_name": "opcode_checker",
        "chk_description": """检查opcode译码正确性：
1.合法opcode检查：0x10译码为WR_CSR，0x11译码为RD_CSR，0x20译码为AHB_WR32，0x21译码为AHB_RD32；
2.帧长确定检查：前端收满8bit opcode后正确确定期望帧长；
3.非法opcode检查：非法opcode(如0x00/0xFF)应返回STS_BAD_OPCODE(0x01)。""",
        "note": "覆盖TP_008"
    },
    {
        "chk_id": "CHK_007",
        "chk_name": "ctrl_config_checker",
        "chk_description": """检查CTRL寄存器配置生效正确性：
1.EN字段检查：CTRL.EN=1使能模块功能，CTRL.EN=0禁用模块；
2.LANE_MODE字段检查：仅允许00=1-bit、01=4-bit，其他值应返回错误；
3.SOFT_RST字段检查：SOFT_RST写1触发协议上下文清零并恢复默认lane模式(1-bit)；
4.配置生效时序检查：配置在下一个事务生效。""",
        "note": "覆盖TP_009"
    },
    {
        "chk_id": "CHK_008",
        "chk_name": "status_polling_checker",
        "chk_description": """检查状态查询机制正确性：
1.STATUS寄存器检查：busy位反映模块执行状态，sticky位记录历史错误；
2.LAST_ERR寄存器检查：正确记录最近错误码(0x00~0x08)；
3.无中断检查：MVP版本无独立中断输出，所有状态通过轮询获取。""",
        "note": "覆盖TP_010"
    },
    {
        "chk_id": "CHK_009",
        "chk_name": "exception_checker",
        "chk_description": """检查异常检测和状态码返回正确性：
1.BAD_OPCODE(0x01)：非法opcode检测；
2.BAD_REG(0x02)：非法CSR地址检测；
3.ALIGN_ERR(0x03)：非4Byte对齐地址检测；
4.DISABLED(0x04)：CTRL.EN=0时发送命令检测；
5.NOT_IN_TEST(0x05)：test_mode_i=0时发送命令检测；
6.FRAME_ERR(0x06)：pcs_n_i提前拉高帧错误检测；
7.AHB_ERR(0x07)：hresp_i=1错误检测；
8.TIMEOUT(0x08)：AHB超时检测；
9.错误收敛检查：在发起AHB访问前完成前置错误收敛。""",
        "note": "覆盖TP_011"
    },
    {
        "chk_id": "CHK_010",
        "chk_name": "low_power_checker",
        "chk_description": """检查低功耗设计正确性：
1.空闲态检查：pcs_n_i=1时，接收移位寄存器不更新；
2.非发送态检查：非发送阶段，发送移位寄存器不翻转；
3.超时计数器检查：timeout counter仅在AHB等待态工作；
4.测试模式检查：test_mode_i=0时，AHB输出保持IDLE值。""",
        "note": "覆盖TP_012"
    },
    {
        "chk_id": "CHK_011",
        "chk_name": "performance_checker",
        "chk_description": """检查性能指标达标：
1.频率检查：clk_i=100MHz稳定工作；
2.延时检查：4-bit模式下AHB_RD32最小端到端延时约23~24 cycles；
3.吞吐率检查：1-bit模式线速12.5MB/s，4-bit模式线速50MB/s；
4.AHB约束检查：AHB接口32bit字访问，地址4Byte对齐。""",
        "note": "覆盖TP_013"
    },
    {
        "chk_id": "CHK_012",
        "chk_name": "dfx_observer_checker",
        "chk_description": """检查DFX可观测点可访问：
1.状态机状态可观测；
2.opcode、addr、wdata、rdata、status_code可观测；
3.rx/tx计数可观测；
4.pcs_n_i、pdi_i、pdo_o、pdo_oe_o信号可观测。""",
        "note": "覆盖TP_014"
    },
    {
        "chk_id": "CHK_013",
        "chk_name": "memory_map_checker",
        "chk_description": """检查memory map正确性：
1.CSR访问检查：模块内部CSR(VERSION/CTRL/STATUS/LAST_ERR)通过WR_CSR/RD_CSR协议命令访问；
2.CSR隔离检查：模块自身CSR不进入SoC AHB memory map；
3.AHB Master检查：对外AHB-Lite Master访问采用32bit地址空间和word访问粒度。""",
        "note": "覆盖TP_015"
    },
    {
        "chk_id": "CHK_014",
        "chk_name": "ahb_interface_checker",
        "chk_description": """检查AHB-Lite Master接口正确性：
1.htrans_o检查：仅输出IDLE(2'b00)和NONSEQ(2'b10)；
2.hsize_o检查：固定为WORD(3'b010)；
3.hburst_o检查：固定为SINGLE(3'b000)；
4.hwrite_o检查：写命令为高，读命令为低；
5.haddr_o检查：地址4Byte对齐；
6.hwdata_o/hrdata_i检查：32bit数据正确传输；
7.hready_i/hresp_i检查：正确处理响应信号。""",
        "note": "覆盖TP_016"
    }
]

# Testcase definitions - active, driving type
TESTCASES = [
    {
        "tc_id": "TC_001",
        "tc_name": "clk_domain_sync_test",
        "tc_description": """配置条件：
1.配置clk_i时钟频率为100MHz；
2.配置test_mode_i=1，通过WR_CSR(0x10)设置CTRL.EN=1；
3.分别配置LANE_MODE=00(1-bit)和LANE_MODE=01(4-bit)。

输入激励：
1.在1-bit模式下，连续发送AHB_RD32(0x21)和AHB_WR32(0x20)命令各100次；
2.在4-bit模式下，重复上述测试；
3.随机插入idle周期，验证时钟稳定性。

期望结果：
1.所有命令在100MHz频率下正确执行；
2.协议采样、状态机控制和AHB-Lite主接口同域工作正常；
3.无时序违例，无数据丢失。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_001"
    },
    {
        "tc_id": "TC_002",
        "tc_name": "reset_behavior_test",
        "tc_description": """配置条件：
1.初始状态rst_ni为低，模块处于复位状态；
2.时钟clk_i稳定运行。

输入激励：
1.释放rst_ni，等待同步释放完成；
2.通过RD_CSR(0x11)读取CTRL寄存器，验证EN=0、LANE_MODE=00；
3.通过RD_CSR读取STATUS和LAST_ERR寄存器，验证清零；
4.验证状态机处于IDLE状态；
5.反复复位释放10次，验证复位行为一致性。

期望结果：
1.复位后状态机处于IDLE；
2.CTRL.EN=0，CTRL.LANE_MODE=00(1-bit)；
3.STATUS=0x00，LAST_ERR=0x00；
4.协议上下文和错误状态已清空，无残留状态。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_002"
    },
    {
        "tc_id": "TC_003",
        "tc_name": "csr_access_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1；
2.通过WR_CSR(0x10)设置CTRL.EN=1使能模块。

输入激励：
1.通过RD_CSR(0x11)读取VERSION寄存器，验证版本号；
2.通过WR_CSR写入CTRL.EN=1，LANE_MODE=01，验证配置生效；
3.通过RD_CSR读取CTRL寄存器，验证写入正确；
4.写入CTRL.SOFT_RST=1触发软复位，验证恢复默认值；
5.随机读写STATUS和LAST_ERR寄存器，验证sticky位行为。

期望结果：
1.VERSION寄存器返回预期版本号；
2.CTRL配置正确写入和读取；
3.SOFT_RST触发后恢复默认lane模式；
4.STATUS/LAST_ERR反映正确状态。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_003"
    },
    {
        "tc_id": "TC_004",
        "tc_name": "work_mode_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，通过WR_CSR(0x10)设置CTRL.EN=1；
2.分别配置LANE_MODE=00(1-bit)和LANE_MODE=01(4-bit)。

输入激励：
1.在test_mode_i=1时，发送WR_CSR配置lane模式，发送AHB_WR32/AHB_RD32命令；
2.在test_mode_i=0时，发送功能命令，验证返回NOT_IN_TEST错误(0x05)；
3.在CTRL.EN=0时，发送功能命令，验证返回DISABLED错误(0x04)；
4.尝试配置非法LANE_MODE值(02/03)，验证错误处理；
5.验证半双工请求/响应模式：请求阶段pdo_oe_o=0，响应阶段pdo_oe_o=1。

期望结果：
1.test_mode_i=1且CTRL.EN=1时，命令正确执行；
2.test_mode_i=0时，返回STS_NOT_IN_TEST(0x05)；
3.CTRL.EN=0时，返回STS_DISABLED(0x04)；
4.非法LANE_MODE值返回错误；
5.Burst和AXI功能确认不可用。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_004, TP_005"
    },
    {
        "tc_id": "TC_005",
        "tc_name": "data_interface_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.分别配置LANE_MODE=00(1-bit)和LANE_MODE=01(4-bit)。

输入激励：
1.在1-bit模式下发送WR_CSR(0x10)命令，验证pdi_i[0]/pdo_o[0]数据传输；
2.在4-bit模式下发送相同命令，验证pdi_i[3:0]/pdo_o[3:0]按高nibble优先发送；
3.验证pcs_n_i帧边界：拉低开启事务，拉高结束事务；
4.验证MSB first传输顺序。

期望结果：
1.1-bit模式正确使用bit0传输；
2.4-bit模式按高nibble优先发送；
3.pcs_n_i正确标记帧边界；
4.数据按MSB first顺序传输。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_006"
    },
    {
        "tc_id": "TC_006",
        "tc_name": "protocol_timing_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.配置LANE_MODE=01(4-bit模式)。

输入激励：
1.发送WR_CSR(0x10)命令，记录请求阶段结束时刻；
2.验证turnaround周期为1个clk_i周期；
3.检查pdo_oe_o在turnaround后置1；
4.依次发送四种命令：WR_CSR(0x10)、RD_CSR(0x11)、AHB_WR32(0x20)、AHB_RD32(0x21)；
5.测量每种命令的端到端延时。

期望结果：
1.请求阶段与响应阶段正确分离；
2.turnaround固定1周期；
3.pdo_oe_o在响应阶段置1；
4.协议字段MSB first传输；
5.四种帧格式正确处理。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_007"
    },
    {
        "tc_id": "TC_007",
        "tc_name": "opcode_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.AHB总线空闲。

输入激励：
1.发送opcode=0x10(WR_CSR)，验证CSR写功能；
2.发送opcode=0x11(RD_CSR)，验证CSR读功能；
3.发送opcode=0x20(AHB_WR32)，验证AHB单次写功能；
4.发送opcode=0x21(AHB_RD32)，验证AHB单次读功能；
5.发送非法opcode(0x00/0xFF/0x30/0x0F等)，验证错误返回；
6.随机生成100个非法opcode，验证全部返回STS_BAD_OPCODE(0x01)。

期望结果：
1.四种合法opcode正确译码并执行；
2.非法opcode返回STS_BAD_OPCODE(0x01)；
3.前端收满8bit后正确确定期望帧长。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_008"
    },
    {
        "tc_id": "TC_008",
        "tc_name": "ctrl_config_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1；
2.模块初始状态禁用(CTRL.EN=0)。

输入激励：
1.写CTRL.EN=1使能模块，发送功能命令验证可执行；
2.写CTRL.EN=0禁用模块，发送命令验证返回DISABLED(0x04)；
3.配置LANE_MODE=00验证1-bit模式工作；
4.配置LANE_MODE=01验证4-bit模式工作；
5.尝试配置LANE_MODE=10/11，验证非法配置处理；
6.写CTRL.SOFT_RST=1触发软复位，验证协议上下文清零；
7.软复位后验证恢复默认lane模式(1-bit)。

期望结果：
1.EN使能/禁用状态切换正确；
2.LANE_MODE=00/01配置生效；
3.非法LANE_MODE返回错误；
4.SOFT_RST触发协议上下文清零；
5.恢复默认1-bit模式。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_009"
    },
    {
        "tc_id": "TC_009",
        "tc_name": "status_polling_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.准备触发各类错误条件。

输入激励：
1.触发非法opcode错误，通过RD_CSR读取STATUS寄存器sticky位；
2.读取LAST_ERR寄存器验证错误码更新；
3.依次触发各类错误(BAD_REG/ALIGN_ERR/DISABLED/NOT_IN_TEST/FRAME_ERR/AHB_ERR/TIMEOUT)；
4.验证无独立中断输出信号；
5.模拟ATE轮询方式获取状态。

期望结果：
1.STATUS寄存器sticky位正确记录历史错误；
2.LAST_ERR正确记录最近错误码；
3.MVP版本无中断输出；
4.轮询方式正确获取状态。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_010"
    },
    {
        "tc_id": "TC_010",
        "tc_name": "exception_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.AHB总线正常响应。

输入激励：
1.发送非法opcode(0x00/0xFF)验证BAD_OPCODE(0x01)；
2.访问非法CSR地址(如0xFC)验证BAD_REG(0x02)；
3.发送非4Byte对齐地址(如0x01)验证ALIGN_ERR(0x03)；
4.设置CTRL.EN=0后发送命令验证DISABLED(0x04)；
5.设置test_mode_i=0后发送命令验证NOT_IN_TEST(0x05)；
6.在请求阶段提前拉高pcs_n_i验证FRAME_ERR(0x06)；
7.配置hresp_i=1模拟AHB错误验证AHB_ERR(0x07)；
8.模拟hready_i长时间为0验证TIMEOUT(0x08)；
9.验证所有错误在发起AHB访问前完成收敛。

期望结果：
1.各类错误正确检测并返回对应状态码；
2.LAST_ERR更新正确；
3.错误在AHB访问前收敛，不发起错误AHB访问。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_011"
    },
    {
        "tc_id": "TC_011",
        "tc_name": "low_power_test",
        "tc_description": """配置条件：
1.模块初始处于空闲态(test_mode_i=0或pcs_n_i=1)。

输入激励：
1.保持pcs_n_i=1，观察接收移位寄存器是否翻转；
2.模拟AHB等待态，观察超时计数器是否工作；
3.设置test_mode_i=0，验证AHB输出保持IDLE；
4.切换到工作态，验证关键寄存器翻转；
5.测量空闲态和工作态的翻转活动差异。

期望结果：
1.pcs_n_i=1时接收移位寄存器不翻转；
2.超时计数器仅在AHB等待态工作；
3.test_mode_i=0时AHB输出IDLE；
4.空闲态翻转最小化，低功耗目标满足。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_012"
    },
    {
        "tc_id": "TC_012",
        "tc_name": "performance_test",
        "tc_description": """配置条件：
1.配置clk_i=100MHz；
2.AHB总线hready_i=1正常响应。

输入激励：
1.在1-bit模式下连续执行AHB_RD32/AHB_WR32命令各100次，计算端到端延时；
2.在4-bit模式下执行相同测试，测量延时；
3.计算吞吐率：1-bit模式和4-bit模式；
4.发送非4Byte对齐地址，验证AHB访问约束；
5.测量状态机各阶段延时分布。

期望结果：
1.100MHz稳定工作；
2.4-bit模式AHB_RD32最小延时约23~24 cycles；
3.1-bit模式线速≈12.5MB/s，4-bit模式≈50MB/s；
4.AHB访问32bit字粒度，4Byte对齐约束满足。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_013"
    },
    {
        "tc_id": "TC_013",
        "tc_name": "dfx_test",
        "tc_description": """配置条件：
1.仿真环境，配置test_mode_i=1，CTRL.EN=1。

输入激励：
1.执行多种命令序列(包含所有四种opcode)；
2.采集状态机状态信号；
3.采集opcode、addr、wdata、rdata、status_code；
4.采集rx/tx计数；
5.采集pcs_n_i、pdi_i、pdo_o、pdo_oe_o；
6.触发各类错误，观察调试可观测点。

期望结果：
1.状态机状态可观测；
2.所有内部调试信号可采集；
3.便于联调、波形定位和故障复现。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_014"
    },
    {
        "tc_id": "TC_014",
        "tc_name": "memory_map_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1。

输入激励：
1.通过WR_CSR/RD_CSR访问VERSION寄存器，验证CSR路径；
2.通过WR_CSR/RD_CSR访问CTRL、STATUS、LAST_ERR寄存器；
3.发送AHB_WR32/AHB_RD32命令访问SoC内部memory-mapped地址；
4.验证模块自身CSR不通过AHB地址空间访问；
5.验证AHB Master使用32bit地址空间和word访问粒度。

期望结果：
1.CSR通过协议命令正确访问；
2.模块CSR不进入SoC AHB memory map；
3.AHB Master访问正确，地址空间约束满足。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_015"
    },
    {
        "tc_id": "TC_015",
        "tc_name": "ahb_interface_test",
        "tc_description": """配置条件：
1.配置test_mode_i=1，CTRL.EN=1；
2.AHB总线hready_i=1，hresp_i=0正常响应。

输入激励：
1.发送AHB_WR32(0x20)命令，验证haddr_o/hwrite_o/htrans_o/hsize_o/hburst_o/hwdata_o输出；
2.发送AHB_RD32(0x21)命令，验证hrdata_i输入正确接收；
3.验证htrans_o仅输出IDLE(2'b00)和NONSEQ(2'b10)；
4.验证hsize_o固定为WORD(3'b010)；
5.验证hburst_o固定为SINGLE(3'b000)；
6.模拟hready_i=0等待态，验证模块行为；
7.模拟hresp_i=1错误响应，验证错误处理。

期望结果：
1.AHB信号输出符合AHB-Lite协议规范；
2.htrans_o仅IDLE/NONSEQ；
3.hsize_o=WORD，hburst_o=SINGLE；
4.hready_i等待和hresp_i错误正确处理。

coverage check点：
直接用例覆盖，不收功能覆盖率。""",
        "note": "覆盖TP_016"
    }
]

# FL-TP link mapping
TP_TO_CHECKER = {
    "TP_001": "CHK_001",
    "TP_002": "CHK_002",
    "TP_003": "CHK_003",
    "TP_004": "CHK_004",
    "TP_005": "CHK_004",
    "TP_006": "CHK_005",
    "TP_007": "CHK_005",
    "TP_008": "CHK_006",
    "TP_009": "CHK_007",
    "TP_010": "CHK_008",
    "TP_011": "CHK_009",
    "TP_012": "CHK_010",
    "TP_013": "CHK_011",
    "TP_014": "CHK_012",
    "TP_015": "CHK_013",
    "TP_016": "CHK_014"
}

TP_TO_TESTCASE = {
    "TP_001": "TC_001",
    "TP_002": "TC_002",
    "TP_003": "TC_003",
    "TP_004": "TC_004",
    "TP_005": "TC_004",
    "TP_006": "TC_005",
    "TP_007": "TC_006",
    "TP_008": "TC_007",
    "TP_009": "TC_008",
    "TP_010": "TC_009",
    "TP_011": "TC_010",
    "TP_012": "TC_011",
    "TP_013": "TC_012",
    "TP_014": "TC_013",
    "TP_015": "TC_014",
    "TP_016": "TC_015"
}


def copy_cell_style(src_cell, dst_cell):
    """Copy cell style from source to destination."""
    if src_cell.has_style:
        dst_cell.font = copy(src_cell.font)
        dst_cell.border = copy(src_cell.border)
        dst_cell.fill = copy(src_cell.fill)
        dst_cell.number_format = src_cell.number_format
        dst_cell.protection = copy(src_cell.protection)
        dst_cell.alignment = copy(src_cell.alignment)


def find_instruction_row(ws):
    """Find the row where 填写要求 starts."""
    for row in range(1, ws.max_row + 1):
        val = ws.cell(row=row, column=1).value
        if val and '填写要求' in str(val):
            return row
    return ws.max_row + 1


def save_instruction_section(ws, start_row):
    """Save the instruction section content and merged cells info."""
    instruction_content = []
    merged_ranges = list(ws.merged_cells.ranges)

    for row in range(start_row, ws.max_row + 1):
        row_data = []
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            row_data.append({
                'value': cell.value,
                'font': copy(cell.font) if cell.has_style else None,
                'border': copy(cell.border) if cell.has_style else None,
                'fill': copy(cell.fill) if cell.has_style else None,
                'alignment': copy(cell.alignment) if cell.has_style else None
            })
        instruction_content.append(row_data)

    # Save which merged cells are in instruction section
    instruction_merges = []
    for merge in merged_ranges:
        if merge.min_row >= start_row:
            instruction_merges.append(merge)

    return instruction_content, instruction_merges


def restore_instruction_section(ws, start_row, content, merges):
    """Restore the instruction section at new location."""
    # Clear old merged cells in the section
    for merge in merges:
        try:
            ws.unmerge_cells(str(merge))
        except:
            pass

    # Write content
    for i, row_data in enumerate(content):
        for j, cell_data in enumerate(row_data):
            cell = ws.cell(row=start_row + i, column=j + 1)
            cell.value = cell_data['value']
            if cell_data['font']:
                cell.font = cell_data['font']
            if cell_data['border']:
                cell.border = cell_data['border']
            if cell_data['fill']:
                cell.fill = cell_data['fill']
            if cell_data['alignment']:
                cell.alignment = cell_data['alignment']

    # Restore merged cells at new positions
    for merge in merges:
        new_range = openpyxl.utils.range_boundaries(str(merge))
        # Adjust row numbers
        row_offset = start_row - merge.min_row + len(content)
        try:
            ws.merge_cells(
                start_row=merge.min_row + row_offset - len(content),
                start_column=new_range[1],
                end_row=merge.max_row + row_offset - len(content),
                end_column=new_range[3]
            )
        except:
            pass


def generate_rtm(input_path, output_path):
    """Generate new RTM file with Checker List and DV Testcase List."""
    # Load source workbook
    wb = openpyxl.load_workbook(input_path)

    # ============= Checker List =============
    ws_checker = wb['Checker List']

    # Find where 填写要求 starts
    instruction_row_checker = find_instruction_row(ws_checker)
    print(f"Checker List 填写要求 at row {instruction_row_checker}")

    # Save instruction section
    instruction_content_checker, instruction_merges_checker = save_instruction_section(
        ws_checker, instruction_row_checker
    )

    # Unmerge all cells in instruction section
    for merge in instruction_merges_checker:
        try:
            ws_checker.unmerge_cells(str(merge))
        except:
            pass

    # Delete old instruction rows
    if instruction_row_checker <= ws_checker.max_row:
        ws_checker.delete_rows(instruction_row_checker, ws_checker.max_row - instruction_row_checker + 1)

    # Add checkers (starting from row 3)
    for i, checker in enumerate(CHECKERS):
        row = i + 3
        ws_checker.cell(row=row, column=1, value=checker['chk_id'])
        ws_checker.cell(row=row, column=2, value=checker['chk_name'])
        ws_checker.cell(row=row, column=3, value=checker['chk_description'])
        ws_checker.cell(row=row, column=4, value=checker['note'])
        ws_checker.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical='top')

    # Restore instruction section after checkers
    new_instruction_row = len(CHECKERS) + 3
    restore_instruction_section(ws_checker, new_instruction_row, instruction_content_checker, instruction_merges_checker)

    # ============= DV Testcase List =============
    ws_testcase = wb['DV Testcase List']

    # Find where 填写要求 starts (if exists)
    instruction_row_tc = find_instruction_row(ws_testcase)
    if instruction_row_tc > ws_testcase.max_row:
        # No 填写要求 section
        instruction_content_tc = []
        instruction_merges_tc = []
    else:
        print(f"DV Testcase List 填写要求 at row {instruction_row_tc}")
        instruction_content_tc, instruction_merges_tc = save_instruction_section(
            ws_testcase, instruction_row_tc
        )
        # Unmerge cells
        for merge in instruction_merges_tc:
            try:
                ws_testcase.unmerge_cells(str(merge))
            except:
                pass
        # Delete old instruction rows
        if instruction_row_tc <= ws_testcase.max_row:
            ws_testcase.delete_rows(instruction_row_tc, ws_testcase.max_row - instruction_row_tc + 1)

    # Add testcases (starting from row 3)
    for i, testcase in enumerate(TESTCASES):
        row = i + 3
        ws_testcase.cell(row=row, column=1, value=testcase['tc_id'])
        ws_testcase.cell(row=row, column=2, value=testcase['tc_name'])
        ws_testcase.cell(row=row, column=3, value=testcase['tc_description'])
        ws_testcase.cell(row=row, column=4, value=testcase['note'])
        ws_testcase.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical='top')

    # Restore instruction section after testcases
    if instruction_content_tc:
        new_instruction_row_tc = len(TESTCASES) + 3
        restore_instruction_section(ws_testcase, new_instruction_row_tc, instruction_content_tc, instruction_merges_tc)

    # Update FL-TP links
    if 'FL-TP' in wb.sheetnames:
        ws_fltp = wb['FL-TP']
        for row in range(3, ws_fltp.max_row + 1):
            tp_id = ws_fltp.cell(row=row, column=3).value  # TP编号在column 3
            if tp_id and tp_id in TP_TO_CHECKER:
                ws_fltp.cell(row=row, column=5, value=TP_TO_CHECKER[tp_id])  # checker_id
                ws_fltp.cell(row=row, column=6, value=TP_TO_TESTCASE[tp_id])  # testcase_id

    # Adjust column widths
    ws_checker.column_dimensions['A'].width = 12
    ws_checker.column_dimensions['B'].width = 25
    ws_checker.column_dimensions['C'].width = 80
    ws_checker.column_dimensions['D'].width = 15

    ws_testcase.column_dimensions['A'].width = 12
    ws_testcase.column_dimensions['B'].width = 25
    ws_testcase.column_dimensions['C'].width = 80
    ws_testcase.column_dimensions['D'].width = 15

    # Save workbook
    wb.save(output_path)
    print(f"RTM file generated: {output_path}")
    print(f"Checkers: {len(CHECKERS)}")
    print(f"Testcases: {len(TESTCASES)}")

    wb.close()


if __name__ == '__main__':
    input_file = 'RTM_AI.xlsx'
    output_file = 'RTM_AI_generated.xlsx'

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        exit(1)

    generate_rtm(input_file, output_file)
