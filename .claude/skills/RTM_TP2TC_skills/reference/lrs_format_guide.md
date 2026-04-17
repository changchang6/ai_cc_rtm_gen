# LRS Document Format Guide

This document describes the expected format of LRS (Logic Requirements Specification) Word documents and how to extract key information for RTM generation.

---

## Expected LRS Document Structure

A typical LRS document contains the following sections:

1. **Overview/Introduction** - 模块概述
2. **Interface Signals** - 接口信号定义
3. **Functional Requirements** - 功能需求
4. **Register Definition** - 寄存器定义
5. **Timing Requirements** - 时序要求
6. **Protocol Specification** - 协议规范
7. **Error Handling** - 错误处理
8. **DFX Requirements** - DFX需求

---

## Key Information to Extract

### 1. Interface Signals (接口信号)

**提取命令**:
```bash
python3 scripts/lrs_reader.py read <lrs_file.docx>
```

**关键信息**:
- 信号名 (Signal Name)
- 方向 (Direction: In/Out)
- 位宽 (Width)
- 功能描述 (Description)

**典型格式**:
| 信号名 | 方向 | 位宽 | 描述 |
|--------|------|------|------|
| clk_i | In | 1 | 主时钟 |
| rst_ni | In | 1 | 低有效复位 |
| pcs_n_i | In | 1 | 片选，低有效 |
| pdi_i[3:0] | In | 4 | 输入数据 |
| pdo_o[3:0] | Out | 4 | 输出数据 |
| pdo_oe_o | Out | 1 | 输出使能 |
| test_mode_i | In | 1 | 测试模式使能 |

**在Checker/Testcase中使用**:
```
Checker示例: 检查pcs_n_i定义帧边界，pdi_i/pdo_o在clk_i上升沿采样
Testcase示例: 配置test_mode_i=1，发送数据到pdi_i[3:0]
```

---

### 2. Opcodes (操作码定义)

**提取命令**:
```bash
python3 scripts/lrs_reader.py opcodes <lrs_file.docx>
```

**典型格式**:
| Opcode | 名称 | 功能描述 |
|--------|------|----------|
| 0x10 | WR_CSR | CSR写操作 |
| 0x11 | RD_CSR | CSR读操作 |
| 0x20 | AHB_WR32 | AHB 32位写 |
| 0x21 | AHB_RD32 | AHB 32位读 |

**在Checker/Testcase中使用**:
```
Checker示例: 检查opcode译码正确：0x10译码为WR_CSR命令
Testcase示例: 发送opcode=0x10执行WR_CSR命令，发送opcode=0xFF验证非法opcode检测
```

---

### 3. Registers (寄存器定义)

**提取命令**:
```bash
python3 scripts/lrs_reader.py registers <lrs_file.docx>
```

**典型格式**:
| 寄存器名 | 地址 | 字段 | 复位值 | 访问属性 |
|----------|------|------|--------|----------|
| VERSION | 0x00 | VERSION[31:0] | 0x00010000 | RO |
| CTRL | 0x04 | EN[0], LANE_MODE[2:1], SOFT_RST[3] | 0x00000002 | RW |
| STATUS | 0x08 | BUSY[0], DONE[1], ERR[2] | 0x00000000 | RO |
| LAST_ERR | 0x0C | ERR_CODE[7:0] | 0x00000000 | RO |

**字段详解**:
```
CTRL.EN: 模块使能，1=使能，0=禁用
CTRL.LANE_MODE: 通道模式，00=1-bit, 01=4-bit
CTRL.SOFT_RST: 软复位触发，写1触发复位
```

**在Checker/Testcase中使用**:
```
Checker示例: 检查CTRL.EN默认值为0，LANE_MODE默认值为01
Testcase示例: 配置CTRL.EN=1使能模块，配置CTRL.LANE_MODE=00选择1-bit模式
```

---

### 4. Timing Requirements (时序要求)

**提取命令**:
```bash
python3 scripts/lrs_reader.py timing <lrs_file.docx>
```

**关键时序参数**:
| 参数 | 值 | 描述 |
|------|-----|------|
| turnaround_cycles | 1 | 请求/响应之间的周转周期 |
| setup_time | X ns | 建立时间 |
| hold_time | Y ns | 保持时间 |
| timeout | Z cycles | 超时计数 |

**在Checker/Testcase中使用**:
```
Checker示例: 检查请求/响应之间存在1个clk_i的turnaround周期
Testcase示例: 验证turnaround固定1周期，验证超时检测功能
```

---

### 5. Protocol Specification (协议规范)

**典型协议格式**:

**帧结构**:
```
请求帧: [opcode(8bit)] [addr(32bit)] [data(32bit)]
响应帧: [status(8bit)] [rdata(32bit)]
```

**传输顺序**:
- MSB first
- 高nibble优先 (4-bit模式)

**在Checker/Testcase中使用**:
```
Checker示例: 检查协议字段按MSB first传输
Testcase示例: 在4-bit模式下验证pdi_i[3:0]按高nibble优先发送
```

---

### 6. Error Codes (错误码定义)

**典型错误码格式**:
| 状态码 | 名称 | 触发条件 |
|--------|------|----------|
| 0x00 | SUCCESS | 操作成功 |
| 0x01 | BAD_OPCODE | 非法opcode |
| 0x02 | BAD_REG | 非法寄存器地址 |
| 0x03 | ALIGN_ERR | 地址未对齐 |
| 0x04 | DISABLED | 模块未使能 |
| 0x05 | NOT_IN_TEST | 非测试模式 |
| 0x06 | FRAME_ERR | 帧错误 |
| 0x07 | AHB_ERR | AHB总线错误 |
| 0x08 | TIMEOUT | 超时 |

**在Checker/Testcase中使用**:
```
Checker示例: 检查错误码生成正确：非法opcode返回0x01
Testcase示例: 发送非法opcode(0x00/0xFF)验证BAD_OPCODE错误(0x01)
```

---

## Complete Key Info Extraction

**综合提取命令**:
```bash
python3 scripts/lrs_reader.py key_info <lrs_file.docx>
```

This command extracts all key design information including:
- interface_signals: 接口信号列表
- opcodes: 操作码定义
- registers: 寄存器定义
- timing: 时序要求
- functional_requirements: 功能需求

---

## LRS Section Headings to Look For

When reading an LRS document manually, look for these common heading patterns:

| 中文标题 | English Title | 关键信息 |
|----------|---------------|----------|
| 接口信号 / 端口定义 | Interface Signals / Ports | 信号名、方向、位宽 |
| 功能需求 / 功能描述 | Functional Requirements | 功能点列表 |
| 寄存器定义 / CSR定义 | Register Definition | 寄存器名、字段、地址 |
| 时序要求 / 时序图 | Timing Requirements | 时序参数 |
| 协议规范 / 通信协议 | Protocol Specification | 帧格式、传输顺序 |
| 错误处理 / 异常处理 | Error Handling | 错误类型、状态码 |
| DFX / DFT | DFX Requirements | 测试模式、调试接口 |
| 低功耗设计 | Low Power Design | 时钟门控、电源管理 |

---

## Table Classification Guide

The `lrs_reader.py` script automatically classifies tables based on headers:

| Header Keywords | Table Type |
|-----------------|------------|
| 信号, signal | interface_signals |
| opcode, 操作码 | opcodes |
| 寄存器, register, CSR | registers |
| 时序, timing | timing |

---

## Best Practices for LRS-based RTM Generation

1. **先提取关键信息**: 在生成Checker/Testcase前，先运行`key_info`提取所有关键信息
2. **引用具体名称**: 所有描述必须引用LRS中的具体信号名、寄存器名、opcode值
3. **保持一致性**: Checker/Testcase中使用的名称必须与LRS完全一致
4. **检查完整性**: 确保所有TP都有对应的Checker和Testcase覆盖

---

## Example: TBUS_LRS_v1.1.docx Key Info

```json
{
  "interface_signals": [
    ["pcs_n_i", "In", "1", "片选，低有效"],
    ["pdi_i", "In", "4", "输入数据"],
    ["pdo_o", "Out", "4", "输出数据"],
    ["pdo_oe_o", "Out", "1", "输出使能"],
    ["clk_i", "In", "1", "主时钟"],
    ["rst_ni", "In", "1", "低有效复位"],
    ["test_mode_i", "In", "1", "测试模式使能"]
  ],
  "opcodes": [
    {"opcode": "0x10", "name": "WR_CSR", "description": "CSR写"},
    {"opcode": "0x11", "name": "RD_CSR", "description": "CSR读"},
    {"opcode": "0x20", "name": "AHB_WR32", "description": "AHB 32位写"},
    {"opcode": "0x21", "name": "AHB_RD32", "description": "AHB 32位读"}
  ],
  "registers": [
    {"name": "CTRL", "fields": ["EN", "LANE_MODE", "SOFT_RST"]},
    {"name": "STATUS", "fields": ["BUSY", "DONE", "ERR"]},
    {"name": "LAST_ERR", "fields": ["ERR_CODE"]}
  ],
  "timing": {
    "turnaround_cycles": "1个clk_i周期"
  }
}
```

---

## Common Extraction Issues

1. **表格格式不一致**: 不同LRS文档的表格格式可能略有差异
2. **命名规范差异**: 有些用驼峰命名，有些用下划线命名
3. **分散的信息**: 同一类型信息可能分散在多个章节

**解决方案**: 提取后人工核对关键信息，确保引用正确。
