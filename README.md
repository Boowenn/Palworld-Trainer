# Palworld 修改器 · 参考版对齐版

一个尽量贴近桌面版 trainer 使用习惯的 Palworld 修改器：下载 `PalworldTrainer.exe`，双击打开，进游戏，然后点按钮就行。

当前主界面固定为参考版对齐的 `关于 / 常用功能 / 制作和建造 / 角色属性 / 帕鲁修改 / *联机帕鲁修改 / *添加物品 / *添加帕鲁 / 传送和移速 / 联机功能 / 更新记录` 十一个页签。主流程仍然保留傻瓜模式，不再把旧的自由命令页暴露给普通使用者。

`角色属性` 页的一键飞行、`传送和移速` 页的传送/Boss 直达/路径传送，会优先通过 `PalworldTrainerBridge` 直接和运行中的游戏同步；`添加物品`、`添加帕鲁`、地图/科技类功能则优先走 bridge 隐藏命令，拿不到隐藏注册表时自动回退到参考版兼容静默输入链路。

---

## 能做什么

![Tabs](https://img.shields.io/badge/Tabs-11-blue) &nbsp; ![Items](https://img.shields.io/badge/物品-1900%2B-green) &nbsp; ![Pals](https://img.shields.io/badge/帕鲁-600%2B-orange) &nbsp; ![Coords](https://img.shields.io/badge/坐标点-900%2B-orange)

| Tab | 功能 |
|-----|------|
| **关于 / 更新记录** | 环境诊断、目录状态、版本说明 |
| **常用功能** | 启动游戏、部署增强模块、打开游戏目录、脱困/回家/治疗/清状态、一键开图、解锁传送点、时间控制 |
| **制作和建造 / 角色属性** | 无敌/体力/负重/移速/跳跃增强、飞行、角色相关常用能力 |
| **帕鲁修改 / 联机帕鲁修改** | 参考版结构对齐中的帕鲁编辑入口 |
| **添加物品 / 添加帕鲁** | 1900+ 物品、600+ 帕鲁搜索，按名称或内部 ID 搜索，最近项和收藏 |
| **传送和移速** | 通用坐标库、收藏夹、Boss 直达、手动坐标传送、路径传送 |
| **联机功能** | 参考版结构对齐中的联机功能入口 |

> **注**：物品/帕鲁/世界解锁等功能依赖 [Client Cheat Commands](https://www.nexusmods.com/palworld)；角色增强与坐标桥接依赖本仓库附带的 `PalworldTrainerBridge`（会自动部署到 UE4SS Mods 目录）。

---

## 快速开始

1. **下载修改器**：
   去 [Releases](https://github.com/Boowenn/Palworld-Trainer/releases/latest) 下载最新的 `PalworldTrainer-vX.Y.Z-win64.exe`。

2. **双击运行**。程序会自动定位 Palworld 安装目录，加载 1900+ 物品 / 600+ 帕鲁 / 500+ 科技目录。

3. **打开游戏，进到世界里**（单人模式或你自己开的房间）。

4. **先看顶部状态栏**：
   - `游戏：运行中` 表示已检测到 Palworld 进程
   - `聊天命令：隐藏执行` 表示 bridge 原生隐藏命令在线
   - `聊天命令：兼容静默` 表示当前改走参考版兼容静默输入链路
   - `增强模块：原生模式 / 兼容模式` 表示飞行/坐标桥接这条链路已在线

5. **角色属性 / 传送和移速 页（傻瓜模式）**：
   - `角色属性` 页直接点「开启飞行 / 关闭飞行 / 读取当前位置」
   - `传送和移速` 页可以直接从通用坐标库、Boss 直达或收藏夹里选点位，然后点「直接传过去」
   - `路径传送` 支持每行一个 `X Y Z`

6. **添加物品 / 添加帕鲁页**：
   - 支持按名称或内部 ID 搜索
   - 双击列表即可执行
   - 最近使用和收藏会自动留在页内，方便重复操作

---

## 工作原理

修改器内部现在主要保留**两条实用路径**：

**路径一：隐藏命令 / 兼容静默输入**。优先通过 bridge 的 `run_hidden_commands` 执行命令；如果当前会话隐藏注册表不可用，但聊天抑制仍在线，就按参考版兼容方式用 `SendInput` 把 `@!giveme` / `@!spawn` / `@!unlocktech` 等命令送进游戏，并由 `PalworldTrainerBridge` 抑制可见聊天回显。

**路径二：UE4SS bridge**。`PalworldTrainerBridge` 在本地玩家对象上读写坐标、飞行和角色增强状态，trainer 通过 `status.json` / `request.json` / `toggles.json` 和它同步。

本程序帮你省掉的是：
- 不用手动打命令
- 不用记物品 / 帕鲁 / 科技的内部 key
- 不用切到 `Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums/*.lua` 里找 id
- 常用物品 / 帕鲁 / 坐标会在界面里自动沉淀成最近项和收藏项

---

## 权限说明

- **单机 / 自己开房**：全部功能生效（你就是房主）。
- **加入别人的房间**：只有读取类命令（如坐标、显示帮助）保证生效。生成帕鲁、解锁科技这类修改共享世界状态的命令在非房主端通常会被主机拒绝——这是 Palworld 的 P2P 权威模型决定的，不是本程序的问题。

---

## 系统要求

- Windows 10 / 11 64-bit
- 已安装 Palworld
- 聊天命令链路：需要 [Client Cheat Commands](https://www.nexusmods.com/palworld)（配套需要 UE4SS Experimental (Palworld)）
- 角色增强 / 坐标桥接链路：需要 UE4SS，trainer 会自动部署 `PalworldTrainerBridge`
- 游戏以**窗口**或**无边框窗口**方式运行时，聊天命令注入更稳定

---

## 从源码运行

```powershell
git clone https://github.com/Boowenn/Palworld-Trainer.git
cd Palworld-Trainer
python -m palworld_trainer
```

## 从源码打包

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Clean
```

构建产物在 `dist\PalworldTrainer.exe`。

## 运行测试

```powershell
python -m unittest discover -s tests
```

---

## 目录结构

```
src/palworld_trainer/
    app.py            # tkinter 主界面
    game_control.py   # Win32 窗口 + SendInput 注入（聊天命令路径）
    commands.py       # @! 命令构建器 + 礼包定义
    catalog.py        # 物品/帕鲁/科技目录解析
    memory.py         # OpenProcess / RPM / WPM / AOB & 值扫描
    mem_engine.py     # 扫描-缩小-锁定-冻结 工作流 + 后台 50 ms ticker
    environment.py    # 游戏安装扫描
    config.py         # 设置持久化
    data/enums/       # 打包进 exe 的 ClientCheatCommands 目录快照
```

---

## 许可与致谢

- 游戏内作弊命令由 [KoZ 的 Client Cheat Commands](https://www.nexusmods.com/palworld) 提供，本程序仅做 GUI 包装。
- UE4SS 运行时由 [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) 团队提供。
- 物品 / 帕鲁 / 科技目录快照来自 ClientCheatCommands 的 `enums/*.lua`（自动从 Palworld Dataminer 生成），随本程序一同分发。

本程序仅供**单机或自建房间娱乐使用**。不要用它去骚扰别人的服务器或影响他人游戏体验。
