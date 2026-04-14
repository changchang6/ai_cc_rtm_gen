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

### 步骤2: 生成新的RTM文件

新的RTM文件需保留源RTM的所有内容（DR-FL、FL-TP、填写要求等）。

### 步骤3: 填写Checker List

根据LRS文档中的功能描述，为每个测试点生成对应的Checker：

**Checker描述要求：**
1. 需要定性+定量描述，具体到check的信号、取值
2. 包含具体的检查步骤和预期值
3. 与DV SPEC的区别：RTM中描述check的内容，DV SPEC中描述实现方案

**示例Checker格式：**
```
CHK_XXX: checker_name
描述：
1. 检查[具体信号]的[具体行为]
2. 验证[条件]时[期望值]
3. 确认[时序要求]满足
```

### 步骤4: 填写DV Testcase List

为每个测试点生成对应的Testcase：

**TC描述必须包含四个部分：**
1. **配置条件**: 模块使能条件、寄存器配置、接口状态
2. **输入激励**: 具体命令序列、数据模式、时序要求
3. **期望结果**: 预期输出、状态变化、返回值
4. **coverage check点**: 功能覆盖率收集要求（直接用例覆盖则标注"不收功能覆盖率"）

**示例Testcase格式：**
```
TC_XXX: testcase_name
配置条件：
1. 模块使能：test_mode_i=1，CTRL.EN=1
2. 配置LANE_MODE=XX

输入激励：
1. 发送[命令]验证[功能]
2. 检查[信号]状态

期望结果：
1. [具体预期行为]
2. STATUS=0x00（成功）

coverage check点：
直接用例覆盖，不收功能覆盖率。
```

### 步骤5: 更新FL-TP链接

将生成的Checker和Testcase编号填写到FL-TP sheet对应的TP条目后：
- Column E: checker编号
- Column F: Testcase编号

### 步骤6: 验证输出

检查生成的RTM文件：
- 所有TP都有对应的Checker和Testcase覆盖
- Checker描述符合定性+定量要求
- TC描述包含配置条件、输入激励、期望结果、coverage check点
- 格式与源RTM一致

## 常见Checker类型

| 类别 | 检查内容示例 |
|------|-------------|
| 时钟 | 频率稳定性、时钟域同步 |
| 复位 | 状态机IDLE、寄存器默认值、上下文清空 |
| 寄存器 | 读写正确性、字段配置生效 |
| 接口 | 信号时序、协议符合性 |
| 协议 | 帧格式、命令序列、状态转换 |
| 异常 | 错误检测、错误码返回、错误恢复 |

## 注意事项

- 不要修改源文件
- Checker编号和Testcase编号需与TP编号对应
- 多个TP可共享同一个Checker或Testcase
- 保留源RTM中的填写要求和说明信息

## 附件资源

- `scripts/rtm_utils.py`: RTM文件读写工具
- `scripts/lrs_reader.py`: LRS文档解析工具
- `examples/`: 参考示例文件
