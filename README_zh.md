# 🚀 AI Credit Limit (AI 额度与 Token 监控仪表盘)

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GUI Framework](https://img.shields.io/badge/GUI-PyQt5-purple.svg)](https://www.riverbankcomputing.com/software/pyqt/)

**AI Credit Limit** 是一款专为开发者打造的高颜值、现代化的 AI 开发工具额度与 Token 消耗本地实时监控仪表盘。

支持自动动态检测本机安装的各类 AI IDE 及 AI 编程辅助工具，实时采集计算账号剩余额度、5小时/周配额窗口、本地 Token 活动记录与会话上下文，帮助开发者精准把控 AI 额度。

---

## 🔗 代码仓库地址

* **Gitee 镜像仓库**: [https://gitee.com/fangjiayu/ai-credit-limit.git](https://gitee.com/fangjiayu/ai-credit-limit.git)
* **GitHub 官方仓库**: [https://github.com/mhxy13867806343/ai-credit-limit.git](https://github.com/mhxy13867806343/ai-credit-limit.git)

---

## ✨ 核心特性

- 🤖 **自动动态检测**：自动搜寻与识别本机安装的 AI IDE 与 AI 辅助工具，无需复杂手动配置。
- 🖥 **macOS 菜单栏 / Windows 托盘**：常驻系统托盘，5 秒轮播展示各大 AI 工具动态，鼠标悬停即刻预览全局配额，无需频繁弹窗。
- ⚡️ **秒开本地缓存**：内置本地持久化缓存机制，打开应用 0.01 秒瞬间加载上次配额面板，杜绝启动白屏等待。
- 📊 **多维度额度可视化**：同时展示 **5小时额度 (5h)** 与 **周额度 (Weekly)**，每项配额配备独属的彩虹动态渐变进度条。
- ⏱ **精准倒计时自动刷新**：支持 5分钟至 24小时 自动刷新周期，基于目标时间戳精准倒数，重启或手动刷新不重置既定周期。
- 🎨 **组件化与样式解耦**：采用模块化架构设计，界面 CSS (QSS) 样式独立提取至 `theme.py` 配置文件，易于定制与二次开发。
- 👁 **自由切换显示**：设置对话框中可自由勾选或取消勾选各大 AI 工具的展示与隐藏。

---

## 🛠 支持的 AI 开发工具

| AI 工具 | 额度 / Token 来源 | 说明 |
| :--- | :--- | :--- |
| **Codex** | Codex App Server 实时 API | 自动同步账号 5小时 & 7天窗口剩余百分比与重置倒计时 |
| **Antigravity** | DevTools Models & Usage 调试通道 | 自动同步 Gemini & Claude/GPT 周额度与 5小时额度 |
| **Claude Code** | 本地 `~/.claude/projects` 会话日志 | 统计今日与近 90 天输入、缓存、输出 Token 消耗 |
| **WorkBuddy** | `~/.workbuddy/workbuddy.db` SQLite 数据 | 同步最新会话上下文容量比例与 Session Token 活动 |

---

## 📦 应用打包构建指南 (macOS / Windows)

项目内置自动化打包脚本 `build.py`：

### macOS 独立应用打包 (`.app`)

```bash
python3 build.py
```
打包成功后，产物位于 `dist/AICreditLimit.app`，拖入 `/Applications` 文件夹即可双击启动。软件将自动嵌入 **macOS 右上角菜单栏**。

### Windows 独立应用打包 (`.exe`)

在 Windows 命令提示符或 PowerShell 中执行：
```cmd
pip install -r requirements.txt
python build.py
```
打包成功后，产物位于 `dist/AICreditLimit/AICreditLimit.exe`，启动后常驻 **Windows 右下角任务栏托盘**。

---

## 📦 安装与运行指南

### 1. 克隆代码仓库

```bash
# 使用 Gitee
git clone https://gitee.com/fangjiayu/ai-credit-limit.git
cd ai-credit-limit

# 或使用 GitHub
git clone https://github.com/mhxy13867806343/ai-credit-limit.git
cd ai-credit-limit
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建 Python 虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装项目依赖 (PyQt5)
pip install -r requirements.txt
```

### 3. 启动应用

```bash
python3 -m ai_credit_limit
```

---

## 🏗 代码架构设计

```
ai_credit_limit/
├── __init__.py          # 包版本信息
├── app.py               # 主窗口 MainWindow 与应用启动入口
├── detectors.py         # 自动检测与数据扫描分流器
├── theme.py             # 全局 QSS 样式表与调色板配置文件
├── ui_usage_card.py     # 额度卡片与细分带进度条面板组件
├── ui_auto_refresh.py   # 自动刷新按钮与定时器弹出面板
├── ui_dialogs.py        # 设置与隐藏开关控制对话框
├── ui_utils.py          # 图标生成与格式化辅助工具
├── config.py            # 配置文件与持久化缓存读写
└── models.py            # 核心数据模型 (CreditUsage, QuotaItem 等)
```

---

## 📜 开源许可

本项目遵循 [MIT License](LICENSE) 开源许可协议。
