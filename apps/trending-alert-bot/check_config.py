"""Validate bot runtime config without starting monitor loop."""

import argparse

from bot_app import load_runtime_config, validate_runtime_config


def parse_args():
    parser = argparse.ArgumentParser(description="Check bot config")
    parser.add_argument("--bot-config", required=True, help="Bot config JSON path")
    parser.add_argument("--common-config", default="", help="Common config JSON path")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = load_runtime_config(args.bot_config, args.common_config or None)
    validate_runtime_config(cfg)
    print(
        "config ok | "
        f"chain={cfg.chain} | data_dir={cfg.data_dir} | "
        f"check_interval={cfg.check_interval} | cooldown={cfg.notify_cooldown_hours}h | "
        f"confirmations={cfg.multiplier_confirmations}"
    )
