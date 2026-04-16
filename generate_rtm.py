#!/usr/bin/env python3
"""
RTM Generator Script
Generate Checker List and DV Testcase List based on RTM and LRS files.
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.claude', 'skills', 'rtm_chk_tc_gen', 'scripts'))

import openpyxl
from rtm_utils import read_rtm_structure, add_checker_to_rtm, add_testcase_to_rtm, link_tp_to_checker_testcase, save_rtm
from lrs_reader import read_lrs_structure, extract_key_design_info


# ============================================================================
# Checker Definitions
# ============================================================================

CHECKERS = [
    {
        'id': 'CHK_001',
        'name': 'clock_domain_checker',
        'description': '''描述：
1. 检查clk_i时钟频率稳定性：连续采集clk_i上升沿，计算实际周期，判断是否处于目标频率100MHz的允许误差范围内（±1%，即周期10ns±0.1ns）；
2. 检查时钟域同步性：验证协议采样（pcs_n_i/pdi_i采样）、状态机控制、AHB-Lite主接口均使用同一clk_i上升沿触发，无跨时钟域数据传输；
3. 检查clk_i上升沿时，所有内部寄存器和状态机在clk_i上升沿更新状态。'''
    },
    {
        'id': 'CHK_002',
        'name': 'reset_state_checker',
        'description': '''描述：
1. 检查rst_ni异步复位行为：rst_ni低电平有效，异步复位、同步释放；
2. 检查复位后状态机状态：rst_ni释放后，状态机应处于IDLE状态；
3. 检查复位后寄存器默认值：
   - CTRL.EN=0
   - CTRL.LANE_MODE=2'b00（1-bit模式）
   - CTRL.SOFT_RST=0
   - STATUS=0x00
   - LAST_ERR=0x00
4. 检查复位后协议上下文：接收/发送移位寄存器清零，超时计数器复位；
5. 检查复位后AHB接口：htrans_o=2'b00（IDLE），hwrite_o=0，haddr_o=0。'''
    },
    {
        'id': 'CHK_003',
        'name': 'csr_access_checker',
        'description': '''描述：
1. 检查VERSION寄存器读访问：通过opcode=0x11(RD_CSR)读取VERSION，返回值应为设计定义的版本号；
2. 检查CTRL寄存器读写访问：
   - 写操作：opcode=0x10(WR_CSR)，检查EN/LANE_MODE/SOFT_RST字段写入后生效
   - 读操作：opcode=0x11(RD_CSR)，检查读取值与写入值一致
3. 检查STATUS寄存器读访问：busy位正确反映模块工作状态，错误位sticky行为正确；
4. 检查LAST_ERR寄存器读访问：存储最近一次错误码，新错误覆盖旧错误；
5. 检查CSR访问帧格式：请求阶段opcode+wdata，响应阶段status+rdata，符合LRS定义。'''
    },
    {
        'id': 'CHK_004',
        'name': 'mode_enable_checker',
        'description': '''描述：
1. 检查test_mode_i使能条件：test_mode_i=1时模块才能响应功能命令；
2. 检查CTRL.EN使能条件：CTRL.EN=1时模块才能执行AHB读写操作；
3. 检查test_mode_i=1且CTRL.EN=1时：
   - opcode=0x10/0x11/0x20/0x21命令正常执行
   - 状态机从IDLE正确跳转
4. 检查CTRL.EN=0时：AHB_WR32/AHB_RD32命令返回STS_DISABLED(0x04)错误；
5. 检查test_mode_i=0时：任何命令返回STS_NOT_IN_TEST(0x05)错误；
6. 检查LANE_MODE配置：仅允许2'b00(1-bit)和2'b01(4-bit)，其他值(2'b10/2'b11)返回错误。'''
    },
    {
        'id': 'CHK_005',
        'name': 'lane_mode_checker',
        'description': '''描述：
1. 检查1-bit模式（LANE_MODE=2'b00）：
   - pdi_i[0]作为唯一数据输入
   - pdo_o[0]作为唯一数据输出
   - 数据按MSB first逐bit传输
2. 检查4-bit模式（LANE_MODE=2'b01）：
   - pdi_i[3:0]全bit有效，按高nibble优先发送
   - pdo_o[3:0]全bit有效，按高nibble优先接收
3. 检查pcs_n_i帧边界：
   - pcs_n_i下降沿标志帧开始
   - pcs_n_i上升沿标志帧结束
4. 检查turnaround周期：请求阶段到响应阶段中间固定1个clk_i周期，期间pdo_oe_o=0；
5. 检查pdo_oe_o输出使能：响应阶段pdo_oe_o=1，请求阶段pdo_oe_o=0；
6. 检查协议字段MSB first传输顺序。'''
    },
    {
        'id': 'CHK_006',
        'name': 'opcode_decoder_checker',
        'description': '''描述：
1. 检查opcode=0x10(WR_CSR)解码：前端收满8bit后确定帧长=8bit opcode + 8bit addr + 32bit wdata，任务类型为CSR写；
2. 检查opcode=0x11(RD_CSR)解码：帧长=8bit opcode + 8bit addr，任务类型为CSR读；
3. 检查opcode=0x20(AHB_WR32)解码：帧长=8bit opcode + 32bit addr + 32bit wdata，任务类型为AHB写；
4. 检查opcode=0x21(AHB_RD32)解码：帧长=8bit opcode + 32bit addr，任务类型为AHB读；
5. 检查非法opcode检测：opcode=0x00/0xFF等未定义值，返回STS_BAD_OPCODE(0x01)错误码；
6. 检查opcode解析时序：在收满8bit opcode后的下一个clk_i周期完成解码。'''
    },
    {
        'id': 'CHK_007',
        'name': 'config_register_checker',
        'description': '''描述：
1. 检查CTRL.EN配置：
   - 写入EN=1后，模块使能，可响应功能命令
   - 写入EN=0后，模块禁用，功能命令返回STS_DISABLED(0x04)
2. 检查CTRL.LANE_MODE配置：
   - LANE_MODE=2'b00：切换到1-bit模式
   - LANE_MODE=2'b01：切换到4-bit模式
   - LANE_MODE=2'b10/2'b11：非法配置，保持原模式
3. 检查CTRL.SOFT_RST软复位：
   - 写入SOFT_RST=1触发软复位
   - 软复位后：协议上下文清零，LANE_MODE恢复默认(2'b00)
   - SOFT_RST为write-1-to-trigger，写后自动清零
4. 检查配置生效时序：配置写入后在下一个clk_i上升沿生效。'''
    },
    {
        'id': 'CHK_008',
        'name': 'status_polling_checker',
        'description': '''描述：
1. 检查STATUS寄存器状态：
   - STATUS[7:0]反映命令执行状态（busy、error等标志位）
   - STATUS.sticky位行为：错误标志一旦置位，需要显式清除
2. 检查LAST_ERR寄存器：
   - 存储最近一次错误的错误码
   - 新错误发生时覆盖旧值
   - 成功命令不更新LAST_ERR
3. 检查轮询机制：
   - MVP版本无独立中断输出
   - 所有状态通过STATUS/LAST_ERR轮询获取
4. 检查无中断输出：确认设计未实现中断信号线。'''
    },
    {
        'id': 'CHK_009',
        'name': 'error_detection_checker',
        'description': '''描述：
1. 检查BAD_OPCODE(0x01)错误：opcode值非0x10/0x11/0x20/0x21，返回status_code=0x01；
2. 检查BAD_REG(0x02)错误：访问未定义的CSR地址，返回status_code=0x02；
3. 检查ALIGN_ERR(0x03)错误：AHB_WR32/AHB_RD32的addr[1:0]!=2'b00，返回status_code=0x03；
4. 检查DISABLED(0x04)错误：CTRL.EN=0时发送功能命令，返回status_code=0x04；
5. 检查NOT_IN_TEST(0x05)错误：test_mode_i=0时发送命令，返回status_code=0x05；
6. 检查FRAME_ERR(0x06)错误：pcs_n_i在帧传输过程中提前拉高，返回status_code=0x06；
7. 检查AHB_ERR(0x07)错误：hresp_i=1（ERROR response），返回status_code=0x07；
8. 检查TIMEOUT(0x08)错误：AHB访问超时（hready_i长时间为0），返回status_code=0x08；
9. 检查前置错误收敛：在发起AHB访问前完成所有前置错误检测（BAD_OPCODE/BAD_REG/ALIGN_ERR/DISABLED/NOT_IN_TEST/FRAME_ERR）。'''
    },
    {
        'id': 'CHK_010',
        'name': 'lowpower_behavior_checker',
        'description': '''描述：
1. 检查空闲态寄存器行为：
   - pcs_n_i=1时，接收移位寄存器不更新
   - 无TX任务时，发送移位寄存器不更新
2. 检查超时计数器：
   - 仅在WAIT_AHB状态（等待AHB响应）时超时计数器工作
   - 其他状态计数器保持复位值
3. 检查test_mode_i=0时的AHB输出：
   - htrans_o=2'b00（IDLE）
   - hwrite_o=0
   - haddr_o/hwdata_o保持上一次值或复位值
4. 检查工作态寄存器翻转：
   - RX状态：接收移位寄存器每个clk_i更新
   - TX状态：发送移位寄存器每个clk_i更新
   - WAIT_AHB状态：超时计数器递增'''
    },
    {
        'id': 'CHK_011',
        'name': 'performance_checker',
        'description': '''描述：
1. 检查时钟频率：clk_i稳定工作在100MHz（周期10ns），误差±1%；
2. 检查端到端延时：
   - 从pcs_n_i下降沿（帧开始）到pcs_n_i上升沿（帧结束）的总周期数
   - 预期约23~24 cycles（含turnaround）
3. 检查吞吐率：
   - 1-bit模式：原始链路线速12.5MB/s（100MHz/8）
   - 4-bit模式：原始链路线速50MB/s（100MHz/4*2）
4. 检查AHB访问粒度：
   - hsize_o固定为3'b010（32-bit WORD访问）
   - 地址haddr_o[1:0]=2'b00（4Byte对齐）
5. 检查AHB事务效率：单次AHB读写事务在hready_i=1时耗时2 cycles（地址相+数据相）。'''
    },
    {
        'id': 'CHK_012',
        'name': 'debug_observability_checker',
        'description': '''描述：
1. 检查状态机状态可观测性：内部fsm_state信号可通过波形或调试接口访问；
2. 检查opcode可观测性：当前正在处理的opcode值可访问；
3. 检查地址/数据可观测性：
   - addr寄存器（当前访问地址）可访问
   - wdata寄存器（写数据）可访问
   - rdata寄存器（读返回数据）可访问
4. 检查status_code可观测性：当前命令的status_code可访问；
5. 检查rx/tx计数器可观测性：接收/发送bit计数器值可访问；
6. 检查接口信号可观测性：pcs_n_i、pdi_i、pdo_o、pdo_oe_o可通过波形直接观测。'''
    },
    {
        'id': 'CHK_013',
        'name': 'memory_map_checker',
        'description': '''描述：
1. 检查CSR访问方式：
   - 模块内部CSR（VERSION/CTRL/STATUS/LAST_ERR）通过协议命令访问
   - CSR不映射到SoC AHB memory map
2. 检查AHB Master访问：
   - AHB_WR32/AHB_RD32命令访问SoC内部memory-mapped地址
   - haddr_o为32bit地址空间
   - 访问粒度为32-bit word
3. 检查地址空间约束：
   - 具体可达目标地址范围由SoC顶层约束
   - 模块不检查地址有效性（由AHB slave响应）'''
    },
    {
        'id': 'CHK_014',
        'name': 'ahb_protocol_checker',
        'description': '''描述：
1. 检查AHB-Lite Master信号：
   - haddr_o[31:0]：32bit地址输出
   - hwrite_o：写使能（1=写，0=读）
   - htrans_o[1:0]：仅输出IDLE(2'b00)或NONSEQ(2'b10)
   - hsize_o[2:0]：固定为WORD(3'b010)，表示32bit传输
   - hburst_o[2:0]：固定为SINGLE(3'b000)，单次传输
   - hwdata_o[31:0]：写数据输出
2. 检查AHB时序：
   - 地址相：haddr_o、hwrite_o、htrans_o、hsize_o、hburst_o有效
   - 数据相：hwdata_o有效（写操作时）
   - hready_i=1时事务推进
3. 检查AHB响应：
   - hrdata_i[31:0]：读返回数据
   - hready_i：总线ready信号
   - hresp_i：错误响应（1=ERROR，0=OKAY）
4. 检查单次读写事务时序符合AMBA AHB-Lite协议规范。'''
    }
]


# ============================================================================
# Testcase Definitions
# ============================================================================

TESTCASES = [
    {
        'id': 'TC_001',
        'name': 'test_clock_domain',
        'description': '''配置条件：
1. 配置clk_i时钟频率为100MHz；
2. 模块解复位，test_mode_i=1；

输入激励：
1. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；
2. 在1-bit模式(LANE_MODE=2'b00)下，连续发送AHB_RD32(opcode=0x21)和AHB_WR32(opcode=0x20)命令各10次；
3. 切换到4-bit模式(LANE_MODE=2'b01)，重复步骤2；

期望结果：
1. 所有命令在100MHz频率下正确执行；
2. 协议采样在clk_i上升沿正确捕获pdi_i数据；
3. 状态机控制在clk_i上升沿正确跳转；
4. AHB-Lite主接口在clk_i上升沿正确输出信号；
5. 无时序违例，无跨时钟域问题；

coverage check点：
对lane模式(1-bit/4-bit)和命令类型(RD/WR)的组合收集功能覆盖率。'''
    },
    {
        'id': 'TC_002',
        'name': 'test_reset_sequence',
        'description': '''配置条件：
1. 初始状态rst_ni=0，模块处于复位状态；

输入激励：
1. 释放rst_ni（拉高），等待1个clk_i周期；
2. 通过RD_CSR(opcode=0x11)读取CTRL寄存器，检查默认值；
3. 通过RD_CSR(opcode=0x11)读取STATUS寄存器，检查默认值；
4. 通过RD_CSR(opcode=0x11)读取LAST_ERR寄存器，检查默认值；
5. 检查状态机状态（通过波形或调试接口）；

期望结果：
1. rst_ni释放后，状态机处于IDLE状态；
2. CTRL.EN=0；
3. CTRL.LANE_MODE=2'b00（1-bit模式）；
4. CTRL.SOFT_RST=0；
5. STATUS=0x00；
6. LAST_ERR=0x00；
7. 协议上下文清零，无残留状态；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_003',
        'name': 'test_csr_access',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 通过RD_CSR(opcode=0x11)读取VERSION寄存器，记录版本号；
2. 通过WR_CSR(opcode=0x10)写入CTRL.EN=1, LANE_MODE=2'b01；
3. 通过RD_CSR(opcode=0x11)读取CTRL寄存器，验证写入值；
4. 通过WR_CSR(opcode=0x10)写入CTRL.EN=1, LANE_MODE=2'b00；
5. 通过RD_CSR(opcode=0x11)读取CTRL寄存器，验证写入值；
6. 执行一个AHB_WR32命令，然后通过RD_CSR读取STATUS检查busy位；
7. 触发一个错误条件，然后通过RD_CSR读取LAST_ERR检查错误码；

期望结果：
1. VERSION寄存器返回预期版本号；
2. CTRL寄存器读写正确，EN/LANE_MODE字段配置生效；
3. STATUS寄存器busy位在命令执行期间为1，完成后为0；
4. LAST_ERR寄存器正确记录最近错误码；
5. CSR访问帧格式正确：请求阶段opcode+addr+wdata，响应阶段status+rdata；

coverage check点：
对CSR寄存器(VERSION/CTRL/STATUS/LAST_ERR)和访问类型(读/写)收集功能覆盖率。'''
    },
    {
        'id': 'TC_004',
        'name': 'test_mode_enable',
        'description': '''配置条件：
1. 模块解复位；

输入激励：
1. test_mode_i=0，发送WR_CSR(opcode=0x10)命令，检查响应；
2. test_mode_i=1，发送WR_CSR(opcode=0x10)命令写CTRL.EN=0；
3. test_mode_i=1, CTRL.EN=0，发送AHB_RD32(opcode=0x21)命令，检查响应；
4. test_mode_i=1，通过WR_CSR写CTRL.EN=1；
5. test_mode_i=1, CTRL.EN=1，发送AHB_RD32命令，检查响应；
6. 通过WR_CSR写CTRL.EN=0；
7. 发送AHB_RD32命令，检查响应；

期望结果：
1. test_mode_i=0时，命令返回STS_NOT_IN_TEST(0x05)；
2. CTRL.EN=0时，AHB_WR32/AHB_RD32命令返回STS_DISABLED(0x04)；
3. test_mode_i=1且CTRL.EN=1时，命令正常执行，status=0x00；
4. 半双工请求/响应模式工作正常；

coverage check点：
对test_mode_i(0/1)和CTRL.EN(0/1)的组合收集功能覆盖率。'''
    },
    {
        'id': 'TC_005',
        'name': 'test_lane_mode',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 通过WR_CSR配置LANE_MODE=2'b00（1-bit模式）；
2. 发送AHB_RD32(opcode=0x21)命令，观察pdi_i[0]和pdo_o[0]；
3. 通过WR_CSR配置LANE_MODE=2'b01（4-bit模式）；
4. 发送AHB_RD32命令，观察pdi_i[3:0]和pdo_o[3:0]；
5. 尝试配置LANE_MODE=2'b10（非法值）；
6. 尝试配置LANE_MODE=2'b11（非法值）；
7. 发送AHB_RD32命令，验证当前lane模式；

期望结果：
1. LANE_MODE=2'b00时，1-bit模式正常工作；
2. LANE_MODE=2'b01时，4-bit模式正常工作；
3. LANE_MODE=2'b10/2'b11时，配置被拒绝或保持原模式；
4. Burst和AXI后端功能确认不可用；

coverage check点：
对LANE_MODE值(00/01/10/11)收集功能覆盖率。'''
    },
    {
        'id': 'TC_006',
        'name': 'test_data_interface_1bit',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1, LANE_MODE=2'b00（1-bit模式）；

输入激励：
1. 发送WR_CSR(opcode=0x10)命令，输入opcode=0b00010000逐bit到pdi_i[0]；
2. 检查pcs_n_i下降沿标志帧开始；
3. 观察pdi_i[0]数据接收顺序为MSB first；
4. 观察turnaround周期：请求阶段后1个clk_i周期pdo_oe_o=0；
5. 观察响应阶段pdo_oe_o=1，pdo_o[0]逐bit输出；
6. 检查pcs_n_i上升沿标志帧结束；
7. 发送AHB_WR32(opcode=0x20)命令，重复上述观察；

期望结果：
1. pcs_n_i帧边界正确：下降沿开始，上升沿结束；
2. pdi_i[0]在1-bit模式下接收数据正确；
3. pdo_o[0]在1-bit模式下输出数据正确；
4. turnaround固定1个clk_i周期；
5. 数据传输MSB first顺序正确；
6. pdo_oe_o方向控制正确；

coverage check点：
对帧类型(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32)收集功能覆盖率。'''
    },
    {
        'id': 'TC_007',
        'name': 'test_data_interface_4bit',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1, LANE_MODE=2'b01（4-bit模式）；

输入激励：
1. 发送WR_CSR(opcode=0x10)命令，输入opcode=0x10到pdi_i[3:0]（2拍）；
2. 观察pdi_i[3:0]按高nibble优先接收；
3. 发送AHB_RD32(opcode=0x21)命令，包含opcode+addr共10拍；
4. 观察turnaround周期：请求阶段后1个clk_i周期pdo_oe_o=0；
5. 观察响应阶段pdo_oe_o=1，pdo_o[3:0]按高nibble优先输出；
6. 验证四种命令帧格式：
   - WR_CSR(0x10)：8bit opcode + 8bit addr + 32bit wdata
   - RD_CSR(0x11)：8bit opcode + 8bit addr
   - AHB_WR32(0x20)：8bit opcode + 32bit addr + 32bit wdata
   - AHB_RD32(0x21)：8bit opcode + 32bit addr；

期望结果：
1. pdi_i[3:0]在4-bit模式下按高nibble优先接收正确；
2. pdo_o[3:0]在4-bit模式下按高nibble优先输出正确；
3. turnaround固定1个clk_i周期；
4. 四种命令帧格式正确处理；

coverage check点：
对帧类型和lane模式组合收集功能覆盖率。'''
    },
    {
        'id': 'TC_008',
        'name': 'test_opcode_decode',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 发送opcode=0x10(WR_CSR)命令，验证帧长和任务类型；
2. 发送opcode=0x11(RD_CSR)命令，验证帧长和任务类型；
3. 发送opcode=0x20(AHB_WR32)命令，验证帧长和任务类型；
4. 发送opcode=0x21(AHB_RD32)命令，验证帧长和任务类型；
5. 发送opcode=0x00（非法），检查错误响应；
6. 发送opcode=0xFF（非法），检查错误响应；
7. 发送opcode=0x30（未定义），检查错误响应；

期望结果：
1. opcode=0x10：帧长48bit，任务类型CSR写；
2. opcode=0x11：帧长16bit，任务类型CSR读；
3. opcode=0x20：帧长72bit，任务类型AHB写；
4. opcode=0x21：帧长40bit，任务类型AHB读；
5. 非法opcode返回STS_BAD_OPCODE(0x01)；
6. 前端在收满8bit opcode后正确确定期望帧长；

coverage check点：
对opcode值(0x10/0x11/0x20/0x21/非法值)收集功能覆盖率。'''
    },
    {
        'id': 'TC_009',
        'name': 'test_config_register',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；

输入激励：
1. 通过WR_CSR(opcode=0x10)写入CTRL.EN=1，验证模块使能；
2. 发送AHB_RD32命令验证功能正常；
3. 通过WR_CSR写入CTRL.EN=0，验证模块禁用；
4. 发送AHB_RD32命令验证返回STS_DISABLED(0x04)；
5. 通过WR_CSR写入CTRL.LANE_MODE=2'b00，验证1-bit模式；
6. 通过WR_CSR写入CTRL.LANE_MODE=2'b01，验证4-bit模式；
7. 通过WR_CSR写入CTRL.SOFT_RST=1，验证软复位；
8. 检查软复位后协议上下文清零，LANE_MODE恢复默认；

期望结果：
1. CTRL.EN=1使能模块，EN=0禁用模块；
2. LANE_MODE=00切换到1-bit模式，01切换到4-bit模式；
3. SOFT_RST=1触发软复位，协议上下文清零；
4. 配置写入后在下一个clk_i上升沿生效；

coverage check点：
对CTRL寄存器字段(EN/LANE_MODE/SOFT_RST)和配置值组合收集功能覆盖率。'''
    },
    {
        'id': 'TC_010',
        'name': 'test_status_polling',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 发送AHB_WR32命令，命令执行期间通过RD_CSR(opcode=0x11)读取STATUS检查busy位；
2. 触发BAD_OPCODE错误（发送opcode=0x00）；
3. 通过RD_CSR读取STATUS检查错误标志；
4. 通过RD_CSR读取LAST_ERR检查错误码=0x01；
5. 触发另一个错误（ALIGN_ERR）；
6. 通过RD_CSR读取LAST_ERR检查错误码更新为0x03；
7. 执行成功命令；
8. 通过RD_CSR读取LAST_ERR检查值不变；

期望结果：
1. STATUS.busy位在命令执行期间为1，完成后为0；
2. 错误发生时STATUS错误标志置位；
3. LAST_ERR记录最近错误码，新错误覆盖旧值；
4. 成功命令不更新LAST_ERR；
5. MVP版本无中断输出，所有状态通过轮询获取；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_011',
        'name': 'test_bad_opcode',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 发送opcode=0x00，检查响应status_code；
2. 发送opcode=0xFF，检查响应status_code；
3. 发送opcode=0x12（未定义），检查响应status_code；
4. 发送opcode=0x30（未定义），检查响应status_code；
5. 每次错误后通过RD_CSR读取LAST_ERR验证错误码；

期望结果：
1. 所有非法opcode返回STS_BAD_OPCODE(0x01)；
2. LAST_ERR寄存器更新为0x01；
3. 前端在收满8bit opcode后立即检测错误，不等待后续数据；

coverage check点：
对非法opcode值(0x00/0xFF/0x12/0x30等)收集功能覆盖率。'''
    },
    {
        'id': 'TC_012',
        'name': 'test_bad_reg',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 发送WR_CSR(opcode=0x10)命令，访问未定义的CSR地址（如addr=0xFF）；
2. 检查响应status_code；
3. 发送RD_CSR(opcode=0x11)命令，访问未定义的CSR地址；
4. 检查响应status_code；
5. 通过RD_CSR读取LAST_ERR验证错误码；

期望结果：
1. 访问未定义CSR地址返回STS_BAD_REG(0x02)；
2. LAST_ERR寄存器更新为0x02；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_013',
        'name': 'test_align_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 发送AHB_WR32(opcode=0x20)命令，addr[1:0]=2'b01（非4Byte对齐）；
2. 检查响应status_code；
3. 发送AHB_RD32(opcode=0x21)命令，addr[1:0]=2'b10；
4. 检查响应status_code；
5. 发送AHB_WR32命令，addr[1:0]=2'b11；
6. 检查响应status_code；
7. 通过RD_CSR读取LAST_ERR验证错误码；

期望结果：
1. addr[1:0]!=2'b00时返回STS_ALIGN_ERR(0x03)；
2. LAST_ERR寄存器更新为0x03；
3. 不发起AHB访问；

coverage check点：
对非对齐地址值(01/10/11)收集功能覆盖率。'''
    },
    {
        'id': 'TC_014',
        'name': 'test_disabled_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=0；

输入激励：
1. 发送AHB_WR32(opcode=0x20)命令，检查响应status_code；
2. 发送AHB_RD32(opcode=0x21)命令，检查响应status_code；
3. 通过RD_CSR读取LAST_ERR验证错误码；
4. 通过WR_CSR配置CTRL.EN=1；
5. 发送相同命令验证正常执行；

期望结果：
1. CTRL.EN=0时，AHB命令返回STS_DISABLED(0x04)；
2. LAST_ERR寄存器更新为0x04；
3. CTRL.EN=1后命令正常执行；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_015',
        'name': 'test_not_in_test_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=0；

输入激励：
1. 发送WR_CSR(opcode=0x10)命令，检查响应status_code；
2. 发送RD_CSR(opcode=0x11)命令，检查响应status_code；
3. 发送AHB_WR32(opcode=0x20)命令，检查响应status_code；
4. 发送AHB_RD32(opcode=0x21)命令，检查响应status_code；
5. 通过RD_CSR读取LAST_ERR验证错误码；
6. 设置test_mode_i=1；
7. 发送相同命令验证正常执行；

期望结果：
1. test_mode_i=0时，任何命令返回STS_NOT_IN_TEST(0x05)；
2. LAST_ERR寄存器更新为0x05；
3. test_mode_i=1后命令正常执行；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_016',
        'name': 'test_frame_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 开始发送AHB_WR32命令，在opcode发送完成后立即拉高pcs_n_i（提前结束）；
2. 检查响应status_code；
3. 通过RD_CSR读取LAST_ERR验证错误码；
4. 发送完整命令验证模块恢复正常；

期望结果：
1. pcs_n_i提前拉高返回STS_FRAME_ERR(0x06)；
2. LAST_ERR寄存器更新为0x06；
3. 后续命令正常执行；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_017',
        'name': 'test_ahb_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；
3. AHB slave配置为返回ERROR response；

输入激励：
1. 发送AHB_WR32(opcode=0x20)命令；
2. AHB slave在响应时返回hresp_i=1（ERROR）；
3. 检查响应status_code；
4. 通过RD_CSR读取LAST_ERR验证错误码；
5. AHB slave恢复正常，发送命令验证模块恢复正常；

期望结果：
1. hresp_i=1时返回STS_AHB_ERR(0x07)；
2. LAST_ERR寄存器更新为0x07；
3. 后续命令正常执行；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_018',
        'name': 'test_timeout_error',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；
3. AHB slave配置为长时间不响应；

输入激励：
1. 发送AHB_RD32(opcode=0x21)命令；
2. AHB slave保持hready_i=0超过超时阈值；
3. 检查响应status_code；
4. 通过RD_CSR读取LAST_ERR验证错误码；
5. AHB slave恢复正常，发送命令验证模块恢复正常；

期望结果：
1. AHB超时后返回STS_TIMEOUT(0x08)；
2. LAST_ERR寄存器更新为0x08；
3. 后续命令正常执行；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_019',
        'name': 'test_lowpower',
        'description': '''配置条件：
1. 模块解复位；

输入激励：
1. 设置test_mode_i=0，保持pcs_n_i=1；
2. 观察接收/发送移位寄存器是否更新；
3. 观察AHB输出htrans_o是否为IDLE；
4. 设置test_mode_i=1，配置CTRL.EN=1；
5. 发送命令，观察工作态关键寄存器翻转；
6. 命令完成后，观察空闲态寄存器保持；

期望结果：
1. 空闲态（test_mode_i=0或pcs_n_i=1）：接收/发送移位寄存器不更新；
2. test_mode_i=0时，AHB输出保持IDLE（htrans_o=2'b00）；
3. 工作态：关键寄存器正常翻转；
4. 低功耗设计目标满足；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_020',
        'name': 'test_performance',
        'description': '''配置条件：
1. 配置clk_i=100MHz；
2. 模块解复位，test_mode_i=1；
3. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 配置LANE_MODE=2'b00（1-bit模式）；
2. 连续发送100次AHB_RD32/AHB_WR32命令，记录端到端延时；
3. 计算吞吐率；
4. 配置LANE_MODE=2'b01（4-bit模式）；
5. 连续发送100次AHB_RD32/AHB_WR32命令，记录端到端延时；
6. 计算吞吐率；
7. 检查AHB接口hsize_o固定为WORD，haddr_o[1:0]=2'b00；

期望结果：
1. 目标频率100MHz稳定工作；
2. 端到端延时约23~24 cycles；
3. 1-bit模式吞吐率接近12.5MB/s；
4. 4-bit模式吞吐率接近50MB/s；
5. AHB接口32bit字访问，地址4Byte对齐；

coverage check点：
对lane模式和命令类型组合收集功能覆盖率，记录性能指标。'''
    },
    {
        'id': 'TC_021',
        'name': 'test_debug_observability',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；
3. 仿真环境，启用波形记录；

输入激励：
1. 发送多种命令序列（WR_CSR/RD_CSR/AHB_WR32/AHB_RD32）；
2. 采集内部信号：fsm_state、opcode、addr、wdata、rdata、status_code；
3. 采集rx/tx计数器；
4. 采集接口信号：pcs_n_i、pdi_i、pdo_o、pdo_oe_o；
5. 验证所有调试可观测点可访问；

期望结果：
1. 状态机状态可观测；
2. opcode/addr/wdata/rdata/status_code可观测；
3. rx/tx计数器可观测；
4. 接口信号可观测；
5. 便于联调、波形定位和故障复现；

coverage check点：
直接用例覆盖，不收功能覆盖率。'''
    },
    {
        'id': 'TC_022',
        'name': 'test_memory_map',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；

输入激励：
1. 通过RD_CSR(opcode=0x11)访问VERSION寄存器；
2. 通过WR_CSR/RD_CSR访问CTRL寄存器；
3. 通过RD_CSR访问STATUS/LAST_ERR寄存器；
4. 发送AHB_WR32命令访问SoC memory-mapped地址；
5. 发送AHB_RD32命令访问SoC memory-mapped地址；
6. 验证模块CSR不出现在SoC AHB memory map中；
7. 验证AHB Master访问使用32bit地址空间；

期望结果：
1. CSR通过协议命令正确访问；
2. AHB Master正确访问SoC memory-mapped地址；
3. 模块CSR不进入SoC AHB memory map；
4. AHB Master使用32bit地址空间和word访问粒度；

coverage check点：
对CSR寄存器和AHB地址范围收集功能覆盖率。'''
    },
    {
        'id': 'TC_023',
        'name': 'test_ahb_interface',
        'description': '''配置条件：
1. 模块解复位，test_mode_i=1；
2. 通过WR_CSR(opcode=0x10)配置CTRL.EN=1；
3. AHB总线空闲；

输入激励：
1. 发送AHB_WR32(opcode=0x20)命令；
2. 检查AHB输出：haddr_o、hwrite_o=1、htrans_o=NONSEQ、hsize_o=WORD、hburst_o=SINGLE；
3. 检查hwdata_o在数据相输出正确；
4. 发送AHB_RD32(opcode=0x21)命令；
5. 检查AHB输出：hwrite_o=0、htrans_o=NONSEQ；
6. 检查hrdata_i正确接收；
7. 测试hready_i=0等待场景；
8. 测试hresp_i=1错误场景；

期望结果：
1. AHB-Lite Master信号符合规范；
2. htrans_o仅输出IDLE(2'b00)或NONSEQ(2'b10)；
3. hsize_o固定为WORD(3'b010)；
4. hburst_o固定为SINGLE(3'b000)；
5. 地址相和数据相时序正确；
6. hready_i/hresp_i响应正确处理；

coverage check点：
对AHB命令类型(WR/RD)和响应场景(normal/wait/error)收集功能覆盖率。'''
    }
]


# ============================================================================
# TP to Checker/Testcase Mapping
# ============================================================================

TP_MAPPING = {
    'TP_001': ('CHK_001', 'TC_001'),
    'TP_002': ('CHK_002', 'TC_002'),
    'TP_003': ('CHK_003', 'TC_003'),
    'TP_004': ('CHK_004', 'TC_004'),
    'TP_005': ('CHK_004', 'TC_005'),
    'TP_006': ('CHK_005', 'TC_006'),
    'TP_007': ('CHK_005', 'TC_007'),
    'TP_008': ('CHK_006', 'TC_008'),
    'TP_009': ('CHK_007', 'TC_009'),
    'TP_010': ('CHK_008', 'TC_010'),
    'TP_011': ('CHK_009', 'TC_011,TC_012,TC_013,TC_014,TC_015,TC_016,TC_017,TC_018'),
    'TP_012': ('CHK_010', 'TC_019'),
    'TP_013': ('CHK_011', 'TC_020'),
    'TP_014': ('CHK_012', 'TC_021'),
    'TP_015': ('CHK_013', 'TC_022'),
    'TP_016': ('CHK_014', 'TC_023')
}


def main():
    """Main function to generate RTM file."""

    print("=" * 70)
    print("RTM Generator - Generating Checker List and DV Testcase List")
    print("=" * 70)

    # Load source RTM file
    input_file = 'RTM_AI.xlsx'
    output_file = 'RTM_AI_gen.xlsx'

    print(f"\n[1/5] Loading source RTM file: {input_file}")
    wb = openpyxl.load_workbook(input_file)
    print(f"      Sheets: {wb.sheetnames}")

    # Add Checkers
    print(f"\n[2/5] Adding {len(CHECKERS)} Checkers to Checker List...")
    for checker in CHECKERS:
        add_checker_to_rtm(wb, checker['id'], checker['name'], checker['description'])
        print(f"      + {checker['id']}: {checker['name']}")

    # Add Testcases
    print(f"\n[3/5] Adding {len(TESTCASES)} Testcases to DV Testcase List...")
    for testcase in TESTCASES:
        add_testcase_to_rtm(wb, testcase['id'], testcase['name'], testcase['description'])
        print(f"      + {testcase['id']}: {testcase['name']}")

    # Update FL-TP links
    print(f"\n[4/5] Updating FL-TP links...")
    for tp_id, (checker_id, testcase_id) in TP_MAPPING.items():
        link_tp_to_checker_testcase(wb, tp_id, checker_id, testcase_id)
        print(f"      {tp_id} -> {checker_id}, {testcase_id}")

    # Save output
    print(f"\n[5/5] Saving output RTM file: {output_file}")
    save_rtm(wb, output_file)

    print("\n" + "=" * 70)
    print("RTM generation completed successfully!")
    print(f"Output file: {output_file}")
    print(f"Total Checkers: {len(CHECKERS)}")
    print(f"Total Testcases: {len(TESTCASES)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
