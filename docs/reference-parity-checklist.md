# Chenstack Reference Parity Checklist

Reference artifact: `D:\帕鲁修改器\PalworldTrainer-chenstack-0.13.1.exe`

## Top-level pages

| Reference page | Current repo state | Parity | Action |
| --- | --- | --- | --- |
| `关于` | 已改成顶层第一页，承载环境/目录/诊断 | same-ish | 继续补参考说明文本 |
| `常用功能` | 已保留并对齐为主流程入口 | same-ish | 继续补参考常用开关 |
| `制作和建造` | 已由原 `科技` 页承接 | partial | 继续补建造限制相关功能 |
| `角色属性` | 已由原 `角色` 页承接 | partial | 继续补属性读写字段 |
| `帕鲁修改` | 已补同名入口和子页骨架 | missing | 继续补真实编辑字段 |
| `*联机帕鲁修改` | 已补同名入口 | missing | 继续补高级联机帕鲁操作 |
| `*添加物品` | 已重命名并保留主功能 | partial | 继续补参考分类视图 |
| `*添加帕鲁` | 已重命名并保留主功能 | partial | 继续补参考子分类/字段页 |
| `联机功能` | 已补同名入口 | partial | 继续补参考按钮与透视入口 |
| `传送和移速` | 已由原 `坐标` 页承接 | partial | 继续补参考列表/分组细节 |
| `更新记录` | 已补顶层页 | partial | 继续接入真实更新记录文本 |

## Execution path

| Behavior | Current repo state | Parity | Action |
| --- | --- | --- | --- |
| 可见聊天命令输入/自动打字 | 已从主执行链路移除 | fixed | 不再回退到 `SendInput` |
| 隐藏命令执行 | 走桥接 `run_hidden_commands` | same-ish | 继续扩展桥接覆盖面 |
| 飞行/传送/坐标读取 | 优先走桥接 request/status | same-ish | 继续做真实会话烟测 |

## Known extra or conflicting areas

- 原 `命令` 页和自由命令思路与参考版冲突，已从主界面移除。
- 原 `高级` 内存扫描入口与参考版主流程冲突，已从顶层移除。
- 旧的可见聊天框回退与参考版冲突，已移除主链路。
