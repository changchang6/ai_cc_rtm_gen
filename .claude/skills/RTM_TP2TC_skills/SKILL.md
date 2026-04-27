---
name: RTM_TP2TC_skills
description: 依据LRS文件和RTM文件中的DR-FL、FL-TP，生成RTM文件中的Checker List、DV Testcase List。当用户需要为芯片验证生成RTM文档、填写Checker列表或DV Testcase列表时使用此技能。
allowed-tools: Read,Edit,Grep,Bash(python3:*)
---

你是一名资深芯片验证工程师，依据工作目录下的RTM excel文件和LRS文档（支持.docx和.md格式），生成新的RTM excel文件。

## 工作流程

### 步骤1: 理解输入文件

首先使用提供的脚本读取文件结构：

```bash
# 读取RTM文件结构
python3 scripts/rtm_utils.py read RTM_AI.xlsx

# 读取LRS文档结构（Word格式）
python3 scripts/lrs_reader.py read TBUS_LRS_v1.1.docx
```

**注意**：如果LRS文件为Markdown格式（.md），直接使用Read工具读取文件内容并解析关键信息。

理解以下关键信息：
- **DR-FL**: 硬件功能点列表，包含DR编号、Feature类别、FL编号、Feature描述
- **FL-TP**: 测试点列表，每个功能点对应一个或多个测试点(TP)
- **Checker List**: 验证检查点，用于判断测试点的功能正确性
   checker核心职责：检查结果，判断对错
   checker工作性质：被动的、监控型的。它观察设计的”反应”。
   checker关注焦点：”做得对不对”。设计的行为、时序、数据、协议是否符合规范。
- **DV Testcase List**: 具体测试用例，需涵盖所有测试点
   testcase核心职责：生成激励，创造测试场景。
   testcase工作性质：主动的、驱动型的。它向设计施加”刺激”。
   testcase关注焦点：”做什么测试”。覆盖哪些功能点、场景、边界条件或协议要求。

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

#### 1.6.1 功能覆盖率模型

**必须定义功能覆盖率**以指导随机测试：

```
covergroup rtm_functional_cg;
    // Lane mode 覆盖
    lane_mode_cp: coverpoint lane_mode_i {
        bins lane_1bit  = {2'b00};
        bins lane_4bit  = {2'b01};
        bins lane_8bit  = {2'b10};
        bins lane_16bit = {2'b11};
    }
    
    // Opcode 覆盖
    opcode_cp: coverpoint opcode_latched_q {
        bins wr_csr    = {8'h10};
        bins rd_csr    = {8'h11};
        bins ahb_wr32  = {8'h20};
        bins ahb_rd32  = {8'h21};
        bins ahb_wr_burst = {8'h22};
        bins ahb_rd_burst = {8'h23};
        bins illegal   = default;
    }
    
    // Burst length 覆盖
    burst_len_cp: coverpoint burst_len_latched_q {
        bins single = {1};
        bins incr4  = {4};
        bins incr8  = {8};
        bins incr16 = {16};
        bins illegal = default;
    }
    
    // 状态码覆盖
    status_cp: coverpoint status_code {
        bins ok        = {8'h00};
        bins frame_err = {8'h01};
        bins bad_opcode = {8'h02};
        bins not_in_test = {8'h04};
        bins disabled   = {8'h08};
        bins bad_reg    = {8'h10};
        bins align_err  = {8'h20};
        bins ahb_err    = {8'h40};
        bins bad_burst  = {8'h80};
        bins burst_bound = {8'h81};
    }
    
    // 状态机覆盖
    front_fsm_cp: coverpoint front_state_q {
        bins states[] = {[0:5]}; // IDLE/ISSUE/WAIT_RESP/TA/TX/TX_BURST
    }
    
    axi_fsm_cp: coverpoint axi_state_q {
        bins states[] = {[0:5]}; // AXI_IDLE/REQ/BURST/WAIT/DONE/ERR
    }
    
    // 交叉覆盖
    lane_opcode_cross: cross lane_mode_cp, opcode_cp;
    opcode_status_cross: cross opcode_cp, status_cp;
endcovergroup
```

**后续生成的Testcase必须覆盖所有的功能覆盖率**

### 步骤2: 生成新的RTM文件

新的RTM文件需保留源RTM的所有内容（DR-FL、FL-TP、填写要求等）。

### 步骤3: 填写DV Testcase List

生成测试用例，包括**基础测试用例**和**随机测试用例**。

#### 3.1 随机测试用例类型

**必须生成以下类型的随机测试用例**：

| 类型 | 描述 | 示例 |
|------|------|------|
| 配置随机化 | 遍历所有有效配置组合 | lane_mode(1/4/8/16-bit) × opcode(6种) × burst_len(1/4/8/16) |
| 数据随机化 | 随机数据payload、随机地址 | 随机wdata/rdata，随机对齐地址 |
| 错误注入 | 随机注入各类错误 | hresp_i=1, timeout, frame_abort, 非法opcode |
| 交叉覆盖 | 多维度组合测试 | 所有lane_mode × 所有opcode × 成功/失败场景 |
| 边界测试 | 边界值和极限场景 | 最大burst_len, FIFO满/空, 地址边界 |

#### 3.2 随机测试用例模板

**配置随机化测试模板**：
```
配置条件：
1. 模块复位完成
2. test_mode_i=1，en_i=1
3. 随机配置lane_mode_i[1:0]（遍历2'b00/01/10/11）
4. 随机配置其他不关心信号

输入激励：
1. 随机选择opcode（遍历0x10/0x11/0x20/0x21/0x22/0x23）
2. 对于Burst命令，随机选择burst_len（遍历1/4/8/16）
3. 随机生成地址（addr需4-byte对齐）
4. 对于写命令，随机生成wdata
5. 重复执行N次（N≥100），每次随机配置

期望结果：
1. 成功场景：status_code=STS_OK(0x00)
2. 失败场景：返回对应错误码
3. 所有配置组合均被覆盖

coverage check点：
1. 覆盖lane_mode所有取值：2'b00, 2'b01, 2'b10, 2'b11
2. 覆盖所有opcode：0x10, 0x11, 0x20, 0x21, 0x22, 0x23
3. 覆盖所有burst_len：1, 4, 8, 16
4. 覆盖lane_mode × opcode所有组合
```

**错误注入测试模板**：
```
配置条件：
1. 模块复位完成
2. test_mode_i=1，en_i=1
3. 随机选择测试场景

输入激励：
1. 随机选择错误类型并注入：
   - 非法opcode(随机选择0x00~0x0F或0x24~0xFF)
   - 非法CSR地址(reg_addr随机>=0x40)
   - 非对齐地址(addr随机设置addr[1:0]!=0)
   - 非法burst_len(随机选择2,3,5,6,7,9~15)
   - 跨1KB边界地址
   - AHB错误响应(force hresp_i=1)
   - AHB超时(force hready_i=0持续256+周期)
2. 每种错误类型重复执行N次（N≥10）

期望结果：
1. 前置错误：返回对应错误码，不发起总线访问
2. AHB错误：返回STS_AHB_ERR(0x40)
3. Burst中途中止：已发射beat正常完成

coverage check点：
1. 覆盖所有状态码：0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x81
2. 覆盖错误优先级链各组合
3. 覆盖Burst中途错误中止场景
```

**交叉覆盖测试模板**：
```
配置条件：
1. 模块复位完成
2. 使用嵌套循环遍历所有组合

输入激励：
// 伪代码框架
for lane_mode in [2'b00, 2'b01, 2'b10, 2'b11]:
    for opcode in [0x10, 0x11, 0x20, 0x21, 0x22, 0x23]:
        for burst_len in [1, 4, 8, 16]:  // 仅Burst命令
            for success_or_error in [success, error]:
                配置对应条件
                发送命令
                检查响应
                
期望结果：
1. 成功路径：status=0x00
2. 失败路径：返回正确错误码
3. 所有组合均被验证

coverage check点：
1. lane_mode × opcode × (success|error) 交叉覆盖率100%
2. burst_len × lane_mode 交叉覆盖率100%
3. 所有FSM状态跳转至少被触发一次
```

#### 3.3 testcase描述核心要求

**总体目标**：最终testcase数量应为TP数量的**1.1倍以上**

**每条Testcase描述总字数不少于400字符**

**TC完备性**：

1. **TC涵盖所有测试点**
2. **TC覆盖所有的合理的配置和激励的组合** 生成随机测试，通过循环和随机，覆盖合理配置和输入激励的所有组合
3. **TC可以使代码覆盖率和功能覆盖率达到100%** 
   - 所有寄存器的所有位至少有1个测试用例覆盖到
   - 所有状态机的所有状态和状态跳转至少有1个测试用例覆盖到
4. **随机测试用例数量**：每个TP应生成多个testcase（通常2-5个），包括正常场景、边界场景、错误场景、随机组合场景
5. **TC逻辑充分性**：每条期望结果必须能从输入激励中逻辑推导出来。如果期望结果声称验证了某属性，则输入激励必须包含证明该属性所需的完整操作序列，反例：仅读取RO寄存器就说"验证了RO属性"——读回默认值可能只是因为从未写入，不能排除写入会改变值的可能性。具体规则：
   - **属性验证型**（RO/RW/W1C/W0S等）：必须包含"写入-回读"完整序列。验证RO：先写再读，确认值不变；验证W1C：分别写1和写0，证明只有写1清除；验证RW：写后读回一致
   - **优先级/排序验证型**：必须先单独测试每个条件，再测试组合，三者对比证明优先级。不能把所有条件混在一起就声称验证了优先级链
   - **状态迁移验证型**：必须主动触发迁移（如active→idle），不能仅观测静态状态
   - **持续/粘滞属性验证型**：必须测试属性在中间操作后是否保持。如验证sticky错误，需在错误后插入成功操作，再检查错误仍存在
   - **定量声明验证型**：必须包含基线测量和对比。如验证功耗降低，需先测active基线再测idle

**TC各部分详细要求**：

**1. 配置条件要求**：
- 每条TC的配置条件必须包含**2-5条**具体配置
- 必须使用LRS中的具体寄存器名（如CTRL.EN、CTRL.LANE_MODE）
- 必须包含具体信号取值（如test_mode_i=1，en_i=1，lane_mode_i=2'b01）
- 格式：编号.具体配置；每条以分号结尾

**2. 输入激励要求**：
- 每条TC的输入激励必须包含**4-9步**操作
- 每步必须包含：
  - 具体opcode值（如opcode=0x10）
  - 具体寄存器地址和名称（如reg_addr=0x04(CTRL)）
  - 具体数据值（如wdata=0x00000001(CTRL.EN=1)）
  - 具体接口信号操作（如通过pdi_i[3:0]按MSB-first顺序发送）
- **输入激励可执行性**：不使用模糊描述。不写"触发各类错误条件"这种无法直接执行的描述，而要写"发送非法opcode(0x00/0xFF)验证BAD_OPCODE(0x02)"这种可直接执行的描述
- **输入激励的执行顺序**：明确每一步的操作，按顺序可以正常衔接。如果构造一种错误场景后无法立刻测试另一种错误，需要先复位和进行初始化配置。如果一个testcase中测试多个功能点不好衔接，可拆分为多个testcase
- **输入激励逻辑充分性**：在编写每条输入激励时，自问"这些激励步骤能否逻辑推导出所有期望结果？"。如果某条期望结果是"X属性被验证"，则激励中必须包含证明X属性所需的前提操作。典型反模式：(1)声称验证RO属性但只读不写；(2)声称验证优先级但未单独测试各条件；(3)声称验证状态迁移但未触发迁移；(4)声称验证sticky属性但未插入中间操作；(5)声称验证定量改善但无基线对比
- 格式：编号.具体操作；每条以分号结尾

**3. 期望结果要求**：
- 期望结果必须包含**3-6条**具体检查
- 每条必须包含：
  - 具体信号名和取值（如pdo_oe_o=0，htrans_o=2'b00(IDLE)）
  - 具体错误码和名称（如STS_BAD_REG(0x10)）
  - 具体状态机状态（如front_state=IDLE）
  - 具体寄存器值（如CTRL.EN=0，CTRL.LANE_MODE=2'b00）
- 格式：编号.具体期望；每条以分号结尾

**4. coverage check点要求**：
- 随机测试：描述功能覆盖率模型和需覆盖的维度
- 直接用例：写"直接用例覆盖，不收功能覆盖率"

**高质量Testcase示例**（基于实际LRS文档）：

```
test_reset_behavior
描述：
配置条件：
1.模块上电，clk_i稳定运行100MHz；
2.初始配置test_mode_i=1，en_i=1，lane_mode_i=2'b01（4-bit模式）；
输入激励：
1.拉低rst_ni触发异步复位（至少持续2个clk_i周期）；
2.释放rst_ni（同步释放）；
3.复位释放后发送RD_CSR命令（opcode=0x11，reg_addr=0x08读取STATUS寄存器）验证模块恢复工作；
4.再次拉低rst_ni触发复位，释放后检查复位状态；
期望结果：
1.复位后所有状态机回到IDLE态：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；
2.输出信号deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0；
3.pdo_o[15:0]=16'b0，协议上下文清空；
4.RX/TX FIFO清空：rxfifo_empty_o=1，txfifo_empty_o=1；
5.CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)；
6.复位释放后RD_CSR命令正常响应status_code=STS_OK(0x00)；
coverage check点：
直接用例覆盖，不收功能覆盖率

test_csr_access
描述：
配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.配置lane_mode_i=2'b01（4-bit模式）；
输入激励：
1.发送WR_CSR命令：opcode=0x10，reg_addr=0x04(CTRL)，wdata=0x00000001（CTRL.EN=1）；
2.发送RD_CSR命令：opcode=0x11，reg_addr=0x04(CTRL)，验证RW寄存器写入后读回一致；
3.发送WR_CSR命令：opcode=0x10，reg_addr=0x00(VERSION)，wdata=0xDEADBEEF（尝试写入RO寄存器）；
4.发送RD_CSR命令：opcode=0x11，reg_addr=0x00(VERSION)，验证RO寄存器值未改变；
5.发送WR_CSR命令：opcode=0x10，reg_addr=0x08(STATUS)，wdata=0xFFFFFFFF（尝试写入RO寄存器）；
6.发送RD_CSR命令：opcode=0x11，reg_addr=0x08(STATUS)，验证RO寄存器值未改变；
7.发送RD_CSR命令：opcode=0x11，reg_addr=0x40（超出0x00~0x3F范围），验证地址越界拒绝；
期望结果：
1.WR+RD_CSR(CTRL)：写入0x01后读回0x00000001，证明RW属性——写入值可读回；
2.WR+RD_CSR(VERSION)：尝试写入0xDEADBEEF后读回仍为复位默认值，证明RO属性——写入无效；
3.WR+RD_CSR(STATUS)：尝试写入0xFFFFFFFF后读回仍为复位默认值，证明RO属性——写入无效；
4.地址越界：返回STS_BAD_REG(0x10)，不发起CSR访问（无csr_rd_en_o脉冲）；
5.所有CSR写操作：csr_wr_en_o为单周期脉冲，同一周期内csr_addr_o和csr_wdata_o有效；
coverage check点：
对CSR地址范围0x00~0x3F收集功能覆盖率，覆盖RW/RO属性验证场景

test_mode_rejection
描述：
配置条件：
1.模块复位完成，lane_mode_i=2'b01（4-bit模式）；
输入激励：
1.设置test_mode_i=0，en_i=1；
2.发送RD_CSR命令：opcode=0x11，reg_addr=0x00；
3.检查响应帧status_code；
4.复位模块，设置test_mode_i=1，en_i=0；
5.发送WR_CSR命令：opcode=0x10，reg_addr=0x04，wdata=0x01；
6.检查响应帧status_code；
7.复位模块，设置test_mode_i=0，en_i=0（同时不满足）；
8.发送RD_CSR命令：opcode=0x11，reg_addr=0x00；
9.检查响应帧status_code；
期望结果：
1.test_mode_i=0时：返回STS_NOT_IN_TEST(0x04)，不发起CSR/AHB访问；
2.en_i=0时：返回STS_DISABLED(0x08)，不发起CSR/AHB访问；
3.test_mode_i=0且en_i=0时：返回STS_NOT_IN_TEST(0x04)（优先级STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08)）；
4.所有拒绝场景下csr_wr_en_o=0，csr_rd_en_o=0，htrans_o=IDLE；
coverage check点：
对test_mode_i和en_i的组合状态收集功能覆盖率

test_frame_boundary
描述：
配置条件：
1.模块复位完成，test_mode_i=1，en_i=1；
2.配置lane_mode_i=2'b01（4-bit模式），pcs_n_i初始为高电平；
输入激励：
1.正常帧传输：ATE拉低pcs_n_i开始帧传输，按MSB-first顺序通过pdi_i[3:0]发送RD_CSR帧(opcode=0x11+reg_addr=0x00)；
2.等待1个turnaround周期，检查pdo_oe_o拉高，模块驱动pdo_o[3:0]输出响应；
3.帧中止场景1：发送WR_CSR命令(opcode=0x10+reg_addr=0x04+wdata=0x01)但在接收8bit后(已锁存opcode)提前拉高pcs_n_i；
4.复位模块，帧中止场景2：发送RD_CSR命令但在接收4bit后(opcode未锁存，接收<8bit)提前拉高pcs_n_i；
期望结果：
1.正常帧：pcs_n_i=0期间接收数据，turnaround后pdo_oe_o=1驱动响应，status_code=STS_OK(0x00)；
2.帧中止场景1(opcode已锁存)：返回STS_FRAME_ERR(0x01)，pdo_oe_o拉高后输出状态码；
3.帧中止场景2(opcode未锁存)：接收状态静默复位，不产生frame_abort，不输出响应帧；
coverage check点：
对帧中止时机(opcode已锁存/未锁存)收集功能覆盖率
```

### 步骤4: 填写Checker List

生成Checker：

**生成的checker可以检查所有testcase的结果正确性**

Checker name：如果是SVA checker，需填写SVA property名字

**Checker描述核心要求**：

**每条Checker必须包含4-6条检查点，描述总字数不少于200字符**

**每个检查点必须包含以下要素**：
1. **具体信号名**（含完整位宽，如pdo_o[15:0]、htrans_o[1:0]）
2. **具体取值**（如16'b0、STS_BAD_REG(0x10)、IDLE）
3. **状态机状态列举**（如front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE）
4. **寄存器名**（如CTRL.EN、CTRL.LANE_MODE、LAST_ERR）
5. **协议参数**（如turnaround 1周期、hsize_o=3'b010）

**Checker描述格式要求**：
- 检查点格式：编号.具体描述；每条以分号结尾
- 标题说明检查目的
- 所有信号、寄存器、状态码名称必须来自LRS文档

**Checker与DV SPEC的区别**：
- RTM中描述**check的内容**（定性+定量）
- DV SPEC中描述**checker的实现方案**（SVA/scoreboard/文件对比）

**Checker性质定位**：
- **被动的、监控型的**，用于观察设计行为是否正确
- **不要写成testcase**，不包含测试步骤、激励注入、错误触发
- 例如"九步法检测寄存器（默认值、读写属性、异常地址检查）"属于testcase，不是checker

**高质量Checker示例**（基于实际LRS文档）：

```
reset_state_checker
描述：
检查rst_ni异步复位及同步释放后模块状态正确性：
1.复位后所有状态机回到IDLE态：front_state=IDLE，back_state=S_IDLE，axi_state=AXI_IDLE；
2.复位后所有输出deassert：pdo_oe_o=0，htrans_o=2'b00(IDLE)，csr_rd_en_o=0，csr_wr_en_o=0；
3.pdo_o[15:0]=16'b0，协议上下文清空；
4.RX/TX FIFO清空：rxfifo_empty_o=1，txfifo_empty_o=1；
5.CTRL.EN=0，CTRL.LANE_MODE=2'b00(1-bit默认)，LAST_ERR=0x00。

csr_access_checker
描述：
检查CSR接口读写时序正确性：
1.CSR写操作：csr_wr_en_o为单周期脉冲，同一周期内csr_addr_o和csr_wdata_o有效，外部CSR File在该上升沿采样完成写入；
2.CSR读操作：csr_rd_en_o为单周期脉冲，外部CSR File在下一周期将读数据稳定在csr_rdata_i[31:0]，模块在该周期采样（1 cycle读延迟）；
3.CSR有效地址范围0x00~0x3F，reg_addr>=0x40的访问在前置检查阶段即被拒绝，返回STS_BAD_REG(0x10)，不出现csr_rd_en_o/csr_wr_en_o脉冲；
4.寄存器属性正确：VERSION(0x00)为RO，CTRL(0x04)为RW，STATUS(0x08)为RO，LAST_ERR(0x0C)为RO。

error_priority_checker
描述：
检查错误优先级链和执行期错误检测正确性：
1.前置检查错误按固定优先级链返回(高→低)：STS_FRAME_ERR(0x01) > STS_BAD_OPCODE(0x02) > STS_NOT_IN_TEST(0x04) > STS_DISABLED(0x08) > STS_BAD_REG(0x10) > STS_ALIGN_ERR(0x20)；
2.任何前置错误均在发起CSR/AHB访问前收敛，不产生csr_wr_en_o/csr_rd_en_o/htrans_o脉冲；
3.STS_AHB_ERR(0x40)不在前置优先级链中：仅在前置检查全部通过后、AHB事务实际执行期间发生，与前置错误互斥；
4.AHB执行期错误：hresp_i=1时返回STS_AHB_ERR(0x40)；hready_i持续为0超过BUS_TIMEOUT_CYCLES(256)周期触发超时，返回STS_AHB_ERR(0x40)；
5.Burst内任一beat上hresp_i=1立即中止burst，进入AXI_ERR状态。

lane_mode_checker
描述：
检查lane_mode_i对应的通道宽度和数据信号使用正确性：
1.lane_mode_i=2'b00(1-bit模式)：仅使用pdi_i[0]/pdo_o[0]，pdi_i[15:1]忽略，pdo_o[15:1]驱动为0；RD_CSR帧16bit需16个周期接收；
2.lane_mode_i=2'b01(4-bit模式)：使用pdi_i[3:0]/pdo_o[3:0]，按高nibble优先发送；RD_CSR帧16bit需4个周期接收；
3.lane_mode_i在接收器(SLC_CAXIS)和发送器(SLC_SAXIS)中被连续组合采样，用于计算每拍移位宽度bpc(bits per clock)；
4.MVP版本不支持8-bit(2'b10)和16-bit(2'b11) lane模式。
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