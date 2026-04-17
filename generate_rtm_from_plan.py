#!/usr/bin/env python3
"""
RTM Generator Script
Generate new RTM file with Checker List and DV Testcase List based on plan.
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.claude/skills/RTM_TP2TC_skills/scripts'))

from rtm_utils import add_checker_to_rtm, add_testcase_to_rtm, link_tp_to_checker_testcase, save_rtm
import openpyxl

def main():
    # File paths
    input_rtm = '/home/xingchangchang/ai_evaluation/claude_code/rtm_gen/ai_cc_rtm_gen/RTM_AI.xlsx'
    output_rtm = '/home/xingchangchang/ai_evaluation/claude_code/rtm_gen/ai_cc_rtm_gen/RTM_AI_generated.xlsx'

    # Load source RTM
    print(f"Loading source RTM: {input_rtm}")
    wb = openpyxl.load_workbook(input_rtm)

    # Define Checker list
    checkers = [
        ('CHK_001', 'freq_checker',
         '检查频率值是否正确：连续采集clk_i上升沿和下降沿并计算实际频率/周期，判断是否处于100MHz目标频率的允许误差范围内（±3%）；'
         '检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内。'),

        ('CHK_002', 'rst_checker',
         '检查复位connectivity：是否正确连接至模块并生效；'
         '包含主要复位信号：rst_ni负责模块的全局复位，复位后状态机回到IDLE，CTRL.EN=0，LANE_MODE=01(1-bit默认值)，清空协议/响应上下文和错误状态。'),

        ('CHK_003', 'regs_checker',
         '九步法检测寄存器：包含默认值、读写属性、异常地址读写检查等；'
         '具体检查VERSION(只读)、CTRL(读写)、STATUS(只读)、LAST_ERR(只读)寄存器的访问属性和默认值。'),

        ('CHK_004', 'status_checker',
         '监测模块状态：STATUS.BUSY、STATUS.DONE、STATUS.ERR信号的复位初始状态、模式切换及正常输出的指示值是否正确；'
         '检查test_mode_i=1且CTRL.EN=1时模块处于测试使能状态，允许执行功能命令。'),

        ('CHK_005', 'protocol_checker',
         '检查外部接口协议时序：'
         '1.帧边界检测：pcs_n_i定义帧起始和结束；'
         '2.数据传输时序：pdi_i[3:0]/pdo_o[3:0]在clk_i上升沿采样；'
         '3.方向控制：pdo_oe_o正确切换输入输出方向；'
         '4.协议字段：opcode、addr、data按MSB first传输；'
         '5.Lane模式：1-bit模式使用pdi_i[0]/pdo_o[0]，4-bit模式按高nibble优先发送。'),

        ('CHK_006', 'spi_protocol_checker',
         '检查类SPI协议时序：'
         '1.帧边界检测：pcs_n_i拉低定义帧起始，拉高定义帧结束；'
         '2.数据传输时序：pdi_i[3:0]在clk_i上升沿采样作为输入数据，pdo_o[3:0]在clk_i上升沿更新作为输出数据；'
         '3.方向控制：pdo_oe_o在响应阶段为1(输出使能)，请求阶段为0；'
         '4.协议字段：opcode(8bit)、addr(32bit)、data(32bit)按MSB first传输。'),

        ('CHK_007', 'timing_checker',
         '检查turnaround时序：'
         '请求阶段结束后，固定1个clk_i周期turnaround，然后进入响应阶段；'
         'pdo_oe_o在turnaround周期后拉高，进入TX阶段输出status+rdata。'),

        ('CHK_008', 'opcode_checker',
         '检查opcode译码正确性：'
         '1.正确译码：8\'h10译码为WR_CSR命令，8\'h11译码为RD_CSR命令，8\'h20译码为AHB_WR32命令，8\'h21译码为AHB_RD32命令；'
         '2.非法opcode检测：除0x10/0x11/0x20/0x21外的opcode值视为BAD_OPCODE，期望状态码0x01。'),

        ('CHK_009', 'ctrl_config_checker',
         '检查CTRL寄存器配置正确性：'
         '1.CTRL.EN=1时模块使能，CTRL.EN=0时模块禁用(命令返回DISABLED错误码0x04)；'
         '2.CTRL.LANE_MODE=00(1-bit模式)或01(4-bit模式)，非法值(10/11)返回错误；'
         '3.CTRL.SOFT_RST写1触发软复位，协议上下文清零并恢复默认lane模式。'),

        ('CHK_010', 'status_query_checker',
         '监测模块状态：STATUS寄存器提供busy/done/err状态，LAST_ERR寄存器提供最近错误码；'
         '检查STATUS.BUSY在命令执行期间为1，完成后为0；'
         '检查LAST_ERR在错误发生时更新为对应错误码。'),

        ('CHK_011', 'error_checker',
         '检查协议错误的检测：'
         '1.BAD_OPCODE(0x01)：非法opcode检测；'
         '2.BAD_REG(0x02)：非法CSR地址检测；'
         '3.ALIGN_ERR(0x03)：地址非4Byte对齐检测；'
         '4.DISABLED(0x04)：模块未使能检测；'
         '5.NOT_IN_TEST(0x05)：非测试模式检测；'
         '6.FRAME_ERR(0x06)：帧错误检测(pcs_n_i提前拉高)；'
         '7.AHB_ERR(0x07)：AHB总线错误(hresp_i=1)检测；'
         '8.TIMEOUT(0x08)：超时检测。'
         '所有错误应在发起AHB访问前完成收敛。'),

        ('CHK_012', 'lowpower_checker',
         '检查空闲态低功耗行为：'
         '1.空闲态(test_mode_i=0或无有效任务)接收/发送移位寄存器不翻转；'
         '2.超时计数器仅在RX/TX/WAIT_AHB状态工作；'
         '3.test_mode_i=0时AHB输出保持IDLE(htrans_o=IDLE)；'
         '4.仅在关键状态翻转关键寄存器。'),

        ('CHK_013', 'throughput_checker',
         '检查性能指标：'
         '1.clk_i频率稳定在100MHz±3%；'
         '2.1-bit模式原始链路线速12.5MB/s；'
         '3.4-bit模式原始链路线速50MB/s；'
         '4.AHB接口固定32bit字访问，地址4Byte对齐；'
         '5.端到端延时约23~24 cycles。'),

        ('CHK_014', 'dfx_checker',
         '检查调试可观测点可访问性：'
         '状态机状态、opcode、addr、wdata、rdata、status_code、rx/tx计数等内部调试信号可采集；'
         '便于联调、波形定位和故障复现。'),

        ('CHK_015', 'memory_map_checker',
         '检查memory map约束：'
         '1.模块CSR(VERSION/CTRL/STATUS/LAST_ERR)仅通过WR_CSR/RD_CSR协议命令访问，不映射到SoC AHB地址空间；'
         '2.AHB Master访问采用32bit地址空间和word访问粒度；'
         '3.AHB地址需4Byte对齐。'),

        ('CHK_016', 'ahb_protocol_checker',
         '检查AHB-Lite Master协议符合性：'
         '1.htrans_o仅输出IDLE(2\'b00)或NONSEQ(2\'b10)，不输出SEQ(2\'b01)或BUSY(2\'b11)；'
         '2.hsize_o固定为WORD(3\'b010，32-bit)；'
         '3.hburst_o固定为SINGLE(3\'b000)；'
         '4.haddr_o/hwrite_o/hwdata_o输出正确；'
         '5.hrdata_i/hready_i/hresp_i输入正确处理。')
    ]

    # Define Testcase list
    testcases = [
        ('TC_001', 'test_tbus_clk_normal',
         '配置条件：\n1.配置clk_i时钟频率为100MHz；\n2.配置test_mode_i=1，通过WR_CSR(0x10)设置CTRL.EN=1使能模块；\n3.配置LANE_MODE=00(1-bit模式)或01(4-bit模式)。\n'
         '输入激励：\n1.连续发送AHB_RD32(0x21)和AHB_WR32(0x20)命令，覆盖1-bit和4-bit两种lane模式；\n2.验证协议采样、状态机控制和AHB-Lite主接口同域工作。\n'
         '期望结果：\n1.所有命令在100MHz频率下正确执行；\n2.clk_i时钟域同步性正常，无时序违例；\n3.协议采样正确，状态机跳转正常，AHB-Lite主接口工作正常。\n'
         'coverage check点：\n对lane模式配置(1-bit/4-bit)收集功能覆盖率'),

        ('TC_002', 'test_tbus_rst',
         '配置条件：\n1.配置test_mode_i=1，模块进入测试模式；\n2.初始状态rst_ni为低，模块处于复位状态。\n'
         '输入激励：\n1.释放rst_ni，验证复位后状态机回到IDLE；\n2.通过RD_CSR(0x11)读取CTRL寄存器，检查CTRL.EN=0，LANE_MODE=01默认值；\n3.读取STATUS/LAST_ERR寄存器验证清零；\n4.验证协议上下文和错误状态已清空。\n'
         '期望结果：\n1.复位后状态机处于IDLE状态；\n2.CTRL.EN=0，LANE_MODE=01(1-bit模式)；\n3.STATUS/LAST_ERR寄存器值为0x00000000；\n4.无残留协议上下文和错误状态。\n'
         'coverage check点：\n直接用例覆盖，不收功能覆盖率'),

        ('TC_003', 'test_tbus_reg',
         '配置条件：\n1.配置test_mode_i=1，通过WR_CSR(0x10)设置CTRL.EN=1使能模块；\n2.模块进入使能工作状态。\n'
         '输入激励：\n1.通过RD_CSR(0x11)读取VERSION寄存器验证版本号；\n2.通过WR_CSR(0x10)/RD_CSR(0x11)访问CTRL寄存器配置EN、LANE_MODE、SOFT_RST字段；\n3.读取STATUS检查busy状态；\n4.读取LAST_ERR检查错误状态；\n5.九步法寄存器测试激励。\n'
         '期望结果：\n1.CSR读写正确，VERSION返回预期值(如0x00010000)；\n2.CTRL.EN、CTRL.LANE_MODE、CTRL.SOFT_RST配置生效；\n3.STATUS/LAST_ERR反映正确状态；\n4.寄存器读写属性符合规范。\n'
         'coverage check点：\n对CSR地址和数据位宽收集功能覆盖率'),

        ('TC_004', 'test_tbus_test_mode',
         '配置条件：\n1.配置test_mode_i=1，通过WR_CSR(0x10)设置CTRL.EN=1；\n2.模块进入ATE测试模式。\n'
         '输入激励：\n1.发送WR_CSR(0x10)命令配置LANE_MODE字段；\n2.发送AHB_WR32(0x20)命令进行单次写操作；\n3.发送AHB_RD32(0x21)命令进行单次读操作；\n4.验证半双工请求/响应模式工作正常。\n'
         '期望结果：\n1.模块正确执行功能命令；\n2.协议采用半双工模式：请求阶段输入、turnaround 1周期、响应阶段输出；\n3.CSR访问与AHB-Lite单次读写正常；\n4.STATUS寄存器反映正确的busy/done状态。\n'
         'coverage check点：\n对命令类型(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32)收集功能覆盖率'),

        ('TC_005', 'test_tbus_lane_mode',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.模块进入使能工作状态。\n'
         '输入激励：\n1.配置CTRL.LANE_MODE=00，验证1-bit模式数据传输；\n2.配置CTRL.LANE_MODE=01，验证4-bit模式数据传输(高nibble优先)；\n3.尝试配置非法LANE_MODE值(10/11)，验证错误处理；\n4.验证不支持Burst和AXI后端功能。\n'
         '期望结果：\n1.1-bit模式正常工作，pdi_i[0]/pdo_o[0]正确传输；\n2.4-bit模式正常工作，pdi_i[3:0]/pdo_o[3:0]按高nibble优先发送；\n3.非法LANE_MODE配置返回错误码；\n4.Burst和AXI功能确认不可用。\n'
         'coverage check点：\n对LANE_MODE配置值(00/01/10/11)收集功能覆盖率'),

        ('TC_006', 'test_tbus_data_interface',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.配置LANE_MODE=00(1-bit模式)。\n'
         '输入激励：\n1.在1-bit模式下发送WR_CSR(0x10)命令，验证pdi_i[0]/pdo_o[0]数据传输；\n2.配置LANE_MODE=01(4-bit模式)；\n3.在4-bit模式下发送AHB_WR32(0x20)命令，验证pdi_i[3:0]/pdo_o[3:0]按高nibble优先发送；\n4.验证pcs_n_i帧边界正确：拉低开始帧，拉高结束帧。\n'
         '期望结果：\n1.数据接口按lane模式正确传输；\n2.帧边界清晰：pcs_n_i定义请求阶段和响应阶段；\n3.MSB first顺序正确；\n4.pdo_oe_o在turnaround后拉高，响应阶段输出使能。\n'
         'coverage check点：\n对lane模式(1-bit/4-bit)和数据包类型收集功能覆盖率'),

        ('TC_007', 'test_tbus_protocol_timing',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.配置LANE_MODE=00或01。\n'
         '输入激励：\n1.发送WR_CSR(0x10)命令验证请求阶段；\n2.监测turnaround周期(1个clk_i)；\n3.检查响应阶段pdo_oe_o输出使能；\n4.验证四种命令帧格式：WR_CSR(0x10)、RD_CSR(0x11)、AHB_WR32(0x20)、AHB_RD32(0x21)。\n'
         '期望结果：\n1.请求/响应阶段正确分离；\n2.turnaround固定1个clk_i周期；\n3.协议字段MSB first传输；\n4.四种帧格式正确处理。\n'
         'coverage check点：\n对四种opcode(0x10/0x11/0x20/0x21)收集功能覆盖率'),

        ('TC_008', 'test_tbus_opcode',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.AHB总线空闲。\n'
         '输入激励：\n1.发送opcode=8\'h10执行WR_CSR命令；\n2.发送opcode=8\'h11执行RD_CSR命令；\n3.发送opcode=8\'h20执行AHB_WR32命令；\n4.发送opcode=8\'h21执行AHB_RD32命令；\n5.发送非法opcode(8\'h00/8\'hFF)验证错误处理。\n'
         '期望结果：\n1.四种opcode正确译码并执行；\n2.非法opcode返回STS_BAD_OPCODE(0x01)；\n3.前端正确确定期望帧长；\n4.LAST_ERR寄存器更新为对应错误码。\n'
         'coverage check点：\n对opcode值(0x10/0x11/0x20/0x21/非法值)收集功能覆盖率'),

        ('TC_009', 'test_tbus_ctrl_config',
         '配置条件：\n1.配置test_mode_i=1；\n2.模块初始禁用状态(CTRL.EN=0)。\n'
         '输入激励：\n1.通过WR_CSR(0x10)写CTRL.EN=1使能模块，验证功能命令可执行；\n2.写CTRL.EN=0禁用模块，发送命令验证返回DISABLED错误(0x04)；\n3.配置CTRL.LANE_MODE=00验证1-bit模式；\n4.配置CTRL.LANE_MODE=01验证4-bit模式；\n5.写CTRL.SOFT_RST=1触发软复位，验证协议上下文清零并恢复默认lane模式。\n'
         '期望结果：\n1.CTRL.EN配置正确生效；\n2.使能/禁用状态切换正确；\n3.LANE_MODE配置生效；\n4.软复位功能正常，协议上下文清零。\n'
         'coverage check点：\n对CTRL.EN、CTRL.LANE_MODE、CTRL.SOFT_RST配置值收集功能覆盖率'),

        ('TC_010', 'test_tbus_status_query',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.模块进入使能工作状态。\n'
         '输入激励：\n1.触发各类错误条件(非法opcode、帧错误、AHB错误等)；\n2.通过RD_CSR(0x11)读取STATUS寄存器检查sticky位；\n3.读取LAST_ERR寄存器获取最近错误码；\n4.验证无独立中断输出。\n'
         '期望结果：\n1.所有错误与完成状态通过STATUS/LAST_ERR查询获取；\n2.MVP版本无中断输出；\n3.ATE轮询方式正确获取状态；\n4.STATUS.BUSY在命令执行期间为1，完成后为0。\n'
         'coverage check点：\n对STATUS和LAST_ERR寄存器值收集功能覆盖率'),

        ('TC_011', 'test_tbus_error_detect',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.AHB总线正常。\n'
         '输入激励：\n1.发送非法opcode(8\'h00/8\'hFF)验证BAD_OPCODE错误(0x01)；\n2.访问非法CSR地址验证BAD_REG错误(0x02)；\n3.发送非4Byte对齐地址验证ALIGN_ERR错误(0x03)；\n4.配置CTRL.EN=0后发送命令验证DISABLED错误(0x04)；\n5.配置test_mode_i=0后发送命令验证NOT_IN_TEST错误(0x05)；\n6.提前拉高pcs_n_i验证FRAME_ERR错误(0x06)；\n7.触发hresp_i=1验证AHB_ERR错误(0x07)；\n8.模拟AHB超时验证TIMEOUT错误(0x08)。\n'
         '期望结果：\n1.各类错误正确检测；\n2.在发起AHB访问前完成前置错误收敛；\n3.返回确定性状态码；\n4.LAST_ERR寄存器更新正确。\n'
         'coverage check点：\n对错误类型(0x01~0x08)收集功能覆盖率'),

        ('TC_012', 'test_tbus_lowpower',
         '配置条件：\n1.模块处于空闲态(test_mode_i=0或无有效任务)。\n'
         '输入激励：\n1.保持pcs_n_i=1验证接收/发送移位寄存器不翻转；\n2.模拟AHB等待态验证超时计数器仅在此状态工作；\n3.test_mode_i=0时验证AHB输出保持IDLE；\n4.切换到工作态验证关键寄存器翻转。\n'
         '期望结果：\n1.空闲态无效翻转最小化；\n2.低功耗设计目标满足；\n3.AHB接口在空闲态保持IDLE；\n4.功耗测试通过。\n'
         'coverage check点：\n直接用例覆盖，不收功能覆盖率'),

        ('TC_013', 'test_tbus_performance',
         '配置条件：\n1.配置clk_i=100MHz；\n2.AHB总线响应正常。\n'
         '输入激励：\n1.在1-bit模式下连续执行AHB_RD32/AHB_WR32命令，计算端到端延时和吞吐率；\n2.在4-bit模式下执行相同测试；\n3.验证原始链路线速：1-bit模式12.5MB/s，4-bit模式50MB/s；\n4.验证AHB接口32bit字访问和4Byte对齐约束。\n'
         '期望结果：\n1.目标频率100MHz稳定工作；\n2.延时符合预期(约23~24 cycles)；\n3.吞吐率达标；\n4.AHB访问约束满足。\n'
         'coverage check点：\n对性能指标(频率、延时、吞吐率)收集功能覆盖率'),

        ('TC_014', 'test_tbus_dfx',
         '配置条件：\n1.仿真环境，test_mode_i=1，CTRL.EN=1；\n2.模块进入使能工作状态。\n'
         '输入激励：\n1.执行多种命令序列(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32)；\n2.采集状态机状态、opcode、addr、wdata、rdata、status_code；\n3.采集rx/tx计数、pcs_n_i、pdi_i、pdo_o、pdo_oe_o；\n4.验证内部调试可观测点可访问。\n'
         '期望结果：\n1.所有调试可观测点可采集；\n2.便于联调、波形定位和故障复现；\n3.状态机跳转清晰可追踪。\n'
         'coverage check点：\n直接用例覆盖，不收功能覆盖率'),

        ('TC_015', 'test_tbus_memory_map',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.模块进入使能工作状态。\n'
         '输入激励：\n1.通过WR_CSR(0x10)/RD_CSR(0x11)访问模块内部CSR寄存器(VERSION/CTRL/STATUS/LAST_ERR)；\n2.发送AHB_WR32(0x20)/AHB_RD32(0x21)命令访问SoC内部memory-mapped地址；\n3.验证模块自身CSR不进入SoC AHB memory map；\n4.验证AHB Master访问采用32bit地址空间和word访问粒度。\n'
         '期望结果：\n1.CSR通过协议命令访问正常；\n2.AHB Master访问正确；\n3.地址空间约束满足；\n4.4Byte对齐约束满足。\n'
         'coverage check点：\n对CSR地址和AHB地址收集功能覆盖率'),

        ('TC_016', 'test_tbus_ahb_master',
         '配置条件：\n1.配置test_mode_i=1，CTRL.EN=1；\n2.AHB总线空闲。\n'
         '输入激励：\n1.发送AHB_WR32(0x20)命令，验证haddr_o/hwrite_o/htrans_o/hsize_o/hburst_o/hwdata_o输出正确；\n2.发送AHB_RD32(0x21)命令，验证hrdata_i/hready_i/hresp_i输入正确处理；\n3.验证htrans_o仅输出IDLE/NONSEQ；\n4.验证hsize_o固定为WORD(32-bit)；\n5.验证hburst_o固定为SINGLE。\n'
         '期望结果：\n1.AHB-Lite Master接口符合规范；\n2.单次读写事务正确；\n3.信号时序满足AHB协议要求；\n4.hresp_i=1时正确处理AHB错误。\n'
         'coverage check点：\n对AHB事务类型(读/写)和响应类型收集功能覆盖率')
    ]

    # Add Checkers
    print(f"Adding {len(checkers)} checkers...")
    for chk_id, chk_name, chk_desc in checkers:
        add_checker_to_rtm(wb, chk_id, chk_name, chk_desc)
        print(f"  Added {chk_id}: {chk_name}")

    # Add Testcases
    print(f"Adding {len(testcases)} testcases...")
    for tc_id, tc_name, tc_desc in testcases:
        add_testcase_to_rtm(wb, tc_id, tc_name, tc_desc)
        print(f"  Added {tc_id}: {tc_name}")

    # Link TP to Checker and Testcase
    print("Linking TP to Checker and Testcase...")
    tp_links = [
        ('TP_001', 'CHK_001', 'TC_001'),
        ('TP_002', 'CHK_002', 'TC_002'),
        ('TP_003', 'CHK_003', 'TC_003'),
        ('TP_004', 'CHK_004', 'TC_004'),
        ('TP_005', 'CHK_005', 'TC_005'),
        ('TP_006', 'CHK_006', 'TC_006'),
        ('TP_007', 'CHK_007', 'TC_007'),
        ('TP_008', 'CHK_008', 'TC_008'),
        ('TP_009', 'CHK_009', 'TC_009'),
        ('TP_010', 'CHK_010', 'TC_010'),
        ('TP_011', 'CHK_011', 'TC_011'),
        ('TP_012', 'CHK_012', 'TC_012'),
        ('TP_013', 'CHK_013', 'TC_013'),
        ('TP_014', 'CHK_014', 'TC_014'),
        ('TP_015', 'CHK_015', 'TC_015'),
        ('TP_016', 'CHK_016', 'TC_016')
    ]

    for tp_id, chk_id, tc_id in tp_links:
        link_tp_to_checker_testcase(wb, tp_id, chk_id, tc_id)
        print(f"  Linked {tp_id} -> {chk_id}, {tc_id}")

    # Save new RTM
    print(f"Saving new RTM to: {output_rtm}")
    save_rtm(wb, output_rtm)

    print("\n=== RTM Generation Complete ===")
    print(f"Output file: {output_rtm}")
    print(f"Total checkers: {len(checkers)}")
    print(f"Total testcases: {len(testcases)}")
    print(f"Total TP links: {len(tp_links)}")

if __name__ == '__main__':
    main()
