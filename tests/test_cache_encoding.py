"""Test Chinese character encoding through Redis cache."""
import asyncio
from src.config.cache import RedisCache
from src.config.settings import settings


async def test_cache_encoding():
    """Test that Chinese characters survive Redis round-trip."""
    print("Testing Chinese character encoding through Redis cache...")

    # Initialize cache
    cache = RedisCache(redis_url=settings.redis_url)
    await cache.connect()

    # Test data with Chinese characters
    test_summary = {
        "intro": "這篇論文提出了一種新的大型語言模型架構，能夠更有效地處理繁體中文文本。",
        "background": "傳統的語言模型在處理中文時常常遇到分詞和語義理解的挑戰。",
        "method": "我們採用了基於Transformer的編碼器，並加入了專門的中文語義嵌入層。",
        "conclusion": "實驗結果顯示，我們的模型在多項中文NLP任務上取得了最先進的性能。",
        "bullet_points": [
            "提出新的中文語言模型架構",
            "改進了中文分詞準確度",
            "在多個基準測試中超越現有方法"
        ],
        "limitations": "模型訓練需要大量的繁體中文語料，且計算成本較高。"
    }

    arxiv_id = "2401.12345"
    model = "gpt-4o-mini"

    print("\n=== Original Summary ===")
    for key, value in test_summary.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value[:80]}{'...' if len(value) > 80 else ''}")

    # Save to cache
    print("\n=== Saving to Redis ===")
    await cache.set_summary(arxiv_id, model, test_summary)
    print("✓ Summary saved to cache")

    # Retrieve from cache
    print("\n=== Retrieving from Redis ===")
    retrieved = await cache.get_summary(arxiv_id, model)

    if retrieved:
        print("✓ Summary retrieved from cache")
        print("\n=== Retrieved Summary ===")
        for key, value in retrieved.items():
            if isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value[:80]}{'...' if len(value) > 80 else ''}")

        # Verify content matches
        print("\n=== Verification ===")
        if retrieved == test_summary:
            print("✅ SUCCESS: Retrieved data matches original exactly!")
        else:
            print("❌ FAILURE: Data mismatch!")
            print("\nDifferences:")
            for key in test_summary.keys():
                if test_summary[key] != retrieved.get(key):
                    print(f"  {key}:")
                    print(f"    Original:  {test_summary[key]}")
                    print(f"    Retrieved: {retrieved.get(key)}")
    else:
        print("❌ FAILURE: Could not retrieve from cache")

    # Cleanup
    await cache.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_cache_encoding())
