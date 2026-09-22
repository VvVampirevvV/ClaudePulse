import os
import subprocess

def build():
    print("Building Claude Pulse...")
    # --onefile to create a single executable
    # --windowed to hide the console window
    cmd = [
        "python",
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon=assets/icon.ico",
        "--name=ClaudePulse",
        "--add-data=assets;assets",
        "--collect-data=tzdata",  # часовые пояса для времени сброса из /usage
        "main.py"
    ]
    
    # Run the command
    subprocess.run(" ".join(cmd), shell=True)
    print("Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
