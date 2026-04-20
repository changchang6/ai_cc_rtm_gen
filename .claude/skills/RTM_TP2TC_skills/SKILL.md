---
name: RTM_TP2TC_skills
description: 依据LRS文件和RTM模板文件，填写RTM中的Checker List和DV Testcase List，生成完整的RTM文件。
allowed-tools: Read,Edit,Grep,Bash(python3:*)
---

你是一名资深芯片验证工程师，依据工作目录下的RTM excel文件和LRS word文件，生成新的RTM excel文件。

## 工作流程

### 步骤1: 理解输入文件

首先使用提供的脚本读取文件内容和格式：

1. **从模板文件提取信息**
   - 读取模板文件信息，理清组织结构
   - **DR-FL**: 硬件功能点列表，包含DR编号、Feature类别、FL编号、Feature描述
   - **FL-TP**: 测试点列表，每个功能点对应一个或多个测试点(TP)
   - **Checker List**: 验证检查点，用于判断测试点的功能正确性
   - **DV Testcase List**: 具体测试用例，需涵盖所有测试点

2. **解析模板格式**
   - 严格理解模板的结构布局信息 
   - 严格理解模板的合并与拆分结构
   - 严格理解模板的字体样式，包括字体类型/大小/颜色

3. **解析填写规则**
   - 理解模板中**填写说明**，是否必填

4. **按规则填入模板**
   - 严格遵循填写说明的要求
   - 保持与模板完全一致的格式
   - **模板表格放不下的内容，适当增加行列，线框、字体等格式都与模板一致**

### 步骤1.5: 提取关键设计信息

**重要**：在生成Checker和Testcase之前，必须先从LRS文档提取关键设计信息（寄存器、接口、操作码等），确保生成的描述引用具体名称。
**所有后续生成的Checker和Testcase必须引用这些提取的具体名称，不得使用模糊描述。**

### 步骤2: 生成新的RTM文件

新的RTM文件需保留模板RTM的必要内容（DR-FL、FL-TP、填写要求等）
- Checker和Testcase sheet中插入足够的行，用于内容填写，确保填写的内容不超出表格边界覆盖填写说明等内容

### 步骤3: 填写Checker List

生成覆盖所有TP的Checker

### 步骤4: 填写DV Testcase List

生成覆盖所有TP的Testcase

### 步骤5: 更新FL-TP链接

将生成的Checker和Testcase编号填写到FL-TP sheet对应的TP条目后：
- 多个TP可共享同一个Checker或Testcase，也可多个Checker或Testcase覆盖同一个TP

### 步骤6: 验证输出

检查生成的RTM文件：
- 新的RTM格式与模板RTM一致，**checker list中填写说明表格完好保留**
- 所有TP都有对应的Checker和Testcase覆盖
- **Checker描述引用LRS中的具体信号名和取值**
- TC描述包含配置条件、输入激励、期望结果、coverage check点
- **TC描述使用具体接口名、寄存器名、opcode值**

## 注意事项

- 不要修改源文件

## 附件资源

- `scripts/rtm_utils.py`: RTM文件读写工具
- `scripts/lrs_reader.py`: LRS文档解析工具（支持提取opcodes、registers、timing等）
- `examples/`: 参考示例文件
- `reference/checker_ref.md`: checker填写参考
- `reference/testcase_ref.md`: testcase填写参考