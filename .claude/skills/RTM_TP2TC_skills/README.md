// 该skill（RTM_TP2TC_skills）用于：根据LRS文件和RTM文件中的DR-FL、FL-TP，生成RTM文件中的Checker List、DV Testcase List。

// skill依赖项：Python；Claude code官方文档处理skill（document-skills）

// skill执行步骤：
1.在Claude code工作目录下的input_config.json中指定LRS和RTM模板文件的位置
2.进入claude code
3.进入plan mode
4.通过/RTM_TP2TC_skills命令启动skill

// 注意事项：
// 1.skill会将生成内容填入模板指定位置，所以需确保模板格式已提前设置好（包括单元格行数、格式等）
// 2.skill生成的RTM需要人工review修改，当前版本仍存在AI幻觉和Testcase完备性不足的问题
