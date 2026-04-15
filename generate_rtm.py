#!/usr/bin/env python3
"""
RTM Generator Script
Generate Checker and Testcase entries for RTM file based on LRS specification.
"""

import sys
import os

# Add skills scripts path
script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '.claude/skills/rtm_chk_tc_gen/scripts')
sys.path.insert(0, script_dir)

import openpyxl
from rtm_utils import add_checker_to_rtm, add_testcase_to_rtm, link_tp_to_checker_testcase, save_rtm

# Checker definitions
CHECKERS = {
    "CHK_002": {
        "name": "reset_state_check",
        "description": """1. 检查复位后状态机状态：内部fsm_state信号 == IDLE(0x00)；
2. 检查CTRL寄存器默认值：通过RD_CSR(addr=0x04)读取，期望bit[0]=0(EN=0), bit[2:1]=00(LANE_MODE=1-bit)；
3. 检查STATUS寄存器：RD_CSR(addr=0x08)返回0x00；
4. 检查LAST_ERR寄存器：RD_CSR(addr=0x0C)返回0x00；
5. 检查AHB接口：htrans_o==2'b00, hwrite_o==0, haddr_o==0。"""
    },
    "CHK_003": {
        "name": "csr_rw_check",
        "description": """1. 检查VERSION寄存器(addr=0x00)只读：WR_CSR写入0xFF后RD_CSR读回原值；
2. 检查CTRL寄存器(addr=0x04)读写：WR_CSR(0x04, 0x03)后RD_CSR读回0x03；
3. 检查STATUS寄存器(addr=0x08)只读；
4. 检查LAST_ERR寄存器(addr=0x0C)只读；
5. 检查非法地址：RD_CSR(0x10)返回status_code=0x02。"""
    },
    "CHK_004": {
        "name": "lane_mode_check",
        "description": """1. 检查1-bit模式：WR_CSR(0x04, 0x01)配置LANE_MODE=00，发送WR_CSR命令，监控pdi_i[0]/pdo_o[0]有效，pdi_i[3:1]忽略；
2. 检查4-bit模式：WR_CSR(0x04, 0x03)配置LANE_MODE=01，发送命令，监控pdi_i[3:0]/pdo_o[3:0]全部有效；
3. 检查非法值：WR_CSR(0x04, 0x05)尝试配置LANE_MODE=10，读回验证是否生效；
4. 检查事务期间不可切换：事务执行中修改LANE_MODE，验证当前事务按原模式完成。"""
    },
    "CHK_005": {
        "name": "protocol_timing_check",
        "description": """1. 检查turnaround周期：请求阶段结束(pcs_n_i保持低)后，监控pdo_oe_o从0变为1恰好经过1个clk_i周期；
2. 检查pdo_oe_o时序：响应阶段pdo_oe_o=1，其他阶段pdo_oe_o=0；
3. 检查MSB first：发送opcode=0x10(WR_CSR)，监控pdi_i接收顺序为bit[7]->bit[0]；
4. 检查帧边界：pcs_n_i从1->0开启事务，0->1结束事务。"""
    },
    "CHK_006": {
        "name": "opcode_decode_check",
        "description": """1. 检查opcode=0x10译码：发送帧{0x10, 0x04, 0x00000003}，验证识别为WR_CSR，帧长=48bit(1-bit模式48拍，4-bit模式12拍)；
2. 检查opcode=0x11译码：发送帧{0x11, 0x00}，验证识别为RD_CSR，帧长=16bit；
3. 检查opcode=0x20译码：发送帧{0x20, 0x00001000, 0xDEADBEEF}，验证识别为AHB_WR32，帧长=72bit；
4. 检查opcode=0x21译码：发送帧{0x21, 0x00001000}，验证识别为AHB_RD32，帧长=40bit；
5. 检查非法opcode：发送opcode=0x00，响应status_code=0x01。"""
    },
    "CHK_007": {
        "name": "ctrl_config_check",
        "description": """1. 检查EN使能：WR_CSR(0x04, 0x01)配置EN=1，发送AHB_RD32命令验证可执行；WR_CSR(0x04, 0x00)配置EN=0，发送命令验证返回status_code=0x04；
2. 检查SOFT_RST：WR_CSR(0x04, 0x08)写SOFT_RST=1，检查协议上下文清零，LANE_MODE恢复00；
3. 检查SOFT_RST自清零：WR_CSR(0x04, 0x08)后RD_CSR(0x04)读回bit[3]=0。"""
    },
    "CHK_008": {
        "name": "status_err_check",
        "description": """1. 检查STATUS[0]BUSY：发送命令期间RD_CSR(0x08)返回bit[0]=1，命令完成后bit[0]=0；
2. 检查STATUS[2]CMD_ERR：发送非法opcode后STATUS bit[2]=1；
3. 检查STATUS[3]BUS_ERR：触发hresp_i=1后STATUS bit[3]=1；
4. 检查STATUS[4]FRAME_ERR：提前拉高pcs_n_i后STATUS bit[4]=1；
5. 检查LAST_ERR：触发错误后RD_CSR(0x0C)返回对应错误码。"""
    },
    "CHK_009": {
        "name": "error_detection_check",
        "description": """1. 检查BAD_OPCODE(0x01)：发送opcode=0x00，响应status_code==0x01，不发起AHB访问；
2. 检查BAD_REG(0x02)：RD_CSR(0x10)，status_code==0x02；
3. 检查ALIGN_ERR(0x03)：AHB_WR32(addr=0x00000003)，status_code==0x03，htrans_o保持IDLE；
4. 检查DISABLED(0x04)：WR_CSR(0x04, 0x00)后发送命令，status_code==0x04；
5. 检查NOT_IN_TEST(0x05)：test_mode_i=0时发送命令，status_code==0x05；
6. 检查FRAME_ERR(0x06)：请求阶段提前拉高pcs_n_i，status_code==0x06；
7. 检查AHB_ERR(0x07)：配置AHB slave返回hresp_i=1，status_code==0x07；
8. 检查TIMEOUT(0x08)：配置hready_i=0持续>1024周期，status_code==0x08。"""
    },
    "CHK_010": {
        "name": "low_power_check",
        "description": """1. 检查空闲态移位寄存器：pcs_n_i=1时，监控内部rx_shift_reg和tx_shift_reg信号不翻转；
2. 检查超时计数器：监控timeout_counter仅在AHB_WAIT状态计数；
3. 检查AHB空闲输出：test_mode_i=0时，htrans_o==2'b00, hwrite_o==0；
4. 检查关键寄存器翻转：仅在RX/TX/WAIT_AHB状态翻转相关寄存器。"""
    },
    "CHK_011": {
        "name": "throughput_check",
        "description": """1. 检查端到端延时：4-bit模式发送AHB_RD32，从pcs_n_i拉低到pdo_o输出第一个status bit，周期数约23~24个clk_i；
2. 检查吞吐率：连续发送100次AHB_RD32，计算吞吐率，4-bit模式目标>40MB/s；
3. 检查AHB访问粒度：hsize_o==3'b010(WORD)，haddr_o[1:0]==2'b00。"""
    },
    "CHK_012": {
        "name": "dfx_observability_check",
        "description": """1. 检查状态机状态可观测：仿真中可访问内部fsm_state信号；
2. 检查opcode可观测：可访问当前执行的opcode_reg信号；
3. 检查地址/数据可观测：可访问addr_reg, wdata_reg, rdata_reg信号；
4. 检查rx/tx计数可观测：可访问rx_cnt, tx_cnt信号；
5. 检查status_code可观测：可访问status_code信号。"""
    },
    "CHK_013": {
        "name": "csr_memory_map_check",
        "description": """1. 检查CSR访问路径：通过协议命令WR_CSR/RD_CSR访问CSR，不通过AHB地址空间；
2. 检查AHB Master地址空间：AHB_WR32/AHB_RD32命令时haddr_o输出32-bit地址，支持完整地址空间；
3. 检查访问粒度：CSR和AHB访问均为32-bit word粒度。"""
    },
    "CHK_014": {
        "name": "ahb_interface_check",
        "description": """1. 检查htrans_o：发送AHB_WR32命令，监控htrans_o仅输出2'b00(IDLE)或2'b10(NONSEQ)；
2. 检查hsize_o：AHB命令期间hsize_o==3'b010(WORD)；
3. 检查hburst_o：hburst_o==3'b000(SINGLE)；
4. 检查写时序：AHB_WR32时，第1周期haddr_o/hwrite_o=1/htrans_o=NONSEQ输出，第2周期hwdata_o输出数据；
5. 检查读时序：AHB_RD32时，第1周期haddr_o/hwrite_o=0/htrans_o=NONSEQ输出，第2周期采样hrdata_i；
6. 检查hresp_i=1处理：配置slave返回hresp_i=1，验证事务正确终止；
7. 检查hready_i=0处理：配置hready_i=0，验证等待状态处理。"""
    }
}

# Testcase definitions
TESTCASES = {
    "TC_002": {
        "name": "test_reset_behavior",
        "description": """配置条件：
1. 初始状态：rst_ni=0，模块处于复位状态
2. test_mode_i=1，clk_i=100MHz

输入激励：
1. 拉高rst_ni释放复位，等待2个clk_i周期确保复位同步释放
2. 通过RD_CSR命令(opcode=0x11, addr=0x04)读取CTRL寄存器，验证返回值
3. 通过RD_CSR命令(opcode=0x11, addr=0x08)读取STATUS寄存器
4. 通过RD_CSR命令(opcode=0x11, addr=0x0C)读取LAST_ERR寄存器
5. 监控AHB接口信号：htrans_o, hwrite_o

期望结果：
1. CTRL寄存器返回值bit[0]=0(EN=0), bit[2:1]=00(LANE_MODE=1-bit), bit[3]=0(SOFT_RST=0)
2. STATUS寄存器返回0x00
3. LAST_ERR寄存器返回0x00
4. AHB接口：htrans_o=2'b00(IDLE), hwrite_o=0
5. 内部状态机fsm_state=IDLE(0x00)

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_003": {
        "name": "test_csr_access",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR命令(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1
3. 配置LANE_MODE=00(1-bit模式)

输入激励：
1. 发送RD_CSR命令(opcode=0x11, addr=0x00)读取VERSION寄存器，记录返回的version值
2. 发送WR_CSR命令(opcode=0x10, addr=0x04, wdata=0x00000003)，配置EN=1, LANE_MODE=01
3. 发送RD_CSR命令(opcode=0x11, addr=0x04)读取CTRL寄存器，验证写入值
4. 发送RD_CSR命令(opcode=0x11, addr=0x08)读取STATUS寄存器
5. 发送RD_CSR命令(opcode=0x11, addr=0x0C)读取LAST_ERR寄存器
6. 发送RD_CSR命令(opcode=0x11, addr=0x10)尝试访问非法CSR地址

期望结果：
1. VERSION寄存器返回预设版本号(如0x00000100)
2. CTRL写入0x03后读回0x03
3. STATUS返回当前状态
4. 非法地址0x10的访问返回status_code=0x02(BAD_REG)
5. VERSION/STATUS/LAST_ERR寄存器只读属性正确：写入后读回值不变

coverage check点：
对CSR地址(0x00/0x04/0x08/0x0C/非法地址)和读/写属性收集功能覆盖率"""
    },
    "TC_004": {
        "name": "test_work_mode_ate",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1
3. 配置LANE_MODE=01(4-bit模式，wdata=0x00000003)

输入激励：
1. 发送WR_CSR命令(opcode=0x10, addr=0x04, wdata=0x00000003)，配置EN=1, LANE_MODE=01
2. 发送AHB_WR32命令(opcode=0x20, addr=0x00001000, wdata=0xDEADBEEF)
3. 发送AHB_RD32命令(opcode=0x21, addr=0x00001000)，验证读回0xDEADBEEF
4. 监控协议时序：pcs_n_i, pdi_i, pdo_o, pdo_oe_o

期望结果：
1. WR_CSR命令成功，status_code=0x00
2. AHB_WR32命令成功，haddr_o=0x00001000, hwdata_o=0xDEADBEEF
3. AHB_RD32命令成功，hrdata_i返回0xDEADBEEF
4. 半双工协议正确：请求阶段->turnaround(1周期)->响应阶段
5. pdo_oe_o在响应阶段=1，其他阶段=0

coverage check点：
对命令类型(WR_CSR/RD_CSR/AHB_WR32/AHB_RD32)和LANE_MODE(00/01)组合收集功能覆盖率"""
    },
    "TC_005": {
        "name": "test_lane_mode",
        "description": """配置条件：
1. test_mode_i=1, CTRL.EN=1(通过WR_CSR: opcode=0x10, addr=0x04, wdata=0x00000001)
2. clk_i=100MHz

输入激励：
1. 配置LANE_MODE=00：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)
2. 发送RD_CSR命令(opcode=0x11, addr=0x00)，监控pdi_i[0]/pdo_o[0]有效，pdi_i[3:1]忽略
3. 配置LANE_MODE=01：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000003)
4. 发送相同RD_CSR命令，监控pdi_i[3:0]/pdo_o[3:0]全部有效，高nibble优先发送
5. 尝试配置LANE_MODE=10：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000005)
6. 发送RD_CSR(opcode=0x11, addr=0x04)读取CTRL，验证LANE_MODE是否生效
7. 在事务执行期间修改LANE_MODE，验证当前事务不受影响

期望结果：
1. LANE_MODE=00(1-bit)时：数据仅通过pdi_i[0]/pdo_o[0]传输，帧长按1-bit计算(如RD_CSR=16拍)
2. LANE_MODE=01(4-bit)时：数据通过pdi_i[3:0]/pdo_o[3:0]传输，高nibble优先，帧长按4-bit计算(如RD_CSR=4拍)
3. LANE_MODE=10写入后读回仍为原值或返回错误
4. 事务执行期间修改LANE_MODE不影响当前事务

coverage check点：
对LANE_MODE配置值(00/01/10/11)收集功能覆盖率"""
    },
    "TC_006": {
        "name": "test_data_interface",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1, LANE_MODE=00
3. 配置LANE_MODE=01：WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000003)

输入激励：
1. 在1-bit模式下(LANE_MODE=00)：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000003)，监控pdi_i[0]和pdo_o[0]信号波形，忽略pdi_i[3:1]
2. 在4-bit模式下(LANE_MODE=01)：发送相同WR_CSR命令，监控pdi_i[3:0]和pdo_o[3:0]信号波形
3. 验证MSB first传输顺序：发送opcode=0x10(二进制0001_0000)，监控pdi_i接收顺序为bit[7]->bit[6]->...->bit[0]
4. 验证帧边界：监控pcs_n_i从1->0开启事务，命令完成后0->1结束事务

期望结果：
1. 1-bit模式：pdi_i[0]/pdo_o[0]传输数据，pdi_i[3:1]被忽略，帧长=48拍(opcode+addr+wdata各按1-bit传输)
2. 4-bit模式：pdi_i[3:0]/pdo_o[3:0]全部有效，高nibble先发送，帧长=12拍
3. MSB first正确：opcode 0x10发送顺序为0001_0000(MSB first)
4. 帧边界正确：pcs_n_i低有效期间为事务周期

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_007": {
        "name": "test_turnaround",
        "description": """配置条件：
1. test_mode_i=1, CTRL.EN=1
2. 配置LANE_MODE=01(4-bit模式)

输入激励：
1. 发送WR_CSR命令(opcode=0x10, addr=0x04, wdata=0x00000003)
2. 监控请求阶段结束时刻(最后一个数据接收完成)
3. 监控turnaround周期：记录pdo_oe_o从0变为1的时间间隔
4. 监控响应阶段pdo_oe_o状态
5. 发送四种命令验证帧格式：
   - WR_CSR: opcode=0x10, addr=0x04, wdata=0x00000001
   - RD_CSR: opcode=0x11, addr=0x00
   - AHB_WR32: opcode=0x20, addr=0x00001000, wdata=0x12345678
   - AHB_RD32: opcode=0x21, addr=0x00001000

期望结果：
1. 请求阶段结束后，pdo_oe_o保持0恰好1个clk_i周期
2. turnaround后pdo_oe_o=1，进入响应阶段
3. 响应阶段pdo_oe_o=1，输出status+rdata
4. 四种命令帧格式正确处理，响应格式：写命令返回8-bit status，读命令返回8-bit status+32-bit rdata

coverage check点：
对四种命令类型(0x10/0x11/0x20/0x21)收集功能覆盖率"""
    },
    "TC_008": {
        "name": "test_opcode_decode",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1
3. AHB总线空闲

输入激励：
1. 发送opcode=0x10的WR_CSR命令，帧格式{0x10, 0x04, 0x00000003}，监控帧长=12拍(4-bit模式)
2. 发送opcode=0x11的RD_CSR命令，帧格式{0x11, 0x00}，监控帧长=4拍
3. 发送opcode=0x20的AHB_WR32命令，帧格式{0x20, 0x00001000, 0xDEADBEEF}，监控帧长=18拍
4. 发送opcode=0x21的AHB_RD32命令，帧格式{0x21, 0x00001000}，监控帧长=10拍
5. 发送非法opcode=0x00，监控响应status_code
6. 发送非法opcode=0xFF，监控响应status_code

期望结果：
1. opcode=0x10正确译码为WR_CSR，期望帧长=48bit(4-bit模式12拍)
2. opcode=0x11正确译码为RD_CSR，期望帧长=16bit(4-bit模式4拍)
3. opcode=0x20正确译码为AHB_WR32，期望帧长=72bit(4-bit模式18拍)
4. opcode=0x21正确译码为AHB_RD32，期望帧长=40bit(4-bit模式10拍)
5. opcode=0x00返回status_code=0x01(BAD_OPCODE)
6. opcode=0xFF返回status_code=0x01(BAD_OPCODE)
7. 非法opcode不发起AHB访问

coverage check点：
对opcode值(0x10/0x11/0x20/0x21/非法值)收集功能覆盖率"""
    },
    "TC_009": {
        "name": "test_ctrl_config",
        "description": """配置条件：
1. test_mode_i=1

输入激励：
1. 写CTRL.EN=1：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)
2. 发送AHB_RD32命令(opcode=0x21, addr=0x00001000)验证功能命令可执行
3. 写CTRL.EN=0：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000000)
4. 发送AHB_RD32命令，验证返回status_code=0x04(DISABLED)
5. 写CTRL.LANE_MODE=01：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000003)
6. 发送RD_CSR(opcode=0x11, addr=0x04)读取CTRL，验证LANE_MODE=01
7. 写CTRL.SOFT_RST=1：发送WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000008)
8. 发送RD_CSR(opcode=0x11, addr=0x04)读取CTRL，验证SOFT_RST=0(自清零)且LANE_MODE恢复00
9. 检查协议上下文是否清零

期望结果：
1. CTRL.EN=1时功能命令成功执行，status_code=0x00
2. CTRL.EN=0时返回status_code=0x04(DISABLED)
3. CTRL.LANE_MODE配置生效，读回值与写入一致
4. CTRL.SOFT_RST=1后读回bit[3]=0(自清零)
5. 软复位后LANE_MODE恢复00(1-bit默认值)
6. 协议上下文(rx_shift_reg, tx_shift_reg等)清零

coverage check点：
对CTRL字段组合(EN=0/1, LANE_MODE=00/01/10/11, SOFT_RST=0/1)收集功能覆盖率"""
    },
    "TC_010": {
        "name": "test_status_query",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1

输入激励：
1. 发送非法opcode=0x00，触发BAD_OPCODE错误
2. 发送RD_CSR(opcode=0x11, addr=0x08)读取STATUS寄存器，检查bit[2]=1(CMD_ERR)
3. 发送RD_CSR(opcode=0x11, addr=0x0C)读取LAST_ERR寄存器，验证返回0x01(BAD_OPCODE)
4. 配置AHB slave返回hresp_i=1，发送AHB_RD32命令触发AHB_ERR
5. 读取STATUS检查bit[3]=1(BUS_ERR)，读取LAST_ERR返回0x07
6. 发送命令过程中提前拉高pcs_n_i，触发FRAME_ERR
7. 读取STATUS检查bit[4]=1(FRAME_ERR)，读取LAST_ERR返回0x06
8. 验证无独立中断输出信号

期望结果：
1. 触发错误后STATUS相应错误位置位且sticky
2. LAST_ERR记录最近一次错误码
3. 多次错误后LAST_ERR只记录最近一次
4. MVP版本无中断输出信号
5. 通过轮询STATUS/LAST_ERR可获取错误状态

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_011": {
        "name": "test_error_handling",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1
3. AHB总线正常工作

输入激励：
1. 发送opcode=0x00验证BAD_OPCODE(0x01)：发送帧{0x00}，监控响应status_code==0x01，htrans_o保持IDLE
2. 发送RD_CSR(addr=0x10)验证BAD_REG(0x02)：发送帧{0x11, 0x10}，status_code==0x02
3. 发送AHB_WR32(addr=0x00000003)验证ALIGN_ERR(0x03)：发送帧{0x20, 0x00000003, 0xDEADBEEF}，status_code==0x03，htrans_o保持IDLE
4. 配置CTRL.EN=0：WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000000)，发送命令验证DISABLED(0x04)
5. 配置test_mode_i=0，发送命令验证NOT_IN_TEST(0x05)
6. 发送命令过程中提前拉高pcs_n_i验证FRAME_ERR(0x06)
7. 配置AHB slave返回hresp_i=1验证AHB_ERR(0x07)
8. 配置AHB slave持续hready_i=0超过1024周期验证TIMEOUT(0x08)

期望结果：
1. BAD_OPCODE：status_code=0x01，不发起AHB访问，htrans_o=IDLE
2. BAD_REG：status_code=0x02，不发起AHB访问
3. ALIGN_ERR：status_code=0x03，不发起AHB访问，htrans_o=IDLE
4. DISABLED：status_code=0x04
5. NOT_IN_TEST：status_code=0x05
6. FRAME_ERR：status_code=0x06
7. AHB_ERR：status_code=0x07，STATUS[3]=1
8. TIMEOUT：status_code=0x08，STATUS[3]=1
9. 所有前置错误(BAD_OPCODE/BAD_REG/ALIGN_ERR/DISABLED/NOT_IN_TEST/FRAME_ERR)在发起AHB访问前完成检测

coverage check点：
对错误类型(0x01~0x08)收集功能覆盖率"""
    },
    "TC_012": {
        "name": "test_low_power",
        "description": """配置条件：
1. test_mode_i=0或无有效任务(pcs_n_i=1)

输入激励：
1. 保持pcs_n_i=1(空闲态)，监控内部rx_shift_reg和tx_shift_reg信号，验证不翻转
2. 发送AHB_RD32命令，配置hready_i=0模拟AHB等待态，监控timeout_counter信号计数
3. 配置test_mode_i=0，监控AHB接口：htrans_o==2'b00(IDLE), hwrite_o==0
4. 切换到工作态(pcs_n_i=0, test_mode_i=1, CTRL.EN=1)，发送命令，监控关键寄存器翻转

期望结果：
1. 空闲态(pcs_n_i=1)：rx_shift_reg和tx_shift_reg不翻转
2. timeout_counter仅在AHB_WAIT状态(等待hready_i=1)计数，其他状态=0
3. test_mode_i=0时：htrans_o=2'b00, hwrite_o=0
4. 工作态：关键寄存器(opcode_reg, addr_reg等)在RX/TX/WAIT_AHB状态正确翻转

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_013": {
        "name": "test_performance",
        "description": """配置条件：
1. clk_i=100MHz
2. test_mode_i=1, CTRL.EN=1, LANE_MODE=01(4-bit模式)
3. AHB总线响应正常(hready_i=1, hresp_i=0)

输入激励：
1. 在4-bit模式下发送AHB_RD32命令(opcode=0x21, addr=0x00001000)
2. 记录时间戳：T1=pcs_n_i拉低时刻，T2=pdo_o输出第一个status bit时刻
3. 计算端到端延时：T2-T1(周期数)
4. 在4-bit模式下连续发送100次AHB_RD32/AHB_WR32命令
5. 记录总传输数据量和总时间，计算吞吐率
6. 发送AHB命令时监控haddr_o[1:0]，验证4字节对齐

期望结果：
1. 端到端延时：4-bit模式AHB_RD32约23~24个clk_i周期
2. 吞吐率：4-bit模式约50MB/s(理论值，实际应>40MB/s)
3. AHB访问粒度：hsize_o=3'b010(WORD)
4. 地址对齐：haddr_o[1:0]=2'b00
5. 频率稳定性：100MHz稳定工作，无时序违例

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_014": {
        "name": "test_dfx_observability",
        "description": """配置条件：
1. 仿真环境
2. test_mode_i=1
3. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1

输入激励：
1. 执行WR_CSR命令(opcode=0x10, addr=0x04, wdata=0x00000003)
2. 执行RD_CSR命令(opcode=0x11, addr=0x00)
3. 执行AHB_WR32命令(opcode=0x20, addr=0x00001000, wdata=0xDEADBEEF)
4. 执行AHB_RD32命令(opcode=0x21, addr=0x00001000)
5. 采集调试可观测点：
   - fsm_state(状态机状态)
   - opcode_reg(当前opcode)
   - addr_reg(地址寄存器)
   - wdata_reg(写数据寄存器)
   - rdata_reg(读数据寄存器)
   - status_code(响应状态码)
   - rx_cnt/tx_cnt(接收/发送计数)
   - pdo_oe_o(输出使能)

期望结果：
1. fsm_state可观测：IDLE->RX->DECODE->WAIT_AHB->TX->IDLE状态转换可追踪
2. opcode_reg可观测：正确记录0x10/0x11/0x20/0x21
3. addr_reg可观测：正确记录地址值
4. wdata_reg/rdata_reg可观测：正确记录数据值
5. status_code可观测：记录响应状态码0x00(成功)或错误码
6. rx_cnt/tx_cnt可观测：正确计数传输bit数
7. 所有调试信号可通过仿真波形或调试接口访问

coverage check点：
直接用例覆盖，不收功能覆盖率"""
    },
    "TC_015": {
        "name": "test_memory_map",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1

输入激励：
1. 通过WR_CSR(opcode=0x10, addr=0x00, wdata=0xFFFFFFFF)尝试写VERSION寄存器，验证只读属性
2. 通过RD_CSR(opcode=0x11, addr=0x00)读取VERSION寄存器
3. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000003)写CTRL寄存器
4. 通过RD_CSR(opcode=0x11, addr=0x04)读取CTRL寄存器
5. 发送AHB_WR32命令(opcode=0x20, addr=0x00001000, wdata=0x12345678)访问SoC内部memory-mapped地址
6. 发送AHB_RD32命令(opcode=0x21, addr=0x00001000)读回验证
7. 监控AHB地址空间范围：haddr_o输出32-bit地址

期望结果：
1. CSR通过WR_CSR/RD_CSR协议命令正确访问
2. VERSION寄存器只读，写入后读回原值
3. CTRL寄存器读写正确
4. AHB_WR32/AHB_RD32正确访问SoC memory-mapped地址，haddr_o=0x00001000
5. 模块自身CSR(addr=0x00/0x04/0x08/0x0C)不进入SoC AHB memory map
6. AHB Master访问采用32-bit地址空间，word访问粒度

coverage check点：
对CSR地址(0x00~0x0C)和AHB地址空间收集功能覆盖率"""
    },
    "TC_016": {
        "name": "test_ahb_interface",
        "description": """配置条件：
1. test_mode_i=1
2. 通过WR_CSR(opcode=0x10, addr=0x04, wdata=0x00000001)设置CTRL.EN=1
3. AHB总线空闲

输入激励：
1. 发送AHB_WR32命令(opcode=0x20, addr=0x00001000, wdata=0xDEADBEEF)
2. 监控AHB输出信号：haddr_o, hwrite_o, htrans_o, hsize_o, hburst_o, hwdata_o
3. 发送AHB_RD32命令(opcode=0x21, addr=0x00001000)
4. 监控AHB输入信号：hrdata_i, hready_i, hresp_i
5. 配置hready_i=0验证等待态处理
6. 配置hresp_i=1验证错误响应处理

期望结果：
1. htrans_o仅输出2'b00(IDLE)或2'b10(NONSEQ)，无SEQ或Busy
2. hsize_o=3'b010(WORD=32-bit)，固定不变
3. hburst_o=3'b000(SINGLE)，固定不变
4. 写时序正确：第1周期haddr_o=0x00001000, hwrite_o=1, htrans_o=NONSEQ；第2周期hwdata_o=0xDEADBEEF
5. 读时序正确：第1周期haddr_o=0x00001000, hwrite_o=0, htrans_o=NONSEQ；第2周期采样hrdata_i
6. hready_i=0时正确等待，htrans_o保持NONSEQ
7. hresp_i=1时正确终止事务，返回status_code=0x07

coverage check点：
对AHB命令类型(读/写)和响应情况(hready=0/1, hresp=0/1)收集功能覆盖率"""
    }
}

# FL-TP link mapping
FL_TP_LINKS = {
    "TP_002": ("CHK_002", "TC_002"),
    "TP_003": ("CHK_003", "TC_003"),
    "TP_004": ("CHK_004, CHK_005", "TC_004"),
    "TP_005": ("CHK_004", "TC_005"),
    "TP_006": ("CHK_005, CHK_006", "TC_006"),
    "TP_007": ("CHK_005", "TC_007"),
    "TP_008": ("CHK_006", "TC_008"),
    "TP_009": ("CHK_007", "TC_009"),
    "TP_010": ("CHK_008", "TC_010"),
    "TP_011": ("CHK_009", "TC_011"),
    "TP_012": ("CHK_010", "TC_012"),
    "TP_013": ("CHK_011", "TC_013"),
    "TP_014": ("CHK_012", "TC_014"),
    "TP_015": ("CHK_013", "TC_015"),
    "TP_016": ("CHK_014", "TC_016"),
}


def main():
    # Paths
    source_file = "RTM_AI.xlsx"
    output_file = "RTM_AI_gen.xlsx"

    print(f"Loading source RTM file: {source_file}")

    # Copy source file
    import shutil
    shutil.copy(source_file, output_file)

    # Load workbook
    wb = openpyxl.load_workbook(output_file)

    print("Adding Checkers...")
    for chk_id, chk_data in CHECKERS.items():
        add_checker_to_rtm(wb, chk_id, chk_data["name"], chk_data["description"])
        print(f"  Added {chk_id}: {chk_data['name']}")

    print("Adding Testcases...")
    for tc_id, tc_data in TESTCASES.items():
        add_testcase_to_rtm(wb, tc_id, tc_data["name"], tc_data["description"])
        print(f"  Added {tc_id}: {tc_data['name']}")

    print("Linking FL-TP...")
    for tp_id, (checker_id, testcase_id) in FL_TP_LINKS.items():
        if link_tp_to_checker_testcase(wb, tp_id, checker_id, testcase_id):
            print(f"  Linked {tp_id} -> Checker: {checker_id}, Testcase: {testcase_id}")
        else:
            print(f"  Warning: {tp_id} not found in FL-TP sheet")

    # Save
    save_rtm(wb, output_file)
    wb.close()

    print(f"\nRTM file generated: {output_file}")
    print(f"Total Checkers added: {len(CHECKERS)}")
    print(f"Total Testcases added: {len(TESTCASES)}")
    print(f"Total FL-TP links updated: {len(FL_TP_LINKS)}")


if __name__ == "__main__":
    main()
