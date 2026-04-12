# Palworld 修改器 · 傻瓜版

一个开箱即用的 Palworld 修改器：下载 `PalworldTrainer.exe`，双击打开，进游戏，然后点按钮就行。

所有功能都是标准 Windows GUI，中文界面、分类清晰，不用记任何命令。

---

## 能做什么

![Tabs](https://img.shields.io/badge/Tabs-7-blue) &nbsp; ![Items](https://img.shields.io/badge/物品-1900%2B-green) &nbsp; ![Pals](https://img.shields.io/badge/帕鲁-600%2B-orange) &nbsp; ![Tech](https://img.shields.io/badge/科技-500%2B-purple)

| Tab | 功能 |
|-----|------|
| **主页** | 游戏状态面板、启动游戏、部署 UE4SS Bridge、打开游戏目录 |
| **玩家** | 切换飞行、脱困、打印坐标、解锁所有传送点、一键解锁全部科技、自定义经验、坐标传送 |
| **物品** | 7 种快捷礼包（新手 / 高级材料 / 顶级装备 / 弹药 / 食物 / 捕获 / 科技），1900+ 物品搜索 + 双击即给 |
| **帕鲁** | 600+ 帕鲁搜索 + 双击即生成 |
| **科技** | 一键解锁全部科技、一键解锁全部传送点、500+ 单项科技搜索 |
| **世界** | 时间滑块 + 清晨 / 正午 / 黄昏 / 午夜一键切换 |
| **设置** | 游戏目录浏览、环境扫描报告 |

---

## 快速开始

1. **安装前置 mod**（只需要一次）：
   - [UE4SS Experimental (Palworld)](https://www.nexusmods.com/palworld)
   - [Client Cheat Commands](https://www.nexusmods.com/palworld)
   - 安装后在 `Mods/PalModSettings.ini` 里确认两个 mod 都在 `ActiveModList` 里。

2. **下载修改器**：
   去 [Releases](https://github.com/Boowenn/Palworld-Trainer/releases/latest) 下载 `PalworldTrainer-v1.0.0-win64.exe`。

3. **双击运行**。程序会自动定位 Palworld 安装目录，加载 1900+ 物品 / 600+ 帕鲁 / 500+ 科技目录。

4. **打开游戏，进到世界里**（单人模式或你自己开的房间）。

5. **点任意按钮**，例如：
   - 「🔓 解锁全部科技」
   - 「🎁 新手大礼包」
   - 「🦅 切换飞行 (开)」

   程序会自动把 Palworld 窗口拉到前台，按回车打开聊天框，敲入对应的 `@!` 命令，再回车发送。

---

## 工作原理

修改器本身**不碰游戏内存**。它只做两件事：

1. 通过 Win32 API (`FindWindow` + `SetForegroundWindow`) 定位并聚焦 Palworld 游戏窗口。
2. 通过 `SendInput` 把 `@!` 开头的聊天命令打到游戏聊天框里。

真正执行作弊逻辑的是第三方 mod [Client Cheat Commands](https://www.nexusmods.com/palworld)，它注册了所有 `@!unlockalltech`、`@!giveme`、`@!spawn` 等聊天命令。本程序只是一个**友好的图形界面包装**，帮你：

- 不用手动打命令
- 不用记物品 / 帕鲁 / 科技的内部 key
- 不用切到 `Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums/*.lua` 里找 id
- 按类别分好，方便批量操作

因为这样，它天然稳定、版本适配容易。

---

## 权限说明

- **单机 / 自己开房**：全部功能生效（你就是房主）。
- **加入别人的房间**：只有读取类命令（如坐标、显示帮助）保证生效。生成帕鲁、解锁科技这类修改共享世界状态的命令在非房主端通常会被主机拒绝——这是 Palworld 的 P2P 权威模型决定的，不是本程序的问题。

---

## 系统要求

- Windows 10 / 11 64-bit
- 已安装 Palworld
- 已安装 UE4SS Experimental (Palworld) + Client Cheat Commands
- 游戏以**窗口**或**无边框窗口**方式运行（独占全屏下按键注入不稳定）
- 游戏内聊天打开键保持默认的 Enter

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
    game_control.py   # Win32 窗口 + SendInput 注入
    commands.py       # @! 命令构建器 + 礼包定义
    catalog.py        # 物品/帕鲁/科技目录解析
    environment.py    # 游戏安装扫描 + bridge 部署
    config.py         # 设置持久化
    data/enums/       # 打包进 exe 的 ClientCheatCommands 目录快照
integrations/ue4ss/PalworldTrainerBridge/
    Scripts/main.lua  # 可选的 UE4SS 诊断脚本（由修改器部署按钮写入游戏目录）
```

---

## 许可与致谢

- 游戏内作弊命令由 [KoZ 的 Client Cheat Commands](https://www.nexusmods.com/palworld) 提供，本程序仅做 GUI 包装。
- UE4SS 运行时由 [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) 团队提供。
- 物品 / 帕鲁 / 科技目录快照来自 ClientCheatCommands 的 `enums/*.lua`（自动从 Palworld Dataminer 生成），随本程序一同分发。

本程序仅供**单机或自建房间娱乐使用**。不要用它去骚扰别人的服务器或影响他人游戏体验。
