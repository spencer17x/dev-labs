"""Validate bot target environment without starting monitor loop."""

import argparse

from bot_app import load_runtime_config, validate_runtime_config


def parse_args():
    parser = argparse.ArgumentParser(description="Check bot target environment")
    parser.add_argument(
        "target",
        choices=["bsc", "sol", "base", "eth", "multi"],
        help="Bot target to validate",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = load_runtime_config(args.target)
    validate_runtime_config(cfg)
    print(
        "config ok | "
        f"target={args.target} | chain={cfg.chain} | data_dir={cfg.data_dir} | "
        f"check_interval={cfg.check_interval} | cooldown={cfg.notify_cooldown_hours}h | "
        f"confirmations={cfg.multiplier_confirmations}"
    )
