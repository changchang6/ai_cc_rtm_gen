---
name:rtm_chk_tc_gen
description:依据LRS文件和RTM文件中的DR-FL、FL-TP，生成RTM文件中的Checker List、DV Testcase List
allowed-tools:Read,Edit,Grep,python
---

你是一名芯片验证工程师，依据工作目录下的RTM excel文件和LRS word文件，生成新的RTM excel文件，遵循以下步骤：

1.生成新的RTM excel文件
-新的RTM文件首先复制源RTM的所有内容

2.理解源文件中现有信息
-理解源LRS word文件中DR-FL、FL-TP信息，DR-FL是从硬件设计文档中提取的硬件功能点，FL-TP是对应每条功能点的测试点
-Checker List是测试用例测试测试点时，通过检查这些条目能够判断测试点的功能正确性
-DV Testcase List是每条测试点对应的具体测试用例，测试用例必须涵盖所有测试点
-理解LRS word中对硬件设计的介绍，包括Testcase、Checker中涉及的具体硬件寄存器、信号

3.在新的RTM文件中，填写sheet Checker List和DV Testcase List，使Checker和Testcase可以覆盖所有TP，将对应的Checker和Testcase编号填写到sheet FL-TP对应的TP条目后
-每页内容的填写需遵循每页的填写要求、说明
-TC描述需包含Testcase的配置条件、输入激励、期望结果、coverage check点
-FL-TP页中Testpoint对应的checker和Testcae编号分别对应于Checker List、DV Testcase List中检查、测试相应测试点的条目

4.检查新的RTM excel文件
-生成的Checker和Testcase符合填写要求
-检查所有的TP都有Checker List、DV Testcase List中的Checker和Testcase覆盖
-检查新RTM中包含源文件中DR-FL、FL-TP、填写要求、说明信息
-格式和源RTM一致，包括各个sheet内容的字体、填充颜色、表格边框

##注意事项
-不要修改源文件

##附件资源
最终RTM excel文件填写内容和格式可参考examples文件夹下的RTM excel文件