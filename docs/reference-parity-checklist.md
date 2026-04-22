# Chenstack Reference Parity Checklist

Reference artifact: `D:\帕鲁修改器\PalworldTrainer-chenstack-0.13.1.exe`

Last refreshed: `2026-04-22`

## Current summary

- `same-ish`
  - 顶层页签顺序和命名已经对齐参考版。
  - 可见聊天输入不再作为主路径，优先走 bridge，请求不可隐藏时才回退到参考兼容静默模式。
- `improved`
  - `*添加物品` 已改成参考版的分类页签 + 搜索Id/名称 + 数量 + 一键添加流程。
  - `*添加帕鲁` 已改成参考版的顶层分类页签 + 收藏夹 + 搜索/生成主流程。
  - `传送和移速` 已改成参考版的分组 / 坐标列表 / 坐标读写 / 联机传送工作区。
  - `常用功能` 与 `联机功能` 已去掉明显偏离参考版的旧工具入口，改成参考风格的常用操作与内部分页。
- `missing`
  - `帕鲁修改` 的深度属性读写、`*联机帕鲁修改` 的真实联机改写、`制作和建造` 的大部分限制绕过项，底层还没有完全接齐。

## Top-level pages

| Reference page | Current state | Parity | Notes |
| --- | --- | --- | --- |
| `关于` | 环境/路径/状态页仍保留，但顶层命名已对齐 | same-ish | 仍承担 open-source 诊断职责 |
| `常用功能` | 已重构 | improved | 去掉本地工具入口，保留常用链路 |
| `制作和建造` | 已重构 | partial | 当前先接 `unlockrecipes` 相关链路 |
| `角色属性` | 仍是偏功能化页面 | partial | 现有桥接/属性写入链路可用，但界面仍未完全按参考版单机属性编辑铺开 |
| `帕鲁修改` | 已重构结构 | partial | 5 个内页签已对齐，深度写入未齐 |
| `*联机帕鲁修改` | 已重构结构 | partial | 入口和导航已对齐，真实联机改写未齐 |
| `*添加物品` | 已重构 | improved | 16 个分类页签与参考版一致 |
| `*添加帕鲁` | 已重构 | improved | 5 个分类页签与收藏流程已对齐 |
| `联机功能` | 已重构 | improved | 已切成 `玩家修改 / 其他 / *透视` |
| `传送和移速` | 已重构 | improved | 已切成参考版的工作区结构 |
| `更新记录` | 保留 | same-ish | 仍为 changelog 页 |

## Reference evidence now captured

- Top-level tabs:
  - `关于 / 常用功能 / 制作和建造 / 角色属性 / 帕鲁修改 / *联机帕鲁修改 / *添加物品 / *添加帕鲁 / 联机功能 / 传送和移速 / 更新记录`
- `*添加物品` inner tabs:
  - `新物品(0.7.0) / 次新物品(0.6.0) / 次新物品(0.5.0) / 素材 / 食材 / 消耗品 / 技能果实 / 重要物品 / 设计图 / 帕鲁球 / 滑翔伞 / 武器 / 弹药 / 防具 / 装饰 / 全部`
- `*添加帕鲁` inner tabs:
  - `塔主 / 帕鲁 / 狂暴 / NPC 人类 / NPC 通缉犯`
- `联机功能` inner tabs:
  - `玩家修改 / 其他 / *透视`
- `帕鲁修改` inner tabs:
  - `基本属性 / 更多数据 / 主动技能 / 习得技能 / 被动词条`
- `传送和移速` work area:
  - `分组`
  - `坐标列表`
  - `坐标`
  - `名称 / X坐标 / Y坐标 / Z坐标`
  - `*联机传送(单机也支持)`

## Execution path

| Behavior | Current state | Parity |
| --- | --- | --- |
| 隐藏执行命令 | bridge hidden commands 可用时优先使用 | same-ish |
| 兼容静默命令 | hidden registry 不可用时回退到 suppressed SendInput | same-ish |
| 飞行 / 传送 / 倍率 | 走 bridge request/toggles | improved |
| 可见聊天输入 | 已不再作为主流程显式暴露 | fixed |

## Validation completed

- Unit/UI:
  - `pytest -q tests` -> pass
- Live smoke against the running game:
  - `fly on/off`
  - `坐标读取 / 联机传送`
  - `移速倍率 / 跳跃倍率`
  - `*添加物品`
  - `*添加帕鲁`
  - `设置时间`
  - `解锁传送点`
  - `常用功能` toggles
  - `联机功能` give exp / stamina / fly
