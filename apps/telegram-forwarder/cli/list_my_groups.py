#!/usr/bin/env python3
"""
获取当前登录用户所在的所有群组信息
包括群组名称、ID、类型、成员数等
"""
import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from dotenv import load_dotenv

# 加载环境变量（从父目录）
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 读取配置
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_PATH = os.getenv('TELEGRAM_SESSION_PATH', 'telegram_forwarder_session')

if not API_ID or not API_HASH:
    print("❌ 错误: 未找到 TELEGRAM_API_ID 或 TELEGRAM_API_HASH")
    print("请在 .env 文件中配置这些变量")
    sys.exit(1)


async def list_all_groups(client: TelegramClient, show_details: bool = False):
    """
    获取并显示所有群组信息

    Args:
        client: Telegram 客户端
        show_details: 是否显示详细信息
    """
    print("📡 正在获取群组列表...\n")

    # 获取所有对话
    dialogs = await client.get_dialogs()

    groups = []
    channels = []
    supergroups = []

    for dialog in dialogs:
        entity = dialog.entity

        # 区分不同类型
        if isinstance(entity, Channel):
            if entity.broadcast:
                # 频道
                channels.append(dialog)
            else:
                # 超级群组
                supergroups.append(dialog)
        elif isinstance(entity, Chat):
            # 普通群组
            groups.append(dialog)

    # 显示统计
    print("=" * 80)
    print("📊 统计信息")
    print("=" * 80)
    print(f"📢 频道数量: {len(channels)}")
    print(f"👥 超级群组数量: {len(supergroups)}")
    print(f"👫 普通群组数量: {len(groups)}")
    print(f"📝 总计: {len(channels) + len(supergroups) + len(groups)}")
    print()

    # 显示频道
    if channels:
        print("=" * 80)
        print("📢 频道列表")
        print("=" * 80)
        for i, dialog in enumerate(channels, 1):
            entity = dialog.entity
            print(f"\n{i}. {entity.title}")
            print(f"   🆔 ID: {entity.id}")
            if entity.username:
                print(f"   🔗 用户名: @{entity.username}")
                print(f"   🔗 链接: https://t.me/{entity.username}")
            else:
                print(f"   🔗 用户名: 私有频道")

            if show_details:
                if hasattr(entity, 'participants_count') and entity.participants_count:
                    print(f"   👤 订阅者: {entity.participants_count:,}")
                if hasattr(entity, 'verified') and entity.verified:
                    print(f"   ✅ 已认证")
                if hasattr(entity, 'scam') and entity.scam:
                    print(f"   ⚠️  标记为诈骗")

    # 显示超级群组
    if supergroups:
        print("\n" + "=" * 80)
        print("👥 超级群组列表")
        print("=" * 80)
        for i, dialog in enumerate(supergroups, 1):
            entity = dialog.entity
            print(f"\n{i}. {entity.title}")
            print(f"   🆔 ID: {entity.id}")
            if entity.username:
                print(f"   🔗 用户名: @{entity.username}")
                print(f"   🔗 链接: https://t.me/{entity.username}")
            else:
                print(f"   🔗 用户名: 私有群组")

            if show_details:
                if hasattr(entity, 'participants_count') and entity.participants_count:
                    print(f"   👤 成员数: {entity.participants_count:,}")
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    print(f"   📱 类型: 超级群组")

    # 显示普通群组
    if groups:
        print("\n" + "=" * 80)
        print("👫 普通群组列表")
        print("=" * 80)
        for i, dialog in enumerate(groups, 1):
            entity = dialog.entity
            print(f"\n{i}. {entity.title}")
            print(f"   🆔 ID: {entity.id}")

            if show_details:
                if hasattr(entity, 'participants_count') and entity.participants_count:
                    print(f"   👤 成员数: {entity.participants_count:,}")

    print("\n" + "=" * 80)


async def export_to_json(client: TelegramClient, output_file: str = "my_groups.json"):
    """
    导出群组信息到 JSON 文件

    Args:
        client: Telegram 客户端
        output_file: 输出文件路径
    """
    import json

    print("📡 正在获取群组列表...\n")

    dialogs = await client.get_dialogs()

    result = {
        "channels": [],
        "supergroups": [],
        "groups": []
    }

    for dialog in dialogs:
        entity = dialog.entity

        base_info = {
            "id": entity.id,
            "title": entity.title if hasattr(entity, 'title') else None,
        }

        if isinstance(entity, Channel):
            if hasattr(entity, 'username') and entity.username:
                base_info["username"] = entity.username
                base_info["link"] = f"https://t.me/{entity.username}"

            if hasattr(entity, 'participants_count') and entity.participants_count:
                base_info["participants_count"] = entity.participants_count

            if hasattr(entity, 'verified'):
                base_info["verified"] = entity.verified

            if entity.broadcast:
                result["channels"].append(base_info)
            else:
                base_info["megagroup"] = getattr(entity, 'megagroup', False)
                result["supergroups"].append(base_info)

        elif isinstance(entity, Chat):
            if hasattr(entity, 'participants_count') and entity.participants_count:
                base_info["participants_count"] = entity.participants_count
            result["groups"].append(base_info)

    # 保存到文件
    output_path = Path(__file__).parent.parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 群组信息已导出到: {output_path}")
    print(f"📊 统计:")
    print(f"   - 频道: {len(result['channels'])}")
    print(f"   - 超级群组: {len(result['supergroups'])}")
    print(f"   - 普通群组: {len(result['groups'])}")


async def main():
    """主函数"""
    print("🔍 Telegram 群组列表工具")
    print("-" * 80)

    # 创建客户端
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

    try:
        await client.start()
        print("✅ 已连接到 Telegram\n")

        # 询问显示模式
        print("请选择操作：")
        print("  1. 显示简要列表")
        print("  2. 显示详细列表")
        print("  3. 导出到 JSON 文件")
        print()

        choice = input("👉 请选择 (1/2/3) [默认: 1]: ").strip() or "1"
        print()

        if choice == "1":
            await list_all_groups(client, show_details=False)
        elif choice == "2":
            await list_all_groups(client, show_details=True)
        elif choice == "3":
            filename = input("👉 输入文件名 [默认: my_groups.json]: ").strip() or "my_groups.json"
            await export_to_json(client, filename)
        else:
            print("❌ 无效的选择")

    except KeyboardInterrupt:
        print("\n\n👋 用户中断，再见！")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
        sys.exit(0)
