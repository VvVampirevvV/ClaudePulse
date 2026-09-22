import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def app_version() -> str:
    text = open(os.path.join(ROOT, "src", "config.py"), encoding="utf-8").read()
    return re.search(r'APP_VERSION = "([^"]+)"', text).group(1)


def write_version_file(path: str, version: str):
    """
    Сведения о файле (Свойства → Подробно): название, автор, версия.
    У exe без них SmartScreen и антивирусы подозрительнее.
    """
    nums = [int(x) for x in re.findall(r"\d+", version)][:4]
    nums += [0] * (4 - len(nums))
    ver_tuple = tuple(nums)
    ver_str = ".".join(str(n) for n in nums)
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={ver_tuple}, prodvers={ver_tuple}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'VvVampirevvV'),
      StringStruct('FileDescription', 'Claude Pulse - Claude Code limits and scheduled pings'),
      StringStruct('FileVersion', '{ver_str}'),
      StringStruct('InternalName', 'ClaudePulse'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'ClaudePulse.exe'),
      StringStruct('ProductName', 'Claude Pulse'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build():
    version = app_version()
    print(f"Building Claude Pulse {version}...")
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    version_file = os.path.join(ROOT, "build", "version_info.txt")
    write_version_file(version_file, version)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--noupx",                       # сжатие UPX — частая причина ложных срабатываний антивирусов
        "--version-file=build/version_info.txt",  # относительный путь: в .spec не попадёт имя пользователя
        "--icon=assets/icon.ico",
        "--name=ClaudePulse",
        "--add-data=assets;assets",
        "--collect-data=tzdata",         # часовые пояса для времени сброса из /usage
        "main.py",
    ]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)
    print("Build complete! Check the 'dist' folder.")


if __name__ == "__main__":
    build()
