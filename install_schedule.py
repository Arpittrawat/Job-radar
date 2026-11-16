"""Installs a macOS schedule: runs `run.py` every day at 09:00 and 21:00 (your Mac's local time).
If the Mac is asleep at that time, macOS runs it when the Mac wakes.
Usage:   python3 install_schedule.py            install / update
         python3 install_schedule.py --remove   uninstall
         python3 install_schedule.py --dry-run  show the schedule file without installing"""
import os, sys, plistlib, subprocess

LABEL = "com.jobradar.run"
HOURS = [9, 21]
HERE = os.path.dirname(os.path.abspath(__file__))
PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")

def build():
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, os.path.join(HERE, "run.py")],
        "WorkingDirectory": HERE,
        "StartCalendarInterval": [{"Hour": h, "Minute": 0} for h in HOURS],
        "StandardOutPath": os.path.join(HERE, "radar.log"),
        "StandardErrorPath": os.path.join(HERE, "radar.log"),
    }

def main():
    if "--remove" in sys.argv:
        subprocess.run(["launchctl", "unload", PLIST], check=False)
        if os.path.exists(PLIST): os.remove(PLIST)
        print("Schedule removed."); return
    if "--dry-run" in sys.argv:
        print(plistlib.dumps(build()).decode()); return
    if sys.platform != "darwin":
        print("This installer is for macOS only."); sys.exit(1)
    protected = [os.path.expanduser(p) for p in ("~/Downloads", "~/Desktop", "~/Documents")]
    if any(HERE.startswith(p + os.sep) for p in protected):
        print("STOP: this folder is inside Downloads, Desktop or Documents. macOS blocks scheduled jobs there.\\n"
              "Move the whole job-radar folder to your home folder (for example /Users/<you>/job-radar), then run this again from there.")
        sys.exit(1)
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    with open(PLIST, "wb") as f:
        plistlib.dump(build(), f)
    subprocess.run(["launchctl", "unload", PLIST], check=False, stderr=subprocess.DEVNULL)
    r = subprocess.run(["launchctl", "load", PLIST])
    if r.returncode:
        print("launchctl load failed. Send me this output."); sys.exit(1)
    print(f"Done. Job Radar will run every day at {' and '.join(f'{h:02d}:00' for h in HOURS)}.")
    print(f"Log file: {os.path.join(HERE, 'radar.log')}")

main()
