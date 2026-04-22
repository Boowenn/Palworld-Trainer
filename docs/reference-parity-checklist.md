# Chenstack Reference Parity Checklist

Reference artifact: `D:\帕鲁修改器\PalworldTrainer-chenstack-0.13.1.exe`

Last refreshed: `2026-04-22`

## Current summary

- `same`
  - Top-level flow matches the reference family: `关于 / 常用功能 / 制作和建造 / 角色属性 / 帕鲁修改 / *联机帕鲁修改 / *添加物品 / *添加帕鲁 / 传送和移速 / 联机功能 / 更新记录`.
  - Main execution path stays hidden-first: bridge request/toggles when available, suppressed compatibility input otherwise. No visible chat typing is the primary path.
- `improved`
  - `制作和建造` is no longer a stub. It now exposes build/world shortcuts plus tech quick-unlock, full-tech search, and group unlock flow.
  - `帕鲁修改` now exposes all 5 reference tabs with real actions: duplicate pal, pal memory workbench, skill fruits, passive implants, and support items.
  - `*联机帕鲁修改` now exposes real room-owner / co-op flows instead of placeholder text: duplicate pal plus separate co-op skill/passive/support item panels.
- `no blocking conflicting items`
  - The three pages targeted in this pass no longer route the user back into unrelated legacy tabs as the main workflow.

## Top-level pages

| Reference page | Current state | Parity | Notes |
| --- | --- | --- | --- |
| `关于` | 已对齐 | same | 环境检测、状态说明、更新记录入口保留。 |
| `常用功能` | 已对齐 | same | 常用勾选、世界快捷和常用页面跳转已稳定。 |
| `制作和建造` | 已重做 | improved | 建造兼容动作、科技整组解锁、科技搜索与常用世界快捷已收回主页。 |
| `角色属性` | 已对齐 | same | 保持当前稳定主链路，不在本轮改动。 |
| `帕鲁修改` | 已重做 | improved | 5 个子页全部有实际入口，不再是说明页。 |
| `*联机帕鲁修改` | 已重做 | improved | 联机复制、技能果实、被动词条、培养补给全部独立成页内主流程。 |
| `*添加物品` | 已对齐 | same | 16 分类页签与搜索流程保持稳定。 |
| `*添加帕鲁` | 已对齐 | same | 5 分类页签、收藏与详情工作区保持稳定。 |
| `传送和移速` | 已对齐 | same | 工作区、列表、收藏、路径传送保持稳定。 |
| `联机功能` | 已对齐 | same | 玩家修改 / 其他 / 透视结构保持稳定。 |
| `更新记录` | 已对齐 | same | 维持参考版风格入口。 |

## Changed Areas In This Pass

### 制作和建造

- Reference evidence used:
  - Changelog evidence for `制作和建造无视需求`
  - Changelog evidence for `临时解锁全建造和制作样式`
  - Reference top-level page placement from UIAutomation evidence
- Current implementation:
  - `制作和建造无视需求`
  - `临时解锁全建造和制作样式`
  - `解锁全部科技`
  - `解锁所有传送点`
  - `给满绿胖子像`
  - `科技快捷 / 全部科技 / 搜索 Id / 名称`
- Parity: `improved`
- Planned next action: only if future evidence reveals stable extra build-restriction command names or bridge hooks.

### 帕鲁修改

- Reference evidence used:
  - UIAutomation evidence for 5 nested tabs
  - Changelog evidence for `复制帕鲁`
  - Changelog evidence for `帕鲁刷出4条被动词条`
  - Changelog evidence for `修改帕鲁信赖度`
  - Changelog evidence for `修改帕鲁界面，被动词条布局优化，加上滚动条，技能加上描述`
- Current implementation:
  - `基本属性`: pal memory workbench for level / exp / IVs plus duplicate pal
  - `更多数据`: trust / hunger / mood workbench plus support items
  - `主动技能`: skill-fruit search + grant
  - `习得技能`: separate learned-skill item workflow
  - `被动词条`: passive implant search + grant
- Parity: `improved`
- Planned next action: only if future low-level hooks allow true selected-pal field write without scan flow.

### *联机帕鲁修改

- Reference evidence used:
  - Top-level page placement from UIAutomation evidence
  - Changelog evidence for multiplayer / room-owner pal flows
  - Changelog evidence for `复制帕鲁（单机和4人房主）`
- Current implementation:
  - `复制当前准心帕鲁`
  - `联机技能果实`
  - `联机被动词条`
  - `联机培养补给`
  - direct navigation to `帕鲁修改 / *添加帕鲁 / 联机功能`
- Parity: `improved`
- Planned next action: only if future live evidence proves more room-owner-specific field write hooks.

## Execution Path

| Behavior | Current state | Parity |
| --- | --- | --- |
| Hidden command execution | bridge hidden request first, suppressed fallback second | same |
| Visible chat typing | not the primary path | same |
| Teleport / fly / speed | bridge request or bridge toggles | same |
| Item / pal / tech grant | hidden command dispatch through bridge-compatible path | same |

## Validation Completed

- Unit/UI:
  - `pytest -q tests` -> `96 passed`
- Live smoke against the running game on `2026-04-22`:
  - `@!unlockrecipes`
  - `@!giveme SkillCard_Apocalypse 1`
  - `@!giveme PalPassiveSkillChange_SwimSpeed_up_2 1`
  - `@!giveme PAL_Growth_Stone_L 1`
  - `@!duplast`
  - memory attach / detach path in the pal-edit workbench
