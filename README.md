<div align="center">

# ⚡ Claude Pulse 3.1

**Your Claude Code limits on the desktop — and the 5-hour window opened on schedule**

**English** · [Русский](README.ru.md)

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows)](https://github.com/VvVampirevvV/ClaudePulse)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](LICENSE)
[![Release](https://img.shields.io/github/v/release/VvVampirevvV/ClaudePulse?style=for-the-badge&color=ef4444&label=Download)](https://github.com/VvVampirevvV/ClaudePulse/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/VvVampirevvV/ClaudePulse/ci.yml?branch=main&style=for-the-badge&label=tests)](https://github.com/VvVampirevvV/ClaudePulse/actions)

<p align="center">
  <img src="screenshot.png" alt="Claude Pulse" width="900" style="border-radius: 10px; border: 1px solid #3b3f54;" />
</p>

</div>

---

## 📖 Why

Claude Pro and Max limits work in 5-hour windows: a window opens with your first request and resets exactly 5 hours later. Start work at 14:00 and your limit only refreshes at 19:00, in the middle of your day.

**Claude Pulse** sends a tiny request ahead of time, say at 09:00. The window then resets by 14:00, so you start with a fresh limit. It also shows how much of your limits is left and explains what uses them up.

---

## ✨ Features

### 📊 Real limits
* Data comes from the official `claude /usage` command: 5-hour window, weekly limit and Fable usage, with exact reset times.
* Polled in the background every 5 minutes (configurable) without using your limit.
* When there is no data, the app says so instead of showing placeholders.

### 🎯 Smart ping: "fresh limit by 14:00"
* Set **when** you need a full limit and the app pings 5 hours earlier.
* For early targets (e.g. 03:30) the ping goes out the evening before.
* The "exact time" and "every N hours" modes are still there.

### 🔔 Limit alerts
* A Windows notification when the window or the week hits 80% and 95% (configurable).
* **The tray icon changes color:** green → yellow → red, grey when there is no data.

### 💡 Where your limits go
* The "What's contributing to your limits usage" block from `/usage`, translated and paired with advice. Example: "82% of usage — with context over 150k → use /clear or /compact between tasks".
* View the last 24 hours or 7 days.

### 🌐 English and Russian
* Language follows Windows and can be switched on the fly in settings.

### 🛠️ Windows integration
* Tray, start with Windows, wake the PC for a ping, hidden console, single instance.
* **Catch-up:** if the PC was off at ping time, the ping is sent after the app starts, but only if the limit window is closed at that moment.

> ⚠️ Every ping is a real model request and uses a little of your limit. The **Claude Haiku** preset is the cheapest.

---

## 🚀 Install

### Prebuilt EXE
1. Download [`ClaudePulse.exe`](https://github.com/VvVampirevvV/ClaudePulse/releases/latest/download/ClaudePulse.exe) from the [latest release](https://github.com/VvVampirevvV/ClaudePulse/releases/latest).
2. Run it, no installer needed. You need [Claude Code](https://docs.claude.com/claude-code) installed and signed in with a Pro or Max plan.
3. The EXE is not code-signed, so Windows SmartScreen may warn on first launch: click **More info → Run anyway**. Every release is built from this source code by [GitHub Actions](https://github.com/VvVampirevvV/ClaudePulse/actions).

### From source
Requires Python 3.10+.
```bash
git clone https://github.com/VvVampirevvV/ClaudePulse.git
cd ClaudePulse
pip install -r requirements.txt
python main.py
```

### Build the EXE
```bash
python build.py
```
The file lands in `dist/ClaudePulse.exe`.

### Releasing
Push a tag like `v3.2`: GitHub Actions runs the tests, builds the EXE and publishes a release with the matching section of [CHANGELOG.md](CHANGELOG.md).

### Tests
```bash
python -m unittest discover tests
```

Settings live in `%APPDATA%\ClaudePulse\config.json`. Set the `CLAUDEPULSE_HOME` environment variable to use another folder, e.g. for a second profile.

---

## 👤 Author

**Vv.Vampire.vV** ([@VvVampirevvV](https://github.com/VvVampirevvV))

## 📄 License

[MIT](LICENSE)
