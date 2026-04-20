#!/usr/bin/env python3
"""
TBUS (APLC-Lite) RTM Generator
Generates Checker List and DV Testcase List based on LRS specification.
Properly preserves template formatting, borders, and merged cells.
"""

import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from copy import copy
import os

# =============================================================================
# Checker Definitions - Based on LRS TBUS specification
# =============================================================================
CHECKERS = {
    "CHK_001": {
        "name": "clk_freq_check",
        "description": """1.检查频率值是否正确：连续采集clk_i时钟上升沿和下降沿并计算实际频率/周期，判断是否处于目标频率的允许误差范围内（100MHz ±1%）；
2.检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内。"""
    },
    "CHK_002": {
        "name": "reset_check",
        "description": """在rst_ni释放后的每个cycle，检查模块复位状态：
1.状态机处于IDLE状态；
2.CTRL.EN=0（模块未使能）；
3.CTRL.LANE_MODE=00（默认1-bit模式）；
4.STATUS寄存器全0（BUSY=0, RESP_VALID=0, CMD_ERR=0, BUS_ERR=0, FRAME_ERR=0）；
5.LAST_ERR寄存器=0x00；
6.协议上下文和错误状态已清空。"""
    },
    "CHK_003": {
        "name": "csr_access_check",
        "description": """检查CSR寄存器访问正确性：
1.VERSION寄存器(0x00)：只读，返回版本号值；
2.CTRL寄存器(0x04)：可读写，检查EN[0]、LANE_MODE[2:1]、SOFT_RST[3]字段读写正确；
3.STATUS寄存器(0x08)：只读，检查BUSY[0]、RESP_VALID[1]、CMD_ERR[2]、BUS_ERR[3]、FRAME_ERR[4]、IN_TEST_MODE[5]、OUT_EN[6]字段反映正确状态；
4.LAST_ERR寄存器(0x0C)：只读，记录最近错误码；
5.非法CSR地址返回STS_BAD_REG(0x02)。"""
    },
    "CHK_004": {
        "name": "test_mode_check",
        "description": """检查测试模式工作条件：
1.test_mode_i=1且CTRL.EN=1时，模块允许执行功能命令；
2.test_mode_i=0时，任何命令返回STS_NOT_IN_TEST(0x05)；
3.CTRL.EN=0时，任何命令返回STS_DISABLED(0x04)；
4.半双工请求/响应模式正常工作，pcs_n_i定义帧边界。"""
    },
    "CHK_005": {
        "name": "lane_mode_check",
        "description": """检查lane模式切换正确性：
1.LANE_MODE=00时，使用pdi_i[0]/pdo_o[0]进行1-bit传输；
2.LANE_MODE=01时，使用pdi_i[3:0]/pdo_o[3:0]进行4-bit传输，按高nibble优先发送；
3.LANE_MODE=02/03时，返回错误或忽略；
4.事务执行期间不允许动态切换lane mode；
5.不支持8-bit/16-bit模式（MVP限制）。"""
    },
    "CHK_006": {
        "name": "data_interface_check",
        "description": """检查数据接口传输正确性：
1.pcs_n_i=1表示空闲，拉低后开始接收请求；
2.1-bit模式：仅使用pdi_i[0]/pdo_o[0]，每拍传输1bit；
3.4-bit模式：使用pdi_i[3:0]/pdo_o[3:0]，每拍传输4bit，MSB first；
4.pdo_oe_o在响应阶段输出高电平，指示模块驱动pdo_o；
5.数据按MSB first顺序传输。"""
    },
    "CHK_007": {
        "name": "protocol_timing_check",
        "description": """检查协议时序正确性：
1.请求阶段：ATE驱动pdi_i输入数据；
2.turnaround阶段：固定1个clk_i周期，pdo_oe_o=0；
3.响应阶段：pdo_oe_o=1，模块驱动pdo_o输出status+rdata；
4.写类命令响应：STATUS[7:0]（8bit）；
5.读类命令响应：STATUS[7:0] + RDATA[31:0]（40bit）；
6.pcs_n_i在请求未收满时提前拉高产生帧错误STS_FRAME_ERR(0x06)。"""
    },
    "CHK_008": {
        "name": "opcode_decode_check",
        "description": """检查opcode译码正确性：
1.opcode=0x10 WR_CSR：CSR写命令，帧格式为opcode+addr+wdata；
2.opcode=0x11 RD_CSR：CSR读命令，帧格式为opcode+addr；
3.opcode=0x20 AHB_WR32：AHB单次写命令，帧格式为opcode+addr+wdata；
4.opcode=0x21 AHB_RD32：AHB单次读命令，帧格式为opcode+addr；
5.非法opcode（非0x10/0x11/0x20/0x21）返回STS_BAD_OPCODE(0x01)；
6.前端收满8bit opcode后确定期望帧长。"""
    },
    "CHK_009": {
        "name": "ctrl_config_check",
        "description": """检查CTRL寄存器配置生效：
1.CTRL.EN=1：模块使能，允许执行命令；
2.CTRL.EN=0：模块禁用，命令返回STS_DISABLED(0x04)；
3.CTRL.LANE_MODE=00：1-bit模式；
4.CTRL.LANE_MODE=01：4-bit模式；
5.CTRL.LANE_MODE=10/11：保留，不切换或返回错误；
6.CTRL.SOFT_RST写1：触发软复位，清零协议上下文，恢复LANE_MODE=00默认值。"""
    },
    "CHK_010": {
        "name": "status_polling_check",
        "description": """检查状态查询机制：
1.STATUS[0] BUSY：当前有事务执行时置1；
2.STATUS[1] RESP_VALID：最近响应有效时置1；
3.STATUS[2] CMD_ERR：命令错误时置1（sticky）；
4.STATUS[3] BUS_ERR：总线错误时置1（sticky）；
5.STATUS[4] FRAME_ERR：帧错误时置1（sticky）；
6.STATUS[5] IN_TEST_MODE：镜像test_mode_i输入；
7.STATUS[6] OUT_EN：镜像pdo_oe_o输出使能；
8.LAST_ERR记录最近错误码（0x00~0x08）；
9.MVP版本无独立中断输出，通过轮询STATUS/LAST_ERR获取状态。"""
    },
    "CHK_011": {
        "name": "error_handling_check",
        "description": """检查异常检测与处理：
1.STS_BAD_OPCODE(0x01)：opcode非0x10/0x11/0x20/0x21；
2.STS_BAD_REG(0x02)：CSR地址非0x00/0x04/0x08/0x0C；
3.STS_ALIGN_ERR(0x03)：AHB地址非4Byte对齐；
4.STS_DISABLED(0x04)：CTRL.EN=0时发送命令；
5.STS_NOT_IN_TEST(0x05)：test_mode_i=0时发送命令；
6.STS_FRAME_ERR(0x06)：pcs_n_i提前拉高或帧长度不匹配；
7.STS_AHB_ERR(0x07)：hresp_i=1错误响应；
8.STS_TIMEOUT(0x08)：AHB等待超时（默认1024 cycles）；
9.错误在发起AHB访问前完成前置错误收敛；
10.LAST_ERR更新为最近错误码。"""
    },
    "CHK_012": {
        "name": "low_power_check",
        "description": """检查低功耗设计行为：
1.pcs_n_i=1空闲态时，接收移位寄存器不更新；
2.非发送阶段，发送移位寄存器不翻转；
3.timeout counter仅在AHB等待态工作；
4.test_mode_i=0时，AHB输出保持IDLE（htrans_o=IDLE）；
5.仅在RX/TX/WAIT_AHB相关状态翻转关键寄存器。"""
    },
    "CHK_013": {
        "name": "performance_check",
        "description": """检查性能指标：
1.目标频率：clk_i=100MHz稳定工作；
2.AHB_RD32端到端延时：约23~24 cycles（请求10+译码2+AHB 1~N+turnaround 1+响应10）；
3.AHB_WR32端到端延时：约23 cycles（请求18+执行2+turnaround 1+响应2）；
4.1-bit模式原始链路线速：12.5MB/s；
5.4-bit模式原始链路线速：50MB/s；
6.AHB接口：32bit字访问，地址4Byte对齐。"""
    },
    "CHK_014": {
        "name": "dfx_observable_check",
        "description": """检查调试可观测点：
1.状态机状态可观测；
2.opcode寄存器可观测；
3.addr寄存器可观测；
4.wdata寄存器可观测；
5.rdata寄存器可观测；
6.status_code可观测；
7.rx计数器可观测；
8.tx计数器可观测；
9.关键接口信号可采集：pcs_n_i, pdi_i, pdo_o, pdo_oe_o。"""
    },
    "CHK_015": {
        "name": "memory_map_check",
        "description": """检查存储映射：
1.模块CSR通过协议命令访问，不进入SoC AHB memory map；
2.CSR地址映射：VERSION(0x00), CTRL(0x04), STATUS(0x08), LAST_ERR(0x0C)；
3.AHB Master使用32bit地址空间；
4.AHB Master访问粒度为word（32bit）；
5.AHB目标地址范围由SoC顶层约束。"""
    },
    "CHK_016": {
        "name": "ahb_interface_check",
        "description": """检查AHB-Lite Master接口合规性：
1.haddr_o：32bit地址输出；
2.hwrite_o：读写标志，1=写，0=读；
3.htrans_o：仅输出IDLE(2'b00)或NONSEQ(2'b10)；
4.hsize_o：固定为WORD(3'b010)，表示32bit传输；
5.hburst_o：固定为SINGLE(3'b000)，不支持burst；
6.hwdata_o：32bit写数据；
7.hrdata_i：32bit读返回数据；
8.hready_i：ready信号，为0时插入等待态；
9.hresp_i：错误响应，为1时表示错误；
10.地址必须4Byte对齐；
11.不支持outstanding，当前事务完成前不得发起新请求。"""
    }
}

# =============================================================================
# Testcase Definitions
# =============================================================================
TESTCASES = {
    "DV_TC_001": {
        "name": "tbus_clk_freq_test",
        "description": """配置条件：
1.配置clk_i时钟频率为100MHz；
2.test_mode_i=1，CTRL.EN=1；
3.随机配置LANE_MODE为00或01。

输入激励：
1.连续发送AHB_RD32命令读取SoC内部地址；
2.连续发送AHB_WR32命令写入SoC内部地址；
3.覆盖1-bit和4-bit两种lane模式；
4.持续运行足够长时间验证稳定性。

期望结果：
1.所有命令在100MHz频率下正确执行；
2.协议采样、状态机控制和AHB-Lite主接口同域工作正常；
3.时钟频率偏差在±1%范围内；
4.相邻周期频率偏差在3%内。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_002": {
        "name": "tbus_reset_test",
        "description": """配置条件：
1.初始状态rst_ni为低，模块处于复位状态；
2.clk_i稳定运行。

输入激励：
1.释放rst_ni（异步释放，同步释放逻辑）；
2.通过RD_CSR读取CTRL寄存器验证默认值；
3.通过RD_CSR读取STATUS寄存器验证清零；
4.通过RD_CSR读取LAST_ERR寄存器验证清零；
5.检查状态机处于IDLE状态。

期望结果：
1.复位后状态机处于IDLE；
2.CTRL.EN=0（模块未使能）；
3.CTRL.LANE_MODE=00（默认1-bit模式）；
4.STATUS寄存器全0；
5.LAST_ERR寄存器=0x00；
6.协议上下文和错误状态已清空。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_003": {
        "name": "tbus_csr_access_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.配置LANE_MODE=01（4-bit模式）。

输入激励：
1.通过RD_CSR(0x11)读取VERSION寄存器(0x00)，验证版本号；
2.通过WR_CSR(0x10)写CTRL寄存器(0x04)：EN=1, LANE_MODE=01, SOFT_RST=0；
3.通过RD_CSR(0x11)读取CTRL寄存器验证写入正确；
4.通过RD_CSR(0x11)读取STATUS寄存器(0x08)检查状态；
5.通过RD_CSR(0x11)读取LAST_ERR寄存器(0x0C)；
6.尝试访问非法CSR地址(如0x10)验证错误处理。

期望结果：
1.VERSION寄存器返回预期版本号；
2.CTRL寄存器读写正确，EN/LANE_MODE/SOFT_RST字段配置生效；
3.STATUS寄存器反映正确状态：BUSY=0, RESP_VALID=1, IN_TEST_MODE=1；
4.LAST_ERR寄存器正常记录错误；
5.非法CSR地址返回STS_BAD_REG(0x02)。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_004": {
        "name": "tbus_test_mode_test",
        "description": """配置条件：
1.test_mode_i=1；
2.通过WR_CSR设置CTRL.EN=1；
3.配置LANE_MODE为01（4-bit模式）。

输入激励：
1.发送WR_CSR命令配置lane模式；
2.发送AHB_WR32命令进行单次写操作；
3.发送AHB_RD32命令进行单次读操作；
4.验证半双工请求/响应模式：请求阶段ATE驱动pdi_i，响应阶段模块驱动pdo_o；
5.检查pcs_n_i帧边界正确。

期望结果：
1.模块正确执行功能命令；
2.协议采用半双工模式，请求和响应阶段分离；
3.CSR访问与AHB-Lite单次读写正常；
4.pcs_n_i正确定义帧边界；
5.turnaround周期为1个clk_i。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_005": {
        "name": "tbus_lane_mode_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.准备测试1-bit和4-bit模式切换。

输入激励：
1.配置LANE_MODE=00（1-bit模式），发送WR_CSR命令验证pdi_i[0]/pdo_o[0]传输；
2.配置LANE_MODE=01（4-bit模式），发送相同命令验证pdi_i[3:0]/pdo_o[3:0]传输；
3.尝试配置LANE_MODE=10/11验证错误处理或忽略行为；
4.在事务执行期间尝试切换LANE_MODE验证不被接受；
5.验证不支持Burst和AXI后端。

期望结果：
1.1-bit模式正常工作，仅使用bit0传输；
2.4-bit模式正常工作，按高nibble优先发送，MSB first；
3.非法LANE_MODE值不切换或返回错误；
4.事务期间LANE_MODE切换不生效；
5.Burst和AXI功能确认不可用。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_006": {
        "name": "tbus_data_interface_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.配置1-bit和4-bit lane模式进行对比测试。

输入激励：
1.在1-bit模式下(LANE_MODE=00)：发送WR_CSR命令，验证pdi_i[0]/pdo_o[0]数据传输，每拍1bit；
2.在4-bit模式下(LANE_MODE=01)：发送WR_CSR命令，验证pdi_i[3:0]/pdo_o[3:0]数据传输，每拍4bit；
3.验证pcs_n_i帧边界：拉低开始，拉高结束；
4.验证pdo_oe_o输出方向控制：响应阶段为高电平；
5.验证数据MSB first传输顺序。

期望结果：
1.数据接口按lane模式正确传输；
2.帧边界清晰，pcs_n_i正确控制；
3.pdo_oe_o在响应阶段输出高电平；
4.数据按MSB first顺序传输；
5.1-bit和4-bit模式数据内容一致。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_007": {
        "name": "tbus_protocol_timing_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.配置不同lane模式（1-bit和4-bit）。

输入激励：
1.发送WR_CSR(0x10)命令验证请求阶段：pcs_n_i拉低，ATE驱动pdi_i输入opcode+addr+wdata；
2.验证turnaround周期：请求完成后固定1个clk_i周期，pdo_oe_o=0；
3.检查响应阶段：pdo_oe_o=1，模块驱动pdo_o输出STATUS[7:0]；
4.发送RD_CSR(0x11)命令验证读响应：STATUS[7:0] + RDATA[31:0]；
5.发送AHB_WR32(0x20)和AHB_RD32(0x21)验证四种帧格式；
6.模拟帧错误：pcs_n_i在请求未收满时提前拉高。

期望结果：
1.请求/响应阶段正确分离；
2.turnaround固定1周期；
3.协议字段MSB first传输；
4.四种帧格式正确处理；
5.帧错误返回STS_FRAME_ERR(0x06)。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_008": {
        "name": "tbus_opcode_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.AHB总线空闲。

输入激励：
1.发送opcode=0x10执行WR_CSR命令：写CTRL寄存器设置EN=1；
2.发送opcode=0x11执行RD_CSR命令：读STATUS寄存器；
3.发送opcode=0x20执行AHB_WR32命令：写SoC内部地址；
4.发送opcode=0x21执行AHB_RD32命令：读SoC内部地址；
5.发送非法opcode（如0x00/0x12/0xFF）验证错误处理。

期望结果：
1.四种opcode正确译码并执行；
2.WR_CSR正确写CSR寄存器；
3.RD_CSR正确读CSR寄存器；
4.AHB_WR32正确发起AHB写事务；
5.AHB_RD32正确发起AHB读事务；
6.非法opcode返回STS_BAD_OPCODE(0x01)。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_009": {
        "name": "tbus_ctrl_config_test",
        "description": """配置条件：
1.test_mode_i=1；
2.模块初始状态CTRL.EN=0。

输入激励：
1.写CTRL.EN=1使能模块，验证功能命令可执行；
2.发送AHB_RD32命令验证模块正常工作；
3.写CTRL.EN=0禁用模块，发送命令验证返回STS_DISABLED(0x04)；
4.配置LANE_MODE=00验证1-bit模式切换；
5.配置LANE_MODE=01验证4-bit模式切换；
6.写CTRL.SOFT_RST=1触发软复位，验证协议上下文清零并恢复LANE_MODE=00。

期望结果：
1.CTRL.EN=1时模块使能，命令正常执行；
2.CTRL.EN=0时命令返回STS_DISABLED(0x04)；
3.LANE_MODE配置正确切换lane模式；
4.SOFT_RST=1触发软复位，恢复默认状态。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_010": {
        "name": "tbus_status_polling_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.准备执行各类命令并检查状态。

输入激励：
1.执行正常命令，通过RD_CSR读取STATUS寄存器检查BUSY=0, RESP_VALID=1；
2.触发非法opcode错误，读取STATUS检查CMD_ERR=1，读取LAST_ERR=0x01；
3.触发AHB错误(hresp_i=1)，读取STATUS检查BUS_ERR=1，读取LAST_ERR=0x07；
4.触发帧错误，读取STATUS检查FRAME_ERR=1，读取LAST_ERR=0x06；
5.检查STATUS[5] IN_TEST_MODE镜像test_mode_i；
6.检查STATUS[6] OUT_EN镜像pdo_oe_o；
7.验证无独立中断输出。

期望结果：
1.所有错误与完成状态通过STATUS/LAST_ERR查询获取；
2.STATUS字段正确反映模块状态；
3.LAST_ERR记录最近错误码；
4.MVP版本无中断输出，ATE轮询方式正确获取状态。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_011": {
        "name": "tbus_error_handling_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.AHB总线正常响应。

输入激励：
1.发送非法opcode(0x00/0xFF)验证STS_BAD_OPCODE(0x01)，LAST_ERR=0x01；
2.访问非法CSR地址(0x10)验证STS_BAD_REG(0x02)，LAST_ERR=0x02；
3.发送非4Byte对齐地址(0x01)的AHB命令验证STS_ALIGN_ERR(0x03)，LAST_ERR=0x03；
4.CTRL.EN=0时发送命令验证STS_DISABLED(0x04)，LAST_ERR=0x04；
5.test_mode_i=0时发送命令验证STS_NOT_IN_TEST(0x05)，LAST_ERR=0x05；
6.提前拉高pcs_n_i验证STS_FRAME_ERR(0x06)，LAST_ERR=0x06；
7.触发hresp_i=1验证STS_AHB_ERR(0x07)，LAST_ERR=0x07；
8.模拟AHB超时(等待超过1024 cycles)验证STS_TIMEOUT(0x08)，LAST_ERR=0x08。

期望结果：
1.各类错误正确检测；
2.在发起AHB访问前完成前置错误收敛；
3.返回确定性状态码；
4.LAST_ERR更新正确。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_012": {
        "name": "tbus_low_power_test",
        "description": """配置条件：
1.模块处于空闲态(test_mode_i=0或无有效任务)；
2.clk_i稳定运行。

输入激励：
1.保持pcs_n_i=1，观察接收移位寄存器不更新；
2.模拟AHB等待态，验证超时计数器仅在此状态工作；
3.test_mode_i=0时，观察AHB输出保持IDLE(htrans_o=IDLE)；
4.切换到工作态(发送命令)，验证关键寄存器翻转；
5.非发送阶段，观察发送移位寄存器不翻转。

期望结果：
1.空闲态无效翻转最小化；
2.pcs_n_i=1时接收移位寄存器不更新；
3.test_mode_i=0时AHB输出保持IDLE；
4.非发送阶段发送移位寄存器不翻转；
5.超时计数器仅在AHB等待态工作。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_013": {
        "name": "tbus_performance_test",
        "description": """配置条件：
1.配置clk_i=100MHz；
2.AHB总线响应正常(hready_i=1, hresp_i=0)；
3.test_mode_i=1，CTRL.EN=1。

输入激励：
1.在1-bit模式下连续执行AHB_RD32命令，计算端到端延时和吞吐率；
2.在1-bit模式下连续执行AHB_WR32命令，计算端到端延时；
3.在4-bit模式下执行相同测试；
4.验证原始链路线速：1-bit模式12.5MB/s，4-bit模式50MB/s；
5.验证AHB接口32bit字访问和4Byte对齐约束；
6.长时间运行验证稳定性。

期望结果：
1.目标频率100MHz稳定工作；
2.AHB_RD32端到端延时约23~24 cycles；
3.AHB_WR32端到端延时约23 cycles；
4.吞吐率达标；
5.AHB访问约束满足（32bit字访问，4Byte对齐）。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_014": {
        "name": "tbus_dfx_test",
        "description": """配置条件：
1.仿真环境；
2.test_mode_i=1，CTRL.EN=1。

输入激励：
1.执行多种命令序列（WR_CSR, RD_CSR, AHB_WR32, AHB_RD32）；
2.采集状态机状态、opcode、addr、wdata、rdata、status_code；
3.采集rx/tx计数、pcs_n_i、pdi_i、pdo_o、pdo_oe_o；
4.验证内部调试可观测点可访问；
5.模拟错误场景验证调试信息。

期望结果：
1.所有调试可观测点可采集；
2.状态机状态正确反映当前操作阶段；
3.opcode/addr/wdata/rdata正确记录；
4.rx/tx计数正确统计传输数据量；
5.便于联调、波形定位和故障复现。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_015": {
        "name": "tbus_memory_map_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1。

输入激励：
1.通过WR_CSR/RD_CSR访问模块内部CSR寄存器：
   - VERSION(0x00)：读取版本号
   - CTRL(0x04)：配置使能和lane模式
   - STATUS(0x08)：读取状态
   - LAST_ERR(0x0C)：读取最近错误码
2.发送AHB_WR32/AHB_RD32命令访问SoC内部memory-mapped地址；
3.验证模块自身CSR不进入SoC AHB memory map；
4.验证AHB Master访问采用32bit地址空间和word访问粒度。

期望结果：
1.CSR通过协议命令访问正常；
2.AHB Master访问正确；
3.地址空间约束满足；
4.模块CSR不与SoC AHB地址空间冲突。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    },
    "DV_TC_016": {
        "name": "tbus_ahb_interface_test",
        "description": """配置条件：
1.test_mode_i=1，CTRL.EN=1；
2.AHB总线空闲。

输入激励：
1.发送AHB_WR32命令，验证：
   - haddr_o输出正确32bit地址
   - hwrite_o=1（写操作）
   - htrans_o=NONSEQ
   - hsize_o=WORD(3'b010)
   - hburst_o=SINGLE(3'b000)
   - hwdata_o输出正确32bit数据
2.发送AHB_RD32命令，验证：
   - haddr_o输出正确地址
   - hwrite_o=0（读操作）
   - htrans_o=NONSEQ
   - hrdata_i接收正确数据
   - hready_i控制等待
3.模拟hresp_i=1错误响应；
4.模拟hready_i=0插入等待态；
5.验证地址必须4Byte对齐；
6.验证不支持outstanding。

期望结果：
1.AHB-Lite Master接口符合规范；
2.单次读写事务正确；
3.信号时序满足AHB协议要求；
4.hresp_i=1时返回STS_AHB_ERR(0x07)；
5.hready_i=0时正确插入等待态。

coverage check点：
直接用例覆盖，不收功能覆盖率。"""
    }
}


def get_thin_border():
    """Return standard thin border style."""
    thin_side = Side(style='thin')
    return Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)


def apply_cell_style(cell, font_name='宋体', font_size=11, bold=False,
                     h_align='center', v_align='center', wrap_text=False,
                     border_style='thin'):
    """Apply standard cell style."""
    cell.font = Font(name=font_name, size=font_size, bold=bold)
    cell.alignment = Alignment(horizontal=h_align, vertical=v_align, wrap_text=wrap_text)
    if border_style == 'thin':
        cell.border = get_thin_border()


def generate_rtm(template_path, output_path):
    """Generate RTM file with checkers and testcases."""
    print(f"Loading template: {template_path}")
    wb = openpyxl.load_workbook(template_path)

    # =========================================================================
    # Process Checker List sheet
    # =========================================================================
    print("\nProcessing 'Checker List' sheet...")
    ws = wb['Checker List']

    # Template structure (original):
    # Row 1: Title "Checker List" (merged A1:D1)
    # Row 2: Headers (CHK编号, CHK Name, CHK描述, 备注)
    # Rows 3-15: Data rows (some filled, some empty)
    # Row 16: "填写要求" (merged A16:D16)
    # Rows 17-20: Notes (merged cells)

    # We need: 16 checkers (rows 3-18), then notes (rows 19-23)

    # Save original notes content
    notes_content = []
    for row in range(16, 21):
        row_data = []
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            row_data.append({
                'value': cell.value,
                'font': copy(cell.font),
                'border': copy(cell.border),
                'alignment': copy(cell.alignment)
            })
        notes_content.append(row_data)

    # Unmerge all merged cells in Checker List
    merged_ranges = list(ws.merged_cells.ranges)
    for merged_range in merged_ranges:
        ws.unmerge_cells(str(merged_range))
    print(f"  Unmerged {len(merged_ranges)} merged cell ranges")

    # Clear all existing data rows (rows 3 onwards)
    for row in range(3, ws.max_row + 1):
        for col in range(1, 5):
            ws.cell(row=row, column=col).value = None

    # Fill 16 checkers (rows 3-18)
    checker_row = 3
    for chk_id, chk_data in CHECKERS.items():
        # CHK编号
        cell = ws.cell(row=checker_row, column=1, value=chk_id)
        apply_cell_style(cell, h_align='center')

        # CHK Name
        cell = ws.cell(row=checker_row, column=2, value=chk_data['name'])
        apply_cell_style(cell, h_align='center')

        # CHK描述
        cell = ws.cell(row=checker_row, column=3, value=chk_data['description'])
        apply_cell_style(cell, h_align=None, v_align='center', wrap_text=True)

        # 备注
        cell = ws.cell(row=checker_row, column=4, value=None)
        apply_cell_style(cell)

        print(f"  Added {chk_id}: {chk_data['name']}")
        checker_row += 1

    # Add notes section starting at row 19
    notes_start_row = 19
    for i, row_data in enumerate(notes_content):
        row = notes_start_row + i
        for col, cell_data in enumerate(row_data, 1):
            cell = ws.cell(row=row, column=col)
            cell.value = cell_data['value']
            cell.font = cell_data['font']
            cell.border = cell_data['border']
            cell.alignment = cell_data['alignment']

    # Re-merge cells
    # Title: A1:D1
    ws.merge_cells('A1:D1')
    # Notes section
    ws.merge_cells(f'A{notes_start_row}:D{notes_start_row}')  # "填写要求"
    ws.merge_cells(f'B{notes_start_row+1}:D{notes_start_row+1}')  # CHK Name note
    ws.merge_cells(f'B{notes_start_row+2}:D{notes_start_row+2}')  # CHK描述 note
    print(f"  Notes section at rows {notes_start_row}-{notes_start_row+2}")

    # =========================================================================
    # Process DV Testcase List sheet
    # =========================================================================
    print("\nProcessing 'DV Testcase List' sheet...")
    ws_tc = wb['DV Testcase List']

    # Template structure:
    # Row 1: Title "Test Case List" (merged A1:D1)
    # Row 2: Headers (TC编号, TC Name, TC 描述, 备注)
    # Rows 3+: Data rows

    # Unmerge title
    for merged_range in list(ws_tc.merged_cells.ranges):
        ws_tc.unmerge_cells(str(merged_range))

    # Clear existing data rows
    for row in range(3, ws_tc.max_row + 1):
        for col in range(1, 5):
            ws_tc.cell(row=row, column=col).value = None

    # Fill 16 testcases
    tc_row = 3
    for tc_id, tc_data in TESTCASES.items():
        # TC编号
        cell = ws_tc.cell(row=tc_row, column=1, value=tc_id)
        apply_cell_style(cell, h_align='center', font_size=8)

        # TC Name
        cell = ws_tc.cell(row=tc_row, column=2, value=tc_data['name'])
        apply_cell_style(cell, h_align='center', font_size=8)

        # TC描述
        cell = ws_tc.cell(row=tc_row, column=3, value=tc_data['description'])
        apply_cell_style(cell, h_align=None, v_align='center', wrap_text=True, font_size=8)

        # 备注
        cell = ws_tc.cell(row=tc_row, column=4, value=None)
        apply_cell_style(cell, font_size=8)

        print(f"  Added {tc_id}: {tc_data['name']}")
        tc_row += 1

    # Re-merge title
    ws_tc.merge_cells('A1:D1')

    # =========================================================================
    # Update FL-TP sheet links
    # =========================================================================
    print("\nUpdating 'FL-TP' sheet links...")
    ws_fltp = wb['FL-TP']

    # TP to Checker/Testcase mapping
    tp_mapping = {
        "TP_001": ("CHK_001", "DV_TC_001"),
        "TP_002": ("CHK_002", "DV_TC_002"),
        "TP_003": ("CHK_003", "DV_TC_003"),
        "TP_004": ("CHK_004", "DV_TC_004"),
        "TP_005": ("CHK_005", "DV_TC_005"),
        "TP_006": ("CHK_006", "DV_TC_006"),
        "TP_007": ("CHK_007", "DV_TC_007"),
        "TP_008": ("CHK_008", "DV_TC_008"),
        "TP_009": ("CHK_009", "DV_TC_009"),
        "TP_010": ("CHK_010", "DV_TC_010"),
        "TP_011": ("CHK_011", "DV_TC_011"),
        "TP_012": ("CHK_012", "DV_TC_012"),
        "TP_013": ("CHK_013", "DV_TC_013"),
        "TP_014": ("CHK_014", "DV_TC_014"),
        "TP_015": ("CHK_015", "DV_TC_015"),
        "TP_016": ("CHK_016", "DV_TC_016"),
    }

    # Update links for rows 3-18 (16 TPs)
    for row in range(3, 19):
        tp_id = ws_fltp.cell(row=row, column=3).value
        if tp_id and tp_id in tp_mapping:
            checker_id, tc_id = tp_mapping[tp_id]
            ws_fltp.cell(row=row, column=5, value=checker_id)
            ws_fltp.cell(row=row, column=6, value=tc_id)
            print(f"  Linked {tp_id} -> {checker_id}, {tc_id}")

    # =========================================================================
    # Fix DR-FL sheet borders (Gotcha: A/D/E columns)
    # =========================================================================
    print("\nFixing 'DR-FL' sheet borders...")
    ws_drfl = wb['DR-FL']

    # Apply thin borders to columns A, D, E for data rows (3-18)
    for row in range(3, 19):
        for col in [1, 4, 5]:  # A, D, E columns
            cell = ws_drfl.cell(row=row, column=col)
            if cell.border.left.style != 'thin' or cell.border.right.style != 'thin':
                cell.border = get_thin_border()
    print("  Fixed borders for columns A, D, E")

    # =========================================================================
    # Save the workbook
    # =========================================================================
    print(f"\nSaving to: {output_path}")
    wb.save(output_path)
    wb.close()
    print("Done!")

    return output_path


if __name__ == '__main__':
    template_path = "RTM_AI探索_R3(1).xlsx"
    output_path = "RTM_TBUS_Generated.xlsx"

    if not os.path.exists(template_path):
        print(f"Error: Template file not found: {template_path}")
        exit(1)

    generate_rtm(template_path, output_path)
