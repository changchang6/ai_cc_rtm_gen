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
CHK_001: pcs_frame_boundary_checker
描述：
1. 检查pcs_n_i拉低后模块开始接收请求（state从IDLE→RX）
2. 验证pcs_n_i在请求未完成时提前拉高时，STATUS=LAST_ERR返回FRAME_ERR(0x05)
3. 确认pdo_oe_o在响应阶段正确指示输出方向（TX阶段=1，其他=0）

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
TC_001: test_csr_write_via_1bit_mode
配置条件：
1. test_mode_i=1（测试模式使能）
2. CTRL.EN=1（模块使能）
3. CTRL.LANE_MODE=00（1-bit模式）

输入激励：
1. pcs_n_i拉低，开始帧传输
2. 通过pdi_i[0]按MSB-first顺序发送：opcode=0x10(WR_CSR)，目标寄存器地址，写数据
3. 等待1个turnaround周期
4. pcs_n_i拉高结束请求

期望结果：
1. pdo_oe_o在响应阶段变为1
2. 通过pdo_o[0]接收STATUS=0x00（成功）
3. 目标寄存器被正确写入配置值

coverage check点：
直接用例覆盖，不收功能覆盖率。

TC_002: test_ahb_read_4bit_mode
配置条件：
1. test_mode_i=1
2. CTRL.EN=1
3. CTRL.LANE_MODE=01（4-bit模式）

输入激励：
1. pcs_n_i拉低
2. 通过pdi_i[3:0]发送opcode=0x21(AHB_RD32)
3. 发送32-bit对齐的AHB目标地址
4. 等待响应

期望结果：
1. htrans_o=NONSEQ，hwrite_o=0（AHB读操作）
2. STATUS=0x00 + RDATA[31:0]返回
3. pdo_o[3:0]按高nibble优先顺序输出数据

coverage check点：
对AHB地址范围、LANE_MODE配置值收集功能覆盖率。
```

### 步骤5: 更新FL-TP链接

将生成的Checker和Testcase编号填写到FL-TP sheet对应的TP条目后：
- Column E: checker编号
- Column F: Testcase编号

### 步骤6: 验证输出

检查生成的RTM文件：
- 所有TP都有对应的Checker和Testcase覆盖
- Checker描述引用LRS中的具体信号名和取值
- TC描述包含配置条件、输入激励、期望结果、coverage check点
- TC描述使用具体接口名、寄存器名、opcode值
- 格式与源RTM一致

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
- skill执行中不要修改skill文件夹里的内容
- Checker编号和Testcase编号需与TP编号对应
- 多个TP可共享同一个Checker或Testcase
- 保留源RTM中的填写要求和说明信息
- **关键**：所有描述必须引用LRS中定义的具体信号名、寄存器名、opcode值，不得使用模糊描述

## 附件资源

- `scripts/rtm_utils.py`: RTM文件读写工具
- `scripts/lrs_reader.py`: LRS文档解析工具（支持提取opcodes、registers、timing等）
- `examples/`: 参考示例文件
