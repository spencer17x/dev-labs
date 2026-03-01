"""Convenient launcher for local run and PM2-managed bot control."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


CHAINS = {"bsc", "sol", "base"}
CONFIG_TARGETS = CHAINS | {"multi"}
ACTIONS = {"run", "start", "stop", "logs", "restart"}


def _pm2_name(chain: str) -> str:
    return f"trending-alert-{chain}"


def _ensure_pm2():
    if not shutil.which("pm2"):
        raise RuntimeError("pm2 not found, install pm2 first")


def _run_single(target: str, common_config: str, dry_run: bool):
    root = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        "main.py",
        "--common-config",
        common_config,
        "--bot-config",
        f"configs/bots/{target}.json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True, cwd=root)


def _start_target(target: str, common_config: str, dry_run: bool):
    root = Path(__file__).resolve().parent
    _ensure_pm2()
    cmd = [
        "pm2",
        "start",
        "run.py",
        "--name",
        _pm2_name(target),
        "--interpreter",
        "python3",
        "--",
        "run",
        target,
        "--common-config",
        common_config,
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True, cwd=root)


def _run_all():
    root = Path(__file__).resolve().parent
    _ensure_pm2()
    subprocess.run(["pm2", "start", "ecosystem.all.config.js"], check=True, cwd=root)


def _stop_target(target: str):
    root = Path(__file__).resolve().parent
    _ensure_pm2()

    if target == "all":
        subprocess.run(["pm2", "stop", "ecosystem.all.config.js"], check=True, cwd=root)
        return

    subprocess.run(["pm2", "stop", _pm2_name(target)], check=True, cwd=root)


def _logs_target(target: str):
    root = Path(__file__).resolve().parent
    _ensure_pm2()

    if target == "all":
        subprocess.run(["pm2", "logs"], check=True, cwd=root)
        return

    subprocess.run(["pm2", "logs", _pm2_name(target)], check=True, cwd=root)


def _restart_target(target: str):
    root = Path(__file__).resolve().parent
    _ensure_pm2()

    if target == "all":
        subprocess.run(["pm2", "restart", "ecosystem.all.config.js"], check=True, cwd=root)
        return

    subprocess.run(["pm2", "restart", _pm2_name(target)], check=True, cwd=root)


def parse_args():
    parser = argparse.ArgumentParser(description="Trending alert bot launcher")
    parser.add_argument(
        "action_or_target",
        choices=["run", "start", "stop", "logs", "restart", "bsc", "sol", "base", "multi", "all"],
        help="Action or target config",
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=["bsc", "sol", "base", "multi", "all"],
        help="Target config for action",
    )
    parser.add_argument(
        "--common-config",
        default="configs/common.json",
        help="Common config path for single-config startup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run one scan without sending messages (run/start single-config only)",
    )
    return parser.parse_args()


def _resolve_action(args) -> tuple[str, str]:
    if args.action_or_target in ACTIONS:
        action = args.action_or_target
        target = (args.target or "all").lower()
        return action, target

    if args.action_or_target == "all":
        # Backward-compatible shortcut: `python run.py all`
        return "start", "all"

    # Backward-compatible shortcut: `python run.py bsc`
    return "run", args.action_or_target.lower()


def main():
    args = parse_args()
    action, target = _resolve_action(args)

    if action == "run":
        if target in CONFIG_TARGETS:
            _run_single(target, args.common_config, args.dry_run)
            return
        raise RuntimeError(f"unsupported run target: {target}")

    if action == "start":
        if target in CONFIG_TARGETS:
            _start_target(target, args.common_config, args.dry_run)
            return
        if args.dry_run:
            raise RuntimeError("--dry-run is only supported for run/start single-config")
        _run_all()
        return

    if args.dry_run:
        raise RuntimeError("--dry-run is only supported for run/start action")

    if action == "stop":
        _stop_target(target)
        return

    if action == "logs":
        _logs_target(target)
        return

    if action == "restart":
        _restart_target(target)
        return

    raise RuntimeError(f"unsupported action: {action}")


if __name__ == "__main__":
    main()
