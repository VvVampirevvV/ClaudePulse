# Changelog

## [3.2] — 2026-09-23

**Download:** `ClaudePulse.exe` below. Requires [Claude Code](https://docs.claude.com/claude-code) signed in with a Pro or Max plan.

### New
- **Next ping, front and centre.** A big card shows when the next ping goes out, the countdown and when you get a fresh limit.
- **Don't waste your limit.** A scheduled ping that would land in an already open window no longer goes out — it would not move the reset. The app pings one minute after that window resets instead. The card warns in advance when a ping will move. Manual "Ping now" always goes through.
- **Skip today** — pause pings until midnight, from the card or the tray. Pauses now survive a restart.
- **Actionable notifications.** Clicking a notification opens the app; ping notifications have a "Pause for 2 hours" button.
- **Update check.** Once a day the app asks GitHub for a newer release and shows a download button (can be turned off).
- **Log file.** The journal is saved to `%APPDATA%\ClaudePulse\logs\claudepulse.log`, including when the PC was asleep — handy for "why didn't it ping last night".
- Version details in the EXE properties and no UPX compression, which trips fewer antivirus heuristics.
- Bug report and feature request templates on GitHub.

### Fixed
- Single-instance check reads the Windows error code reliably.
- `build.py` now fails loudly when the build fails.

### Русский
- Крупный блок «Следующий пинг»: когда, через сколько, когда будет свежий лимит.
- Пинг не уходит в уже открытое окно (он бы только потратил лимит) — программа пингнёт сразу после его сброса.
- «Пропустить сегодня», клик по уведомлению открывает программу, кнопка «Пауза на 2 часа».
- Проверка обновлений раз в сутки, журнал сохраняется в файл.

## [3.1] — 2026-09-23

**Download:** `ClaudePulse.exe` below. Requires [Claude Code](https://docs.claude.com/claude-code) signed in with a Pro or Max plan.

### New
- **Fresh limit by…** — a schedule mode where you set when you need a full limit (say 14:00) and the app pings 5 hours earlier (09:00). Early targets ping the evening before.
- **Limit alerts** at 80% and 95% (configurable) for the 5-hour window and the weekly limit. The tray icon turns green → yellow → red.
- **Where your limits go** — the `/usage` breakdown (long context, subagents, parallel sessions, top skills and MCP servers), translated and paired with advice.
- **English interface.** The language follows Windows and can be switched on the fly.

### Fixed
- The app no longer uses ~75% of a CPU core in the background (now ~1%). It used to re-read your Claude session logs every second; limits now come from `claude /usage`, polled every 5 minutes.
- Limits and the countdown are real: they use the reset time from `/usage` instead of guesses and placeholders.
- "Catch up missed pings" actually works.
- Notification text can no longer be executed by PowerShell.
- Invalid times and numbers in settings are reported instead of breaking the save.

### Русский
- Режим «Свежий лимит к…», предупреждения на 80/95% и цветной значок в трее, карточка «На что уходят лимиты», английский интерфейс.
- Программа больше не грузит процессор (было ~75% ядра, стало ~1%), лимиты и таймер настоящие — из `claude /usage`.
