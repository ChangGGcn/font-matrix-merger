# 技术文档

[English](README.md) | **简体中文**

本文档对应 **v0.2.1**。参数默认值和支持行为以源码为准。

## 阅读路径

首次使用先看[使用指南](zh-CN/usage.md)。策略参数见[合并 API](zh-CN/merge-api.md)，webfont 分片见[同源分片与验证](zh-CN/subsets-and-verification.md)。处理实际输入前应阅读[支持边界](zh-CN/limitations.md)。高级 API 与常用流程分开说明。

| 主题 | 内容 |
| --- | --- |
| [安装、CLI 与完整使用示例](zh-CN/usage.md) | 安装目录、交互输入和可运行流程 |
| [合并 API 与策略参数](zh-CN/merge-api.md) | 加载、逐级合并、策略默认值及问答键 |
| [格式、命名、布局及辅助 API](zh-CN/helper-api.md) | 格式转换、命名、变换、布局/表及保存辅助接口 |
| [同源分片与验证](zh-CN/subsets-and-verification.md) | 分片标签、所有权、验证关键字和报告结构 |
| [轴映射与可变数据合成](zh-CN/variation-model.md) | 坐标空间、支撑细化、CFF2 及数学接口 |
| [合并流程与数据不变量](zh-CN/architecture.md) | 类型分派、复制路径、布局及合并收尾 |
| [模块与脚本参考](zh-CN/script-reference.md) | 运行库、测试与构建文件的职责和命令参数 |
| [支持边界与故障排查](zh-CN/limitations.md) | 未支持场景、降级、证据与诊断 |
| [完整源码签名索引](zh-CN/parameter-index.md) | 69 个源码文件与 613 个定义 |

## 范围与证据

- API 页面给出形参默认值、单位、返回值与输入所有权。签名索引也列出内部辅助函数，不代表这些函数是稳定公共接口。
- 源码链接按仓库目录给出。运行 ZIP 包含本文档和库，不收录仅用于仓库开发的测试与构建工具。
- 历史验证结果单独标注。fontTools 保存成功不等于已验证所有排版引擎、轴位置或 Windows 栅格行为。
- 行文遵循 [Academic Humanizer](https://github.com/AIScientists-Dev/academic-humanizer)：术语准确，句子简短，结论与证据相称，不用宣传性保证。

[项目 README](../README.zh-CN.md) · [版本历史](../CHANGELOG.md) · [协议](../LICENSE)
