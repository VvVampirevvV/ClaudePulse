"""Проверки логики без интерфейса: python -m unittest discover tests"""
import os
import sys
import tempfile
import time
import unittest

# Тесты не должны трогать настоящие настройки пользователя
os.environ["CLAUDEPULSE_HOME"] = tempfile.mkdtemp(prefix="claudepulse-test-")
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.claude_parser import parse_usage, parse_reset, parse_tips
from src.scheduler import ping_time_for_target, planned_slots, parse_hhmm
from src.i18n import set_lang, t, RU, EN
from src.ui.tray import usage_level

MSK = ZoneInfo("Europe/Moscow")

USAGE_SAMPLE = """You are currently using your subscription to power your Claude Code usage

Current session: 62% used · resets Sep 23, 4am (Europe/Moscow)
Current week (all models): 76% used · resets Sep 23, 8am (Europe/Moscow)
Current week (Fable): 55% used · resets Sep 23, 8am (Europe/Moscow)

What's contributing to your limits usage?
Approximate, based on local sessions on this machine — does not include other devices or claude.ai. Behaviors are independent characteristics, not a breakdown.

Last 24h · 865 requests · 5 sessions
  82% of your usage was at >150k context
  77% of your usage came from subagent-heavy sessions
  Top skills: /claude-api 5%
  Top MCP servers: Claude Browser 11%

Last 7d · 868 requests · 8 sessions
  82% of your usage was at >150k context
"""


class ParseUsageTest(unittest.TestCase):
    def test_full_sample(self):
        now = datetime(2026, 9, 23, 1, 0, tzinfo=MSK)
        d = parse_usage(USAGE_SAMPLE, now)
        self.assertTrue(d["has_data"])
        self.assertEqual(d["session_pct"], 62)
        self.assertEqual(d["session_reset"], datetime(2026, 9, 23, 4, 0, tzinfo=MSK))
        self.assertEqual(d["weekly_pct"], 76)
        self.assertEqual(d["weekly_reset"], datetime(2026, 9, 23, 8, 0, tzinfo=MSK))
        self.assertEqual(d["fable_pct"], 55)
        self.assertEqual([b["period"] for b in d["tips"]], ["24h", "7d"])
        self.assertEqual(d["tips"][0]["requests"], 865)
        self.assertEqual(len(d["tips"][0]["items"]), 4)

    def test_garbage_gives_no_data(self):
        d = parse_usage("I can't reach that path from this session")
        self.assertFalse(d["has_data"])
        self.assertIsNone(d["session_pct"])

    def test_session_without_reset(self):
        d = parse_usage("Current session: 0% used\nCurrent week (all models): 3% used · resets Oct 1, 8am (Europe/Moscow)")
        self.assertEqual(d["session_pct"], 0)
        self.assertIsNone(d["session_reset"])
        self.assertEqual(d["weekly_pct"], 3)


class ParseResetTest(unittest.TestCase):
    def test_pm_and_minutes(self):
        now = datetime(2026, 9, 23, 1, 0, tzinfo=MSK)
        self.assertEqual(parse_reset("Sep 23, 6:30pm (Europe/Moscow)", now), datetime(2026, 9, 23, 18, 30, tzinfo=MSK))
        self.assertEqual(parse_reset("Sep 23, 12am (Europe/Moscow)", now), datetime(2026, 9, 23, 0, 0, tzinfo=MSK))

    def test_year_rollover(self):
        now = datetime(2026, 12, 30, 12, 0, tzinfo=MSK)
        self.assertEqual(parse_reset("Jan 2, 8am (Europe/Moscow)", now).year, 2027)

    def test_time_only_goes_forward(self):
        now = datetime(2026, 9, 23, 10, 0, tzinfo=MSK)
        dt = parse_reset("4am (Europe/Moscow)", now)
        self.assertEqual(dt, datetime(2026, 9, 24, 4, 0, tzinfo=MSK))

    def test_other_timezone(self):
        now = datetime(2026, 9, 23, 1, 0, tzinfo=timezone.utc)
        dt = parse_reset("Sep 23, 4am (America/New_York)", now)
        self.assertEqual(dt.utcoffset(), timedelta(hours=-4))


class SmartPingTest(unittest.TestCase):
    def test_same_day(self):
        self.assertEqual(ping_time_for_target("14:00"), (9, 0, 0))
        self.assertEqual(ping_time_for_target("05:00"), (0, 0, 0))

    def test_previous_day(self):
        self.assertEqual(ping_time_for_target("03:30"), (22, 30, -1))

    def test_bad(self):
        self.assertIsNone(ping_time_for_target("25:00"))
        self.assertIsNone(parse_hhmm("abc"))

    def test_slots_shift_weekday(self):
        # Свежий лимит в понедельник 03:00 -> пинг в воскресенье 22:00
        slots = planned_slots({"mode": "target", "days": ["Пн"], "target_times": ["03:00"]})
        self.assertEqual(slots, [(6, 22, 0)])
        slots = planned_slots({"mode": "target", "days": ["Пн", "Вт"], "target_times": ["14:00"]})
        self.assertEqual(slots, [(0, 9, 0), (1, 9, 0)])

    def test_fixed_ignores_bad_times(self):
        slots = planned_slots({"mode": "fixed", "days": ["Ср"], "times": ["08:00", "99:99"]})
        self.assertEqual(slots, [(2, 8, 0)])


class TrayLevelTest(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(usage_level(None, [80, 95]), "unknown")
        self.assertEqual(usage_level(79, [80, 95]), "ok")
        self.assertEqual(usage_level(80, [80, 95]), "warn")
        self.assertEqual(usage_level(95, [80, 95]), "critical")


class I18nTest(unittest.TestCase):
    def test_same_keys(self):
        self.assertEqual(set(RU) - set(EN), set())
        self.assertEqual(set(EN) - set(RU), set())

    def test_placeholders_match(self):
        import string
        fmt = string.Formatter()
        for key in RU:
            ru = {f for _, f, _, _ in fmt.parse(RU[key]) if f}
            en = {f for _, f, _, _ in fmt.parse(EN[key]) if f}
            self.assertEqual(ru, en, key)

    def test_switch(self):
        set_lang("en")
        self.assertEqual(t("btn.save"), "💾 Save")
        set_lang("ru")
        self.assertEqual(t("btn.save"), "💾 Сохранить")
        self.assertEqual(t("quota.left", time="01:00:00"), "осталось 01:00:00")


class UpdaterTest(unittest.TestCase):
    def test_versions(self):
        from src.updater import parse_version, is_newer
        self.assertEqual(parse_version("v3.2"), (3, 2))
        self.assertEqual(parse_version("3.2.0"), (3, 2))
        self.assertEqual(parse_version("3.0 VER WORK"), (3,))
        self.assertTrue(is_newer("v3.2", "3.1"))
        self.assertTrue(is_newer("v3.10", "3.9"))
        self.assertFalse(is_newer("v3.2", "3.2"))
        self.assertFalse(is_newer("v3.1.9", "3.2"))
        self.assertFalse(is_newer("nightly", "3.2"))


class IpcTest(unittest.TestCase):
    def test_argv(self):
        from src.ipc import parse_argv
        self.assertEqual(parse_argv(["exe", "claudepulse:pause2h"]), "pause2h")
        self.assertEqual(parse_argv(["exe", "claudepulse://pause_today/"]), "pause_today")
        self.assertEqual(parse_argv(["exe", "claudepulse:rm -rf"]), "open")
        self.assertIsNone(parse_argv(["exe"]))

    def test_roundtrip(self):
        from src import ipc
        ipc.take()
        ipc.send("pause2h")
        ipc.send("bogus")
        ipc.send("open")
        self.assertEqual(ipc.take(), ["pause2h", "open"])
        self.assertEqual(ipc.take(), [])


class DeferTest(unittest.TestCase):
    """Пинг по расписанию в открытое окно не уходит, а переезжает на минуту после сброса."""

    def make(self, reset_in_min=None, skip=True):
        from src.scheduler import SchedulerManager
        from src.config import DEFAULT_CONFIG
        sch = SchedulerManager()
        cfg = dict(DEFAULT_CONFIG, master_enabled=True, mode="fixed", times=["05:00"], skip_if_open=skip)
        sch.set_config(cfg)
        now = datetime.now().astimezone()
        if reset_in_min is not None:
            sch.usage.snapshot = {"session_pct": 40, "session_reset": now + timedelta(minutes=reset_in_min),
                                  "weekly_pct": 10, "weekly_reset": None, "fable_pct": None, "tips": []}
        self.ran = []
        sch._execute_job = lambda: self.ran.append(True)
        return sch, now

    def test_open_window_defers(self):
        sch, now = self.make(reset_in_min=30)
        sch._job()
        self.assertEqual(self.ran, [])
        self.assertAlmostEqual(sch.deferred_at, (now + timedelta(minutes=31)).timestamp(), delta=2)
        info = sch.next_ping_info()
        self.assertTrue(info["deferred"])

    def test_closed_window_pings(self):
        sch, _ = self.make(reset_in_min=None)
        sch._job()
        self.assertEqual(self.ran, [True])
        self.assertIsNone(sch.deferred_at)

    def test_setting_off_pings_anyway(self):
        sch, _ = self.make(reset_in_min=30, skip=False)
        sch._job()
        self.assertEqual(self.ran, [True])

    def test_deferred_run_clears_state(self):
        sch, _ = self.make(reset_in_min=None)
        sch._set_state("deferred_at", 1.0)
        sch._job("deferred")
        self.assertIsNone(sch.deferred_at)
        self.assertEqual(self.ran, [True])

    def test_pause_today(self):
        sch, _ = self.make()
        sch.pause_today()
        self.assertEqual(sch.next_ping_info()["state"], "paused")
        self.assertEqual(datetime.fromtimestamp(sch.paused_until).hour, 0)
        sch._job()
        self.assertEqual(self.ran, [])
        sch.resume()
        self.assertEqual(sch.next_ping_info()["state"], "scheduled")


class SessionsTest(unittest.TestCase):
    def write(self, folder, sid, entries):
        from pathlib import Path
        d = Path(folder) / "C--proj"
        d.mkdir(parents=True, exist_ok=True)
        import json as _json
        (d / f"{sid}.jsonl").write_text("\n".join(_json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")

    def test_list_and_filter(self):
        from pathlib import Path
        from src.sessions import list_sessions
        root = tempfile.mkdtemp()
        sid = "11111111-2222-3333-4444-555555555555"
        self.write(root, sid, [
            {"type": "user", "cwd": r"C:\work\proj", "message": {"content": "<command-name>/clear</command-name>"}},
            {"type": "user", "cwd": r"C:\work\proj", "message": {"content": [{"type": "text", "text": "почини тесты"}]}},
            {"type": "ai-title", "aiTitle": "Починка тестов"},
            {"type": "user", "cwd": r"C:\work\proj", "message": {"content": "и собери релиз"}},
        ])
        self.write(root, "99999999-2222-3333-4444-555555555555", [
            {"type": "user", "cwd": r"C:\tmp", "message": {"content": "/usage"}},
        ])
        items = list_sessions(projects_dir=Path(root))
        self.assertEqual(len(items), 1)          # служебная сессия /usage отфильтрована
        s = items[0]
        self.assertEqual(s["id"], sid)
        self.assertEqual(s["title"], "Починка тестов")
        self.assertEqual(s["last_prompt"], "и собери релиз")
        self.assertEqual(s["project"], "proj")


class ClaudeResultTest(unittest.TestCase):
    def test_json_success(self):
        from src.claude_cli import parse_result
        r = parse_result('{"type":"result","subtype":"success","is_error":false,"result":"Готово","num_turns":3}', "", 0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["text"], "Готово")
        self.assertFalse(r["limit_hit"])

    def test_limit(self):
        from src.claude_cli import parse_result
        r = parse_result('{"type":"result","subtype":"success","is_error":true,"result":"You\'ve hit your limit · resets 4am"}', "", 1)
        self.assertFalse(r["ok"])
        self.assertTrue(r["limit_hit"])
        self.assertEqual(r["reset_hint"], "4am")

    def test_plain_error(self):
        from src.claude_cli import parse_result
        r = parse_result("", "No conversation found with session ID", 1)
        self.assertFalse(r["ok"])
        self.assertFalse(r["limit_hit"])
        self.assertIn("No conversation", r["text"])


class TasksTest(unittest.TestCase):
    SESSION = {"id": "11111111-2222-3333-4444-555555555555", "cwd": r"C:\work\proj", "title": "t", "project": "proj"}

    def make(self, session_reset_min=None, weekly_pct=10):
        from src.scheduler import SchedulerManager
        from src.config import DEFAULT_CONFIG
        import src.tasks as tasks_mod
        tasks_mod.TASKS_FILE = __import__("pathlib").Path(tempfile.mkdtemp()) / "tasks.json"
        sch = SchedulerManager()
        sch.set_config(dict(DEFAULT_CONFIG))
        now = datetime.now().astimezone()
        sch.usage.snapshot = {
            "session_pct": 100 if session_reset_min else 0,
            "session_reset": now + timedelta(minutes=session_reset_min) if session_reset_min else None,
            "weekly_pct": weekly_pct, "weekly_reset": now + timedelta(days=2), "fable_pct": None, "tips": []}
        sch.tasks.tasks = []
        return sch.tasks, now

    def test_due_after_session_reset(self):
        tm, now = self.make(session_reset_min=90)
        task = tm.create(self.SESSION, "продолжи", "reset", "", "auto")
        self.assertAlmostEqual(task["due_at"], (now + timedelta(minutes=91)).timestamp(), delta=2)

    def test_due_now_when_limit_free(self):
        tm, _ = self.make(session_reset_min=None)
        task = tm.create(self.SESSION, "продолжи", "reset", "", "auto")
        self.assertLess(task["due_at"] - time.time(), 10)

    def test_weekly_exhausted_waits_for_week(self):
        tm, now = self.make(session_reset_min=30, weekly_pct=100)
        task = tm.create(self.SESSION, "продолжи", "reset", "", "auto")
        self.assertAlmostEqual(task["due_at"], (now + timedelta(days=2, minutes=1)).timestamp(), delta=2)

    def test_validation(self):
        tm, _ = self.make()
        with self.assertRaises(ValueError):
            tm.create(dict(self.SESSION, id="../../etc"), "x", "reset", "", "auto")
        with self.assertRaises(ValueError):
            tm.create(self.SESSION, "   ", "reset", "", "auto")
        with self.assertRaises(ValueError):
            tm.create(self.SESSION, "x", "time", "25:99", "auto")

    def test_run_limit_then_retry_once(self):
        import src.tasks as tasks_mod
        tm, _ = self.make()
        calls = []
        def fake(sid, prompt, cwd, mode, timeout):
            calls.append(mode)
            return {"ok": False, "text": "usage limit reached", "limit_hit": True, "reset_hint": None}
        tasks_mod.run_resume = fake
        task = tm.create(self.SESSION, "продолжи", "reset", "", "edits")
        task["due_at"] = 0
        tm.tick()
        for _ in range(50):
            if tm.running() is None:
                break
            time.sleep(0.05)
        self.assertEqual(calls, ["acceptEdits"])
        self.assertEqual(task["status"], "scheduled")     # перенесена, а не провалена
        self.assertGreater(task["due_at"], time.time() + 60)
        task["due_at"] = 0
        tm.tick()
        for _ in range(50):
            if tm.running() is None:
                break
            time.sleep(0.05)
        self.assertEqual(task["status"], "failed")        # второй раз — уже ошибка

    def test_run_success(self):
        import src.tasks as tasks_mod
        tm, _ = self.make()
        tasks_mod.run_resume = lambda *a: {"ok": True, "text": "Сделано", "limit_hit": False}
        task = tm.create(self.SESSION, "продолжи", "time", "00:00", "auto")
        tm.run_now(task["id"])
        tm.tick()
        for _ in range(50):
            if tm.running() is None:
                break
            time.sleep(0.05)
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["result"], "Сделано")


class ProcEnvTest(unittest.TestCase):
    """Чужая сессия Claude Code не должна утекать в наши вызовы claude."""

    def test_outside_session_untouched(self):
        from src.procenv import clean_env
        env = {"PATH": "x", "CLAUDE_CODE_GIT_BASH_PATH": "y", "ANTHROPIC_BASE_URL": "http://proxy"}
        self.assertEqual(clean_env(env, persistent=set()), env)

    def test_inside_session_stripped(self):
        from src.procenv import clean_env
        env = {"PATH": "x", "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s", "CLAUDE_CODE_MESSAGING_SOCKET": "p",
               "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH": "1", "ANTHROPIC_BASE_URL": "http://localhost:1",
               "CLAUDE_CODE_GIT_BASH_PATH": "C:/git/bash.exe", "ANTHROPIC_API_KEY": "k",
               "CLAUDE_EFFORT": "high", "CLAUDEPULSE_HOME": "D:/p"}
        out = clean_env(env, persistent={"CLAUDE_CODE_GIT_BASH_PATH"})
        self.assertEqual(out, {"PATH": "x", "CLAUDE_CODE_GIT_BASH_PATH": "C:/git/bash.exe", "ANTHROPIC_API_KEY": "k",
                               "CLAUDEPULSE_HOME": "D:/p"})


class UsageMonitorTest(unittest.TestCase):
    def make(self, cfg=None):
        from src.usage_monitor import UsageMonitor
        self.cfg = dict(cfg or {"alerts_enabled": True, "alert_levels": [80, 95]})
        m = UsageMonitor(lambda: self.cfg)
        self.sent, self.logs, self.saves = [], [], []
        m.notify = lambda title, body: self.sent.append(title)
        m.log = lambda msg, tag="normal": self.logs.append(msg)
        m.save = lambda: self.saves.append(1)
        return m

    def snap(self, pct, reset_text):
        from src.claude_parser import parse_usage
        return parse_usage(f"Current session: 10% used\nCurrent week (all models): {pct}% used · resets {reset_text}")

    def test_alert_not_repeated_for_same_window(self):
        m = self.make()
        future = datetime.now() + timedelta(days=3)
        mon = future.strftime("%b")
        m.snapshot = self.snap(81, f"{mon} {future.day}, 7:59am")
        m._check_alerts()
        m.snapshot = self.snap(81, f"{mon} {future.day}, 8am")   # то же окно, записанное иначе
        m._check_alerts()
        self.assertEqual(len(self.sent), 1)
        # Перезапуск программы: память предупреждений лежит в конфиге
        m2 = self.make(self.cfg)
        m2.snapshot = self.snap(81, f"{mon} {future.day}, 8am")
        m2._check_alerts()
        self.assertEqual(self.sent, [])
        # Следующий порог в том же окне — новое предупреждение
        m2.snapshot = self.snap(96, f"{mon} {future.day}, 8am")
        m2._check_alerts()
        self.assertEqual(len(self.sent), 1)

    def test_failure_logged_once_then_recovery(self):
        import src.usage_monitor as um
        m = self.make()
        outputs = iter(["Error: auth refresh failed", "Error: auth refresh failed",
                        "Current session: 5% used\nCurrent week (all models): 1% used"])
        um.run_cli = lambda cmd, timeout: next(outputs)
        m.account.get = lambda force=False: {"logged_in": True, "subscription": "max", "email": ""}
        m._fetch(); m._fetch()
        self.assertEqual(len(self.logs), 1)
        self.assertIn("auth refresh failed", self.logs[0])      # в журнале видно, что ответил claude
        self.assertEqual(m.ok_at, 0.0)
        m._fetch()
        self.assertEqual(len(self.logs), 2)                      # «лимиты снова обновляются»
        self.assertGreater(m.ok_at, 0)
        self.assertEqual(m.last_error, "")


if __name__ == "__main__":
    unittest.main()
