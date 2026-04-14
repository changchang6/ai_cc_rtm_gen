---
name:rtm_chk_tc_gen
description:依据LRS文件和现有RTM文件，补充完善RTM文件
allowed-tools:Read,Edit,Grep
---

依据工作目录下的RTM excel文件和LRS word文件，生成新的RTM excel文件，遵循以下步骤：

1.从源文件提取信息

2.新的RTM文件包含源RTM的所有内容

3.在新的RTM文件中，按照填写要求，填写sheet Checker List和DV Testcase List的内容，使Checker和Testcase可以覆盖TP中的所有条目，将对应的Checker和Testcase编号填写到sheet FL-TP对应的TP条目后

4.检查生成的RTM excel文件格式和源RTM一致，检查生成的Checker和Testcase符合填写要求，检查所有的TP都有对应的Checker和Testcase覆盖

##注意事项
-不要修改源文件
-生成的RTM excel格式和源RTM一致

##附件资源
最终RTM excel文件内容和格式可参考examples文件夹下的RTM excel文件