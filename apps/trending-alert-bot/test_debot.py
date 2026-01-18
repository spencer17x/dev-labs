"""测试 debot.ai 叙事 API"""

import json
from api import fetch_narrative


def test_bsc():
    """测试 BSC 链"""
    print("=" * 50)
    print("测试 BSC 链叙事 API")
    print("=" * 50)

    ca = "0x7fccd5c6085077dba0b6f6332cb4c8c518044444"
    print(f"合约地址: {ca}")

    try:
        result = fetch_narrative(ca, chain="bsc")
        print(f"请求成功！")
        print(f"code: {result.get('code')}")
        print(f"success: {result.get('success')}")

        data = result.get("data", {})
        history = data.get("history", {})

        if history:
            print(f"\n代币名称: {history.get('name')}")
            story = history.get("story", {})
            if story:
                print(f"叙事类型: {story.get('narrative_type')}")
                rating = story.get("rating", {})
                print(f"评分: {rating.get('score')} 星")
                print(f"评分理由: {rating.get('reason')[:100]}..." if rating.get('reason') else "")

                background = story.get("background", {})
                origin = background.get("origin", {})
                if origin.get("text"):
                    print(f"\n起源描述:\n{origin.get('text')[:200]}...")
        else:
            print("无叙事数据")

    except Exception as e:
        print(f"请求失败: {e}")


def test_sol():
    """测试 SOL 链"""
    print("\n" + "=" * 50)
    print("测试 SOL 链叙事 API")
    print("=" * 50)

    # 使用一个 SOL 代币地址进行测试
    ca = "So11111111111111111111111111111111111111112"  # Wrapped SOL
    print(f"合约地址: {ca}")

    try:
        result = fetch_narrative(ca, chain="sol")
        print(f"请求成功！")
        print(f"code: {result.get('code')}")
        print(f"success: {result.get('success')}")

        data = result.get("data", {})
        history = data.get("history", {})

        if history:
            print(f"\n代币名称: {history.get('name')}")
            story = history.get("story", {})
            if story:
                print(f"叙事类型: {story.get('narrative_type')}")
                rating = story.get("rating", {})
                print(f"评分: {rating.get('score')} 星")
        else:
            print("无叙事数据")

    except Exception as e:
        print(f"请求失败: {e}")


def test_raw_response():
    """获取完整原始响应"""
    print("\n" + "=" * 50)
    print("获取完整原始响应")
    print("=" * 50)

    ca = "0x7fccd5c6085077dba0b6f6332cb4c8c518044444"

    try:
        result = fetch_narrative(ca, chain="bsc")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"请求失败: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "raw":
            test_raw_response()
        elif sys.argv[1] == "sol":
            test_sol()
        elif sys.argv[1] == "bsc":
            test_bsc()
        else:
            # 自定义合约地址
            ca = sys.argv[1]
            chain = sys.argv[2] if len(sys.argv) > 2 else "bsc"
            print(f"测试合约: {ca} ({chain})")
            result = fetch_narrative(ca, chain=chain)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        test_bsc()
        test_sol()
