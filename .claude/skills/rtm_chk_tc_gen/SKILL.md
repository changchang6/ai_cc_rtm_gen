---
name:rtm_chk_tc_gen
description:依据LRS文件和RTM文件中的DR-FL、FL-TP，生成RTM文件中的Checker List、DV Testcase List。当用户需要为芯片验证生成RTM文档、填写Checker列表或DV Testcase列表时使用此技能。
allowed-tools:Read,Edit,Grep,Bash(python3:*)
---

你是一名资深芯片验证工程师，依据工作目录下的RTM excel文件和LRS word文件，生成新的RTM excel文件。

## 工作流程

### 步骤1: 理解输入文件

首先使用提供的脚本读取文件结构：

```bash
# 读取RTM文件结构
python3 scripts/rtm_utils.py read RTM_AI.xlsx

# 读取LRS文档结构
python3 scripts/lrs_reader.py read TBUS_LRS_v1.1.docx
```

理解以下关键信息：
- **DR-FL**: 硬件功能点列表，包含DR编号、Feature类别、FL编号、Feature描述
- **FL-TP**: 测试点列表，每个功能点对应一个或多个测试点(TP)
- **Checker List**: 验证检查点，用于判断测试点的功能正确性
- **DV Testcase List**: 具体测试用例，需涵盖所有测试点

### 步骤1.5: 提取关键设计信息

**重要**：在生成Checker和Testcase之前，必须先从LRS文档提取关键设计信息，确保生成的描述引用具体名称。

```bash
# 提取关键设计信息（汇总）
python3 scripts/lrs_reader.py key_info TBUS_LRS_v1.1.docx

# 或分别提取各项信息：
python3 scripts/lrs_reader.py opcodes TBUS_LRS_v1.1.docx      # 提取opcode定义
python3 scripts/lrs_reader.py registers TBUS_LRS_v1.1.docx    # 提取寄存器定义
python3 scripts/lrs_reader.py timing TBUS_LRS_v1.1.docx      # 提取时序要求
```

**必须提取并记录以下信息**：

1. **接口信号列表**：信号名、方向、位宽
   - 示例：`pcs_n_i`(片选), `pdi_i[3:0]`(输入数据), `pdo_o[3:0]`(输出数据), `pdo_oe_o`(输出使能), `test_mode_i`(测试模式)

2. **Opcode定义**：操作码值、名称、功能
   - 示例：`0x10`(WR_CSR), `0x11`(RD_CSR), `0x20`(AHB_WR32), `0x21`(AHB_RD32)

3. **寄存器定义**：寄存器名、字段
   - 示例：`CTRL.EN`, `CTRL.LANE_MODE`, `CTRL.SOFT_RST`

4. **时序要求**：turnaround周期、建立/保持时间
   - 示例：turnaround 1 cycle

**所有后续生成的Checker和Testcase必须引用这些提取的具体名称，不得使用模糊描述。**

### 步骤2: 生成新的RTM文件

新的RTM文件需保留源RTM的所有内容（DR-FL、FL-TP、填写要求等）。

### 步骤3: 填写Checker List

根据LRS文档中的功能描述，为每个测试点生成对应的Checker：

**Checker描述要求**：
1. 需要定性+定量描述，必须引用LRS中的具体信号名、取值
2. 包含具体的检查步骤和预期值
3. 与DV SPEC的区别：RTM中描述check的内容，DV SPEC中描述实现方案

**Checker描述必须包含**：
- 具体信号名（从LRS interface_signals提取）
- 具体取值范围或条件
- 具体时序要求（从LRS提取）

**示例Checker格式**（基于LRS中的实际信号）：
```
status_reg_check
描述：
在IP解复位后的每个cycle，对IP内部状态寄存器和建模得到的状态进行check：
1、通道使能寄存器chenreg
2、通道任务完成原始中断状态寄存器rawtfr_ch
3、通道任务传输异常原始中断状态寄存器rawerr_ch
4、通道安全访问异常原始中断状态寄存器rawnsec_ch
5、通道访问异常中断状态寄存器rawacc_ch
6、公共寄存器组的安全访问异常原始中断寄存器rawcnnsec
7、公共寄存器组的访问异常原始中断寄存器rawcmacc
8、通道任务完成mask后的中断状态寄存器statustfr
9、通道任务传输异常mask后的中断状态寄存器statuserr
10、通道安全访问异常mask后的中断状态寄存器statusnsec
11、公共寄存器组的安全访问异常mask后的中断状态寄存器statuscmnsec

CHK_002: lane_mode_checker
描述：
1. 检查CTRL.LANE_MODE=00时仅使用pdi_i[0]/pdo_o[0]传输
2. 验证CTRL.LANE_MODE=01时每拍收发4bit（高nibble优先）
3. 确认非法LANE_MODE值(10/11)不改变当前配置
```

### 步骤4: 填写DV Testcase List

为每个测试点生成对应的Testcase：

**TC描述必须引用LRS中的具体名称**：

1. **配置条件**: 使用LRS中的具体寄存器名（CTRL.EN, CTRL.LANE_MODE等）
2. **输入激励**: 使用LRS中的具体接口名（pdi_i, pcs_n_i）和opcode值（0x10, 0x11等）
3. **期望结果**: 使用LRS中的具体状态码和信号名（STATUS=0x00表示成功）
4. **执行顺序**: 明确每一步的操作，按顺序列出

**示例Testcase格式**（基于LRS中的实际定义）：
```
test_memory_map
配置条件：
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
对CSR地址(0x00~0x0C)和AHB地址空间收集功能覆盖率

test_xxx
配置条件：
1.RSIO模块解复位初始化接收通路；
仅配置lane0，其它lane无效：1）解复位并使能接受通道lane0，并配置lane0数据通路正确接收数据；2）复位并不使能lane0通路；3)
再解复位使能lane0，并配置lane0数据通路正确接收数据；
3.仅配置lane1，其它lane无效：配置过程同上lane0
4.仅配置lane2，其它lane无效：配置过程同上lane0
5.仅配置lane3，其它lane无效：配置过程同上lane0
其它：以上测试过程中，不关心的配置或接口控制信号随机
输入激励：
2.对应lane0通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
3.对应lane1通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
4.对应lane2通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
5.对应lane3通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
期望结果：
2.lane0使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
3.lane1使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
4.lane2使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
5.lane3使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
coverage check点：
直接用例覆盖，不收功能覆盖率
```

### 步骤5: 更新FL-TP链接

将生成的Checker和Testcase编号填写到FL-TP sheet对应的TP条目后：
- checker编号
- Testcase编号

### 步骤6: 验证输出

检查生成的RTM文件：
- 所有TP都有对应的Checker和Testcase覆盖
- **Checker描述引用LRS中的具体信号名和取值**
- TC描述包含配置条件、输入激励、期望结果、coverage check点
- **TC描述使用具体接口名、寄存器名、opcode值**
- 新的RTM文件中源RTM的所有内容（DR-FL、FL-TP、填写要求等）没有丢失
- 新的RTM文件格式与源RTM一致

## 常见Checker类型

| 类别 | 检查内容示例 |
|------|-------------|
| 时钟 | clk_i频率稳定性、时钟域同步 |
| 复位 | rst_ni异步复位、状态机IDLE、寄存器默认值 |
| 寄存器 | CTRL/STATUS读写正确性、字段配置生效 |
| 接口 | pcs_n_i帧边界、pdi_i/pdo_o时序、pdo_oe_o方向控制 |
| 协议 | opcode解析、帧格式、turnaround周期 |
| 异常 | FRAME_ERR、BAD_OPCODE、TIMEOUT检测 |

## 注意事项

- 不要修改源文件
- skill执行结束，删除临时文件
- Checker编号和Testcase编号需与TP编号对应
- 多个TP可共享同一个Checker或Testcase
- 保留源RTM中的填写要求和说明信息
- **关键**：所有描述必须引用LRS中定义的具体信号名、寄存器名、opcode值，不得使用模糊描述

## 附件资源

- `scripts/rtm_utils.py`: RTM文件读写工具
- `scripts/lrs_reader.py`: LRS文档解析工具（支持提取opcodes、registers、timing等）
- `examples/`: 参考示例文件
