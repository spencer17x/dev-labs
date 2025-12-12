#!/usr/bin/env python3
"""
查询 Telegram 用户 ID 的工具脚本
支持通过用户名或手机号查询
"""
import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient
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


async def get_user_info(client: TelegramClient, identifier: str):
    """
    获取用户信息

    Args:
        client: Telegram 客户端
        identifier: 用户标识（用户名、手机号或 ID）
    """
    try:
        # 移除 @ 符号（如果有）
        if identifier.startswith('@'):
            identifier = identifier[1:]

        # 尝试获取用户实体
        user = await client.get_entity(identifier)

        print("\n" + "="*50)
        print("📋 用户信息")
        print("="*50)
        print(f"🆔 用户ID: {user.id}")
        print(f"👤 名称: {user.first_name or ''} {user.last_name or ''}")

        if user.username:
            print(f"🔗 用户名: @{user.username}")
        else:
            print(f"🔗 用户名: 无")

        if hasattr(user, 'phone') and user.phone:
            print(f"📱 手机号: +{user.phone}")

        if hasattr(user, 'bot') and user.bot:
            print(f"🤖 类型: Bot")
        else:
            print(f"👥 类型: 用户")

        if hasattr(user, 'verified') and user.verified:
            print(f"✅ 认证: 已认证")

        if hasattr(user, 'premium') and user.premium:
            print(f"⭐ 会员: Premium")

        print("="*50)

        return user

    except ValueError as e:
        print(f"\n❌ 错误: 找不到用户 '{identifier}'")
        print(f"提示: 请确保用户名正确，或者该用户已经与你有过互动")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")

    return None


async def main():
    """主函数"""
    print("🔍 Telegram 用户 ID 查询工具")
    print("-" * 50)

    # 创建客户端
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

    try:
        await client.start()
        print("✅ 已连接到 Telegram\n")

        # 交互式查询
        while True:
            print("\n请输入要查询的用户信息：")
            print("  - 用户名（如: username 或 @username）")
            print("  - 手机号（如: +1234567890）")
            print("  - 用户ID（如: 123456789）")
            print("  - 输入 'quit' 或 'exit' 退出")
            print()

            identifier = input("👉 请输入: ").strip()

            if not identifier:
                print("⚠️  输入不能为空")
                continue

            if identifier.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break

            # 查询用户信息
            await get_user_info(client, identifier)

    except KeyboardInterrupt:
        print("\n\n👋 用户中断，再见！")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
        sys.exit(0)
