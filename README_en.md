# 🚀 AI Credit Limit (AI Usage & Token Meter)

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GUI Framework](https://img.shields.io/badge/GUI-PyQt5-purple.svg)](https://www.riverbankcomputing.com/software/pyqt/)

**AI Credit Limit** is a modern, premium desktop dashboard designed for developers to monitor real-time AI quota usage, token consumption, 5-hour/weekly limit windows, and local session activities across installed AI IDEs and coding assistants.

---

## 🔗 Repositories

* **Gitee Repository**: [https://gitee.com/fangjiayu/ai-credit-limit.git](https://gitee.com/fangjiayu/ai-credit-limit.git)
* **GitHub Repository**: [https://github.com/mhxy13867806343/ai-credit-limit.git](https://github.com/mhxy13867806343/ai-credit-limit.git)

---

## ✨ Key Features

- 🤖 **Auto-Detection**: Automatically discovers installed AI IDEs and tools without tedious manual configuration.
- ⚡️ **Instant Startup Cache**: Loads cached quota states in 0.01 seconds, eliminating startup lag and blank screens.
- 📊 **Multi-Window Visualization**: Displays both **5-Hour** and **Weekly** quota windows, complete with individual rainbow gradient progress bars.
- ⏱ **Target-Timestamp Auto Refresh**: Supports background refresh intervals with precise timestamp countdowns that persist across application restarts.
- 🎨 **Modular Style Architecture**: Separates QSS stylesheet configurations into `theme.py` for easy customization.
- 👁 **Toggle Visibility**: Easily toggle the display of detected AI tools from the Settings menu.

---

## 🛠 Supported AI Development Tools

| AI Tool | Quota / Token Source | Details |
| :--- | :--- | :--- |
| **Codex** | Codex App Server API | Synchronizes account rate limits for 5-hour and 7-day windows |
| **Antigravity** | DevTools Models & Usage endpoint | Fetches Gemini & Claude/GPT 5-hour and weekly usage percentages |
| **Claude Code** | Local `~/.claude/projects` logs | Tracks input, cached input, and output tokens for today & 90 days |
| **WorkBuddy** | `~/.workbuddy/workbuddy.db` SQLite | Monitors session context size and token activity |

---

## 📦 Installation & Usage

### 1. Clone the repository

```bash
# Via Gitee
git clone https://gitee.com/fangjiayu/ai-credit-limit.git
cd ai-credit-limit

# Or via GitHub
git clone https://github.com/mhxy13867806343/ai-credit-limit.git
cd ai-credit-limit
```

### 2. Set up Virtual Environment & Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Launch the Application

```bash
python3 -m ai_credit_limit
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
