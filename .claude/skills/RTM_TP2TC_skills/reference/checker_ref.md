## Checker特征
- checker核心职责：检查结果，用于判断测试点的功能正确性
- checker工作性质：被动的、监控型的。它观察设计的“反应”。
- checker关注焦点：“做得对不对”。设计的行为、时序、数据、协议是否符合规范。

**Checker描述要求**：
1. 需要定性+定量描述，必须引用LRS中的具体信号名、取值
2. 包含具体的检查内容（寄存器、信号、时序、状态机跳转等）和预期值
3. **被动的、监控型的**。不要写成testcase，即checker描述中不包含具体的测试步骤，如九步法检测寄存器：包含默认值、读写属性、异常地址读写检查，这种写法属于testcase
4. 可通过代码实现。checker的内容在测试环境中可以使用代码实现。

**Checker描述必须包含**：
- 具体信号名（从LRS interface_signals提取）
- 具体取值范围或条件
- 具体时序要求（从LRS提取）

**示例Checker格式**（基于LRS中的实际信号）：
```
clk_freq_checker
描述：
1.检查频率值是否正确：连续采集时钟上升沿和下降沿并计算实际频率/周期，判断是否处于目标频率的允许误差范围内（±1%）；
2.检查时钟稳定性：通过连续采样周期，对比相邻两个周期的频率偏差是否在3%内。

dvfs_checker
描述：
检查电压和频率调整的顺序：降频时应先降频率再降电压；升频时应先升电压再升频率；（存在只升降频率不调电压的场景，不要误检测）

DMA_checker
描述：
对于DMA功能，检查能否正常触发DMA请求，以及能否进行DMA数据搬运，包括:
1、DMA发送数据请求：验证在THR或TX_FIFO中数据量为空或小于等于阈值时，dma_tx_req会变为高电平，当THR或TX_FIFO中数据量不为空或大于阈值时,
dma_tx_req会变为低电平，撤销发送请求;
2、DMA发送数据搬运：配置DMA_SAR、DMA_DAR、DMA_CTRL、DMA_CFG以及DMA_CHEN，验证当dma_tx_req拉高时，DMA将数据写入THR或
TX_FIFO，写入的数据通过sout发送出去，DMA写入的数据与sout发送的数据一致;
3、DMA接收数据请求：验证在RBR或RX_FIFO中数据量不为空或大于等于阈值时，dma_1x_req会变为高电平，当RBR或RX_FIFO中数据量为空或小于阈值时,
dma_1x_req会变为低电平，撤销接收请求;
4、DMA接收数据搬运：配置DMA_SAR、DMA_DAR、DMA_CTRL、DMA_CFG以及DMA_CHEN，验证当dma_1x_req拉高时，DMA从RBR或RX_FIFO读出数
据，DMA读出的数据与sin接收的数据一致;
```

## 常见Checker检查内容
| 类别 | 检查内容示例 |
|------|-------------|
| 时钟 | clk_i频率稳定性、时钟域同步 |
| 复位 | rst_ni异步复位、状态机IDLE、寄存器默认值 |
| 寄存器 | CTRL/STATUS读写正确性、字段配置生效 |
| 接口 | pcs_n_i帧边界、pdi_i/pdo_o时序、pdo_oe_o方向控制 |
| 协议 | opcode解析、帧格式、turnaround周期 |
| 异常 | FRAME_ERR、BAD_OPCODE、TIMEOUT检测 |