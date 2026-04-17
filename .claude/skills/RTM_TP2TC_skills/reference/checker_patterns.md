# Checker Patterns Reference

This document provides categorized checker patterns for RTM generation. Checkers are **passive, monitoring** components that observe design behavior and verify correctness.

## Core Principle

**Checker核心职责**: 检查结果，判断对错
**Checker工作性质**: 被动的、监控型的。它观察设计的"反应"。
**Checker关注焦点**: "做得对不对"。设计的行为、时序、数据、协议是否符合规范。

---

## Category 1: Clock Checkers

### freq_checker (频率检查器)

**使用场景**: 验证时钟频率是否符合规格要求

**模板格式**:
```
freq_checker
描述：
1.检查频率值是否正确：连续采集时钟上升沿和下降沿并计算实际频率/周期，判断是否处于目标频率的允许误差范围内（±X%）；
2.检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在Y%内。
```

**示例** (来自RTM_CRG_BT):
```
freq_checker
描述：
1.检查频率值是否正确：在一定数量的时钟周期期间，每个时钟周期都采集时钟上升沿和下降沿并计算该周期的实际周期，判断是否处于目标频率的允许误差范围内（±3%）
2.检查时钟稳定性：在时钟输出阶段通过连续采样，对比相邻两个周期的频率偏差是否在3%内;
```

### duty_cycle_checker (占空比检查器)

**使用场景**: 验证时钟占空比是否符合要求

**模板格式**:
```
duty_cycle_checker
描述：
检查时钟占空比是否正确：通过监测高低电平持续时间来计算占空比比例；
固定50%占空比允许误差范围在±X%内；可调占空比误差允许范围在±Y%内
```

**示例**:
```
duty_cycle_checker
描述：
检查时钟占空比是否正确：通过监测高低电平持续时间来计算占空比比例；
固定50%占空比允许误差范围在±5%内；可调占空比误差允许范围在±10%内
```

### glitch_checker (毛刺检查器)

**使用场景**: 检测时钟信号上的毛刺和异常脉冲

**模板格式**:
```
glitch_checker
描述：
作为free run checker，以最大频率为基准来设置阈值（最大频率周期的X%），检测信号的最小脉宽是否符合要求（注意仿真timescale）。
```

**示例**:
```
glitch_checker
描述：
作为free run checker，以最大频率为基准来设置阈值（最大频率周期的40%），检测信号的最小脉宽是否符合要求（注意仿真timescale）。
```

### sync_checker (同步检查器)

**使用场景**: 验证两个时钟信号的同步性

**模板格式**:
```
sync_checker
描述：
比较两个时钟的相位差，确保在可接受的裕量内（最大频率时钟周期的X%）：
使用monitor捕获两个时钟的边沿事件，并记录时间戳；若源时钟和目标时钟的上升沿时间差大于裕量，则存在相位偏移，两时钟不同步。
```

**示例**:
```
sync_checker
描述：
比较两个时钟的相位差，确保在可接受的裕量内（最大频率时钟周期的10%）：
使用monitor捕获两个时钟的边沿事件，并记录时间戳；若源时钟和目标时钟的上升沿时间差大于裕量，则存在相位偏移，两时钟不同步。
```

---

## Category 2: Reset Checkers

### rst_checker (复位检查器)

**使用场景**: 验证复位连接性和复位行为

**模板格式**:
```
rst_checker
描述：
检查复位connectivity：是否正确连接至模块并生效；
包含主要复位信号：<列出复位信号名>；其中<信号名>负责<功能模块>的复位；<信号名>负责<功能模块>的全局复位，内部带复位的组件均受控
```

**示例**:
```
rst_checker
描述：
检查复位connectivity：是否正确连接至模块并生效；
包含两个主要复位信号：crg_rst_n和preset；其中preset负责clk_rg模块的总线复位；crg_rst_n负责时钟产生功能模块的全局复位，内部带复位的组件均受控
```

---

## Category 3: Register Checkers

### regs_checker (寄存器检查器)

**使用场景**: 验证寄存器读写属性和默认值

**模板格式**:
```
regs_checker
描述：
九步法检测寄存器：包含默认值、读写属性、异常地址读写检查等；
```

**注意**: 九步法包括：
1. 默认值检查
2. 读属性验证
3. 写属性验证
4. 读写一致性
5. 非法地址访问
6. 边界地址访问
7. 位域独立访问
8. 写保护功能
9. 寄存器复位值

---

## Category 4: Interface/Protocol Checkers

### protocol_checker (协议检查器)

**使用场景**: 验证接口协议时序和格式

**模板格式**:
```
<协议名>_checker
描述：
检查<接口名>协议时序：
1. 帧边界检测：<片选信号>定义帧起始和结束
2. 数据传输时序：<数据信号>在<时钟条件>下采样
3. 方向控制：<使能信号>正确切换输入输出方向
4. 协议字段：<字段列表>按MSB first传输
```

**示例**:
```
spi_protocol_checker
描述：
检查SPI协议时序：
1. 帧边界检测：pcs_n_i定义帧起始和结束
2. 数据传输时序：pdi_i[3:0]/pdo_o[3:0]在clk_i上升沿采样
3. 方向控制：pdo_oe_o正确切换输入输出方向
4. 协议字段：opcode、addr、data按MSB first传输
```

### timing_checker (时序检查器)

**使用场景**: 验证特定时序约束

**模板格式**:
```
timing_checker
描述：
检查<时序参数>：
<具体时序要求>，允许误差<范围>
```

---

## Category 5: Low-Power Checkers

### clk_gate_checker (时钟门控检查器)

**使用场景**: 验证时钟门控功能

**模板格式**:
```
clk_gate_checker
描述：
1.检查时钟gate逻辑，能正确关断或打开组件；
2.禁止时钟gate在高电平；
3.同时检查输出时钟不会有X或高阻状态。
```

### dvfs_checker (动态调频调压检查器)

**使用场景**: 验证DVFS顺序和策略

**模板格式**:
```
dvfs_checker
描述：
检查电压和频率调整的顺序：降频时应先降频率再降电压；升频时应先升电压再升频率；（存在只升降频率不调电压的场景，不要误检测）
```

---

## Category 6: Status/State Checkers

### status_checker (状态检查器)

**使用场景**: 监测模块状态信号

**模板格式**:
```
status_checker
描述：
监测模块状态：<状态信号列表>的复位初始状态、模式切换及正常输出的指示值是否正确；
```

**示例**:
```
status_checker
描述：
监测模块状态：*_busy信号的复位初始状态、模式切换及正常输出的指示值是否正确；
```

### scoreboard_checker (记分板检查器)

**使用场景**: 对比参考模型与实际输出

**模板格式**:
```
scoreboard_checker
描述：
将reference model中针对输入配置，预测模块以及中间节点期望的输出状态和信号，传送到scoreboard中与实际目标节点输出的状态和信号进行对比；主要涉及<检查项目列表>。
```

**示例**:
```
scoreboard_checker
描述：
将reference model中针对输入配置，预测模块以及中间节点期望的输出状态和信号，传送到scoreboard中与实际目标节点输出的状态和信号进行对比；主要涉及门控的启用和禁用、直通模式的启用和禁用、时钟的分频正确性、反压状态的监测。
```

---

## Category 7: DFX Checkers

### dft_checker (DFT检查器)

**使用场景**: 验证DFT模式切换和测试时钟

**模板格式**:
```
dft_checker
描述：
1.检查DFT模式切换时序（在dft_mode配置为高时，<控制信号>可以正常切换为<DFT信号>）；
2.检查测试模式下时钟是否符合预期；
```

**示例**:
```
dft_checker
描述：
1.检查DFT模式切换时序（在dft_mode配置为高时，gfreemux的clk_sel和cgm_diff_cfg_div的div_num_in可以正常切换为dvfs_sel和dvfs_div_num）；
2.检查测试模式下时钟是否符合预期；
```

---

## Category 8: Error/Exception Checkers

### error_checker (错误检查器)

**使用场景**: 验证错误检测和状态码生成

**模板格式**:
```
error_checker
描述：
检查<错误类型列表>的检测：
1. <错误类型1>：检测条件，期望状态码<值>
2. <错误类型2>：检测条件，期望状态码<值>
...
所有错误应在<阶段>前完成收敛
```

**示例**:
```
protocol_error_checker
描述：
检查协议错误的检测：
1. BAD_OPCODE：非法opcode检测，期望状态码0x01
2. FRAME_ERR：帧错误检测，期望状态码0x06
3. TIMEOUT：超时检测，期望状态码0x08
所有错误应在发起AHB访问前完成收敛
```

---

## Category 9: Special Function Checkers

### bypass_checker (旁路检查器)

**使用场景**: 验证bypass功能

**模板格式**:
```
bypass_checker
描述：
检查bypass配置能否生效且逻辑正确：<bypass信号列表>
```

**示例**:
```
bypass_checker
描述：
检查bypass配置能否生效且逻辑正确：pre_div内部div、clk_core内部div的bypass信号
```

---

## Common Mistakes to Avoid

1. **不要写成testcase**: Checker描述中不应包含具体测试步骤
   - ❌ 错误: "配置寄存器X，然后检查信号Y"
   - ✅ 正确: "检查信号Y在条件X下的取值范围"

2. **必须定性+定量**: 引用具体信号名和取值
   - ❌ 错误: "检查时钟是否正常"
   - ✅ 正确: "检查clk_i频率是否在100MHz±3%范围内"

3. **可代码实现**: Checker内容必须可以通过代码实现
   - 确保检查条件明确、可编程

4. **避免模糊描述**: 必须引用LRS中的具体名称
   - ❌ 错误: "检查输出数据正确性"
   - ✅ 正确: "检查pdo_o[3:0]与预期值一致"

---

## Checker Naming Convention

| 前缀 | 用途 |
|------|------|
| freq_ | 频率相关 |
| duty_ | 占空比相关 |
| glitch_ | 毛刺检测 |
| sync_ | 同步性检测 |
| rst_ | 复位相关 |
| regs_ | 寄存器相关 |
| clk_gate_ | 时钟门控 |
| status_ | 状态监测 |
| dft_ | DFT相关 |
| protocol_ | 协议相关 |
| error_ | 错误检测 |
