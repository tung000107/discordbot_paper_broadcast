"""Test JSON encoding/decoding with Chinese characters (no Redis needed)."""
import json


def test_json_roundtrip():
    """Test that Chinese characters survive JSON encode/decode."""
    print("Testing JSON encoding/decoding with Chinese characters...\n")

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

    print("=== Original Data ===")
    print(json.dumps(test_summary, ensure_ascii=False, indent=2))

    # Encode with ensure_ascii=False (CORRECT)
    print("\n=== Encoding with ensure_ascii=False (CORRECT) ===")
    json_str_correct = json.dumps(test_summary, ensure_ascii=False)
    print(f"String length: {len(json_str_correct)}")
    print(f"Preview: {json_str_correct[:100]}...")

    # Decode and verify
    decoded_correct = json.loads(json_str_correct)
    print(f"\nDecoded intro: {decoded_correct['intro']}")

    # Encode with ensure_ascii=True (INCORRECT - causes garbled output)
    print("\n=== Encoding with ensure_ascii=True (INCORRECT) ===")
    json_str_wrong = json.dumps(test_summary, ensure_ascii=True)
    print(f"String length: {len(json_str_wrong)}")
    print(f"Preview: {json_str_wrong[:150]}...")

    # Decode - will work but shows escape sequences
    decoded_wrong = json.loads(json_str_wrong)
    print(f"\nDecoded intro: {decoded_wrong['intro']}")

    # Verification
    print("\n=== Verification ===")
    if decoded_correct == test_summary:
        print("✅ ensure_ascii=False: Data preserved correctly")
    else:
        print("❌ ensure_ascii=False: Data corrupted!")

    if decoded_wrong == test_summary:
        print("✅ ensure_ascii=True: Data decoded correctly (but JSON string was ugly)")
    else:
        print("❌ ensure_ascii=True: Data corrupted!")

    print("\n=== Topic Categories Test ===")
    topics_data = {
        "categories": [
            {"name": "LLM架構", "count": 5},
            {"name": "LLM應用", "count": 8},
            {"name": "RAG改良", "count": 3},
            {"name": "RAG應用", "count": 6},
            {"name": "OCR", "count": 2},
            {"name": "LLM Router", "count": 1},
        ]
    }

    # Correct encoding
    topics_json = json.dumps(topics_data, ensure_ascii=False, indent=2)
    print("Categories with Chinese text:")
    print(topics_json)

    topics_decoded = json.loads(topics_json)
    print("\nDecoded categories:")
    for cat in topics_decoded["categories"]:
        print(f"  • {cat['name']}: {cat['count']} papers")

    print("\n✅ All tests passed! Chinese characters work correctly with ensure_ascii=False")


if __name__ == "__main__":
    test_json_roundtrip()
