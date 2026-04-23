---
name: RTM_TP2TC_gen
description: 依据LRS文件和RTM文件中的DR-FL、FL-TP，生成RTM文件中的Checker List、DV Testcase List。当用户需要为芯片验证生成RTM文档、填写Checker列表或DV Testcase列表时使用此技能。
allowed-tools: Read,Edit,Grep,Bash(python3:*)
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
   checker核心职责：检查结果，判断对错
   checker工作性质：被动的、监控型的。它观察设计的“反应”。
   checker关注焦点：“做得对不对”。设计的行为、时序、数据、协议是否符合规范。
- **DV Testcase List**: 具体测试用例，需涵盖所有测试点
   testcase核心职责：生成激励，创造测试场景。
   testcase工作性质：主动的、驱动型的。它向设计施加“刺激”。
   testcase关注焦点：“做什么测试”。覆盖哪些功能点、场景、边界条件或协议要求。

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

### 步骤1.6: 生成功能覆盖率

根据设计信息和FL/TP，生成所有可能的功能覆盖率

**后续生成的Testcase必须覆盖所有的功能覆盖率**

### 步骤2: 生成新的RTM文件

新的RTM文件需保留源RTM的所有内容（DR-FL、FL-TP、填写要求等）。

### 步骤3: 填写Checker List

根据LRS文档中的功能描述，生成涵盖所有TP检查的Checker：

**Checker描述要求**：
1. 需要定性+定量描述，必须引用LRS中的具体信号名、取值
2. **必须包含具体的检查内容（寄存器、信号、时序、状态机跳转等）和预期值**
3. 与DV SPEC的区别：RTM中描述check的内容，DV SPEC中描述实现方案
4. **被动的、监控型的**。不要写成testcase，即checker描述中不包含具体的测试步骤，如九步法检测寄存器：包含默认值、读写属性、异常地址读写检查，这种写法属于testcase。

**示例Checker格式**（基于LRS中的实际信号）：
```
dvfs_checker
描述：
检查电压和频率调整的顺序：降频时应先降频率再降电压；升频时应先升电压再升频率；（存在只升降频率不调电压的场景，不要误检测）

status_reg_checker
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

clk_freq_checker
描述：
1.检查频率值是否正确：连续采集时钟上升沿和下降沿并计算实际频率/周期，判断是否处于目标频率的允许误差范围内（±1%）；
2.检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内。
```

### 步骤4: 填写DV Testcase List

生成测试用例

**TC完备性**：

1. **TC涵盖所有测试点**
2. **TC覆盖所有的合理的配置和激励的组合** 生成随机测试，通过循环和随机，覆盖合理配置和输入激励的所有组合
3. **TC可以使代码覆盖率和功能覆盖率达到100%** 
   - 所有寄存器的所有位至少有1个测试用例覆盖到
   - 所有状态机的所有状态和状态跳转至少有1个测试用例覆盖到

**TC描述必须引用LRS中的具体名称**：

1. **配置条件**: 使用LRS中的具体寄存器名（CTRL.EN, CTRL.LANE_MODE等）
2. **输入激励**: 使用LRS中的具体接口名（pdi_i, pcs_n_i）和opcode值（0x10, 0x11等）
   - **输入激励可执行性**：不要使用不具体的描述：如触发各类错误条件(非法opcode、帧错误、AHB错误等)，未指明如何触发。发送命令验证优先级，未指明发送什么命令。使用明确可执行的描述，如发送非法opcode(0x00/0xFF)验证BAD_OPCODE(0x01)。
   - **输入激励的执行顺序**: 明确每一步的操作，按顺序可以正常衔接，如test_error_handling，构造一种错误场景后无法立刻测试另一种错误，需要先复位和进行一些初始化配置。如果一个testcase中测试多个功能点不好衔接或显得混乱，可以多写一些testcase，每个testcase只测一个功能点。
3. **期望结果**: 使用LRS中的具体状态码和信号名（STATUS=0x00表示成功）

**示例Testcase格式**（基于LRS中的实际定义）：

```
配置条件：
//对配置寄存器或接口控制信号进行描述
输入激励：
//对接口激励进行描述
期望结果：
// 描述逻辑处理期望的结果，以及check点
coverage check点：
//如果通过随机测试，功能模型建模来确认对测试点的覆盖，需要描述功能模型的功能。如果通过直接用例来覆盖测试点，则不需要收集功能覆盖率，该部分内容不用描述。

test_xxx
配置条件：
1.RSIO模块解复位初始化接收通路；
2.仅配置lane0，其它lane无效：1）解复位并使能接受通道lane0，并配置lane0数据通路正确接收数据；2）复位并不使能lane0通路；3）再解复位使能lane0，并配置lane0数据通路正确接收数据；
3.仅配置lane1，其它lane无效：配置过程同上lane0
4.仅配置lane2，其它lane无效：配置过程同上lane0
5.仅配置lane3，其它lane无效：配置过程同上lane0
其它：以上测试过程中，不关心的配置或接口控制信号随机
输入激励：
1.对应lane0通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
2.对应lane1通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
3.对应lane2通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
4.对应lane3通路，依次按照使能的情况，发送方依次输入激励数据包和参考时钟；
期望结果：
1.lane0使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
2.lane1使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
3.lane2使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
4.lane3使能期间，能正确接受到发送方发来的数据，不使能期间无数据；其它lane通道无数据；
coverage check点：
直接用例覆盖，不收功能覆盖率

配置条件：
1.URAT模块解复位初始化接收通路;
2.配置DLF[3:0]设置波特率小数部分，配置DLH和DLL设置波特率整数部分;
3.配置FCR[0]=1使能FIFO;
4.随机设置FCR[5:4]设置TX_FIFO水线;
5.随机配置FCR[7:6]设置RX_FIFO水线;
6.随机配置IER[7]设置THRE使能
7.随机配置LCR[1:0]设置数据位宽(5-8bit);
8.随机配置LCR[2]设置停止位位宽(1/1.5/2bit停止位);
9.随机配置LCR[5:3]设置奇/偶校验;
10.配置MCR[1]=1和MCR[5]=1使能autoflow模式;
输入激励：
1.将随机数据通过sin从UART_VIP中传输到UART中;
2.将随机数据通过sout从UART传输到UART_VIP中，在传输过程中将cts_n端force为高电平;
期望结果:
1.将随机数据通过sin从UART_VIP中传输到UART中，UART不读取，当RX_FIFO中数据量大于等于阈值时，rts_n输出高电平到UART_VIP的cts_n端，
UART_VIP会停止发送串行数据，通过读RBR清空RX_FIFO，rts_n输出低电平到UART_VIP的cts_n端，通知UART_VIP继续发送串行数据;
2.将随机数据通过sout从UART传输到UART_VIP中，在传输过程中将cts_n端force为高电平。TX_FIFO仍可以写入，但不会通过sout进行传输，当cts_n输入再次变为低电平时，传输恢复;
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

## 常见Checker检查内容

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
- 多个TP可共享同一个Checker或Testcase，也可多个Checker或Testcase覆盖同一个TP
- 保留源RTM中的填写要求和说明信息
- **关键**：所有描述必须引用LRS中定义的具体信号名、寄存器名、opcode值，不得使用模糊描述

## 附件资源

- `scripts/rtm_utils.py`: RTM文件读写工具
- `scripts/lrs_reader.py`: LRS文档解析工具（支持提取opcodes、registers、timing等）
- `examples/`: 参考示例文件