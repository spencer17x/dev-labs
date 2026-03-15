#!/usr/bin/env python3
"""Manual smoke runner for the XXYY client."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.xxyy_client import XXYYClient, build_xxyy_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='XXYY smoke runner')
    parser.add_argument('--chain', default='sol', help='chain id, default: sol')
    parser.add_argument('--mint', required=True, help='token mint / contract address')
    parser.add_argument(
        '--pair',
        default='',
        help='pair address for follow/kol endpoints, default resolves from pair/info',
    )
    parser.add_argument(
        '--mode',
        choices=['pair-info', 'stat-info', 'follow', 'kol', 'context', 'all'],
        default='context',
        help='which XXYY capability to test',
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = XXYYClient()
    pair_info_payload: Dict[str, Any] = {}
    stat_info_payload: Dict[str, Any] = {}
    follow_payload: Dict[str, Any] = {}
    kol_payload: Dict[str, Any] = {}

    needs_pair_info = args.mode in {'pair-info', 'follow', 'kol', 'context', 'all'}
    if needs_pair_info:
        pair_info_payload = client.fetch_pair_info(
            pair_address=args.mint,
            chain=args.chain,
            base_only=0,
        )
        if args.mode == 'pair-info':
            _print_json(pair_info_payload)
            return 0

    if args.mode in {'stat-info', 'context', 'all'}:
        stat_info_payload = client.fetch_holder_stat_info(
            mint=args.mint,
            chain=args.chain,
            only_total=0,
        )
        if args.mode == 'stat-info':
            _print_json(stat_info_payload)
            return 0

    pair_address = _resolve_pair_address(args.pair, pair_info_payload)

    if args.mode in {'follow', 'context', 'all'}:
        if not pair_address:
            raise SystemExit('pair address is required for follow mode')
        follow_payload = client.fetch_follow_holders(
            mint=args.mint,
            pair=pair_address,
            chain=args.chain,
        )
        if args.mode == 'follow':
            _print_json(follow_payload)
            return 0

    if args.mode in {'kol', 'context', 'all'}:
        if not pair_address:
            raise SystemExit('pair address is required for kol mode')
        kol_payload = client.fetch_kol_holders(
            mint=args.mint,
            pair=pair_address,
            chain=args.chain,
        )
        if args.mode == 'kol':
            _print_json(kol_payload)
            return 0

    if args.mode == 'all':
        _print_json(
            {
                'pair_info': pair_info_payload,
                'holder_stat_info': stat_info_payload,
                'follow_holders': follow_payload,
                'kol_holders': kol_payload,
            }
        )
        return 0

    _print_json(
        build_xxyy_context(
            {},
            stat_info=(
                stat_info_payload.get('data', {})
                if isinstance(stat_info_payload, dict)
                else {}
            ),
            pair_info=(
                pair_info_payload.get('data', {})
                if isinstance(pair_info_payload, dict)
                else {}
            ),
            kol_holders=kol_payload.get('data', []) if isinstance(kol_payload, dict) else [],
            follow_holders=follow_payload.get('data', []) if isinstance(follow_payload, dict) else [],
        )
    )
    return 0


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def _resolve_pair_address(explicit_pair: str, pair_info_payload: Dict[str, Any]) -> str:
    pair_address = explicit_pair.strip()
    if pair_address:
        return pair_address
    if not isinstance(pair_info_payload, dict):
        return ''
    return str(
        pair_info_payload.get('data', {})
        .get('launchPlatform', {})
        .get('launchedPair', '')
    ).strip()


if __name__ == '__main__':
    raise SystemExit(main())
