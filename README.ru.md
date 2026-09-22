<div align="center">

# ⚡ Claude Pulse 3.1

**Лимиты Claude Code на рабочем столе и 5-часовое окно по расписанию**

[English](README.md) · **Русский**

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows)](https://github.com/VvVampirevvV/ClaudePulse)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![UI](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![License](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](LICENSE)
[![Download](https://img.shields.io/badge/Скачать-EXE%203.1-ef4444?style=for-the-badge)](https://github.com/VvVampirevvV/ClaudePulse/raw/main/dist/ClaudePulse.exe)

<p align="center">
  <img src="screenshot.png" alt="Claude Pulse" width="900" style="border-radius: 10px; border: 1px solid #3b3f54;" />
</p>

</div>

---

## 📖 Зачем это

У подписок Claude Pro и Max лимит считается 5-часовыми окнами: окно открывается первым запросом и сбрасывается ровно через 5 часов. Если начать работу в 14:00, лимит обновится только в 19:00, как раз в разгар работы.

**Claude Pulse** отправляет короткий запрос заранее, например в 09:00. Тогда окно сбросится к 14:00, и вы начнёте работу со свежим лимитом. Заодно программа показывает остаток лимитов и объясняет, на что они уходят.

---

## ✨ Возможности

### 📊 Настоящие лимиты
* Данные берутся из официальной команды `claude /usage`: процент 5-часового окна, недельного лимита и Fable, точное время сброса.
* Опрос идёт в фоне раз в 5 минут (настраивается) и лимит не тратит.
* Нет данных — программа так и пишет, вместо того чтобы подставлять заглушки.

### 🎯 Умный пинг: «свежий лимит к 14:00»
* Вы указываете, **к какому часу** нужен полный лимит, а программа сама пингует за 5 часов до него.
* Если нужный час ранний (например, 03:30), пинг уйдёт накануне вечером.
* Остались режимы «точное время» и «каждые N часов».

### 🔔 Предупреждения о лимитах
* Уведомление Windows, когда окно или неделя израсходованы на 80% и 95%. Пороги настраиваются.
* **Значок в трее меняет цвет:** зелёный → жёлтый → красный, серый — данных нет.

### 💡 На что уходят лимиты
* Блок «What's contributing to your limits usage» из `/usage`: переведён и снабжён советами. Пример: «82% расхода — при контексте больше 150k → между задачами делайте /clear или /compact».
* Можно смотреть за 24 часа и за 7 дней.

### 🌐 Русский и English
* Язык выбирается по Windows, переключается на лету в настройках.

### 🛠️ Интеграция с Windows
* Трей, автозапуск, пробуждение ПК к пингу, запуск без окна консоли, защита от второй копии.
* **Наверстывание:** если ПК был выключен в момент пинга, программа отправит его после запуска, но только если окно лимитов в этот момент закрыто.

> ⚠️ Каждый пинг — это настоящий запрос к модели, он тратит немного лимита. Самый дешёвый вариант — пресет **Claude Haiku**.

---

## 🚀 Установка

### Готовый EXE
1. Скачайте [`ClaudePulse.exe`](https://github.com/VvVampirevvV/ClaudePulse/raw/main/dist/ClaudePulse.exe) (он же в папке `dist/`).
2. Запустите, установка не нужна. Нужен установленный [Claude Code](https://docs.claude.com/claude-code) со входом по подписке Pro или Max.

### Из исходников
Нужен Python 3.10 или новее.
```bash
git clone https://github.com/VvVampirevvV/ClaudePulse.git
cd ClaudePulse
pip install -r requirements.txt
python main.py
```

### Сборка EXE
```bash
python build.py
```
Файл появится в `dist/ClaudePulse.exe`.

### Тесты
```bash
python -m unittest discover tests
```

---

## 📂 Структура

```
ClaudePulse/
├── main.py                  # Точка входа: окно + трей + планировщик
├── src/
│   ├── claude_parser.py     # Разбор вывода claude /usage и auth status
│   ├── usage_monitor.py     # Фоновый опрос лимитов, предупреждения
│   ├── scheduler.py         # Расписание: точное время / интервал / «свежий лимит к…»
│   ├── i18n.py              # Переводы RU / EN
│   ├── config.py            # Настройки в %APPDATA%\ClaudePulse\config.json
│   ├── runner.py            # Запуск команды без окна консоли
│   ├── notifications.py     # Уведомления Windows
│   ├── autostart.py         # Автозапуск через реестр
│   ├── single_instance.py   # Защита от второй копии
│   └── ui/                  # Окно, карточки, трей
└── tests/                   # Проверки логики без интерфейса
```

Настройки лежат в `%APPDATA%\ClaudePulse\config.json`. Переменная окружения `CLAUDEPULSE_HOME` задаёт другую папку, например для второго профиля.

---

## 👤 Автор

**Vv.Vampire.vV** ([@VvVampirevvV](https://github.com/VvVampirevvV))

## 📄 Лицензия

[MIT](LICENSE)
