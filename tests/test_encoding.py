"""Test Chinese character encoding."""
import json
import sys

# Test 1: Print encoding
print(f"System encoding: {sys.stdout.encoding}")
print(f"Default encoding: {sys.getdefaultencoding()}")

# Test 2: Direct Chinese output
print("\n=== Test 1: Direct Chinese output ===")
print("測試中文：LLM架構、LLM應用、RAG改良")

# Test 3: JSON encoding with ensure_ascii=False
print("\n=== Test 2: JSON with ensure_ascii=False ===")
data = {
    "topic": "LLM架構",
    "intro": "這是一篇關於大型語言模型的論文",
    "background": "傳統中文處理技術的發展",
}
json_str = json.dumps(data, ensure_ascii=False, indent=2)
print(json_str)

# Test 4: JSON encoding with ensure_ascii=True (should show escape sequences)
print("\n=== Test 3: JSON with ensure_ascii=True (bad) ===")
json_str_bad = json.dumps(data, ensure_ascii=True, indent=2)
print(json_str_bad)

# Test 5: Parse and re-display
print("\n=== Test 4: Parse and re-display ===")
parsed = json.loads(json_str)
print(f"Topic: {parsed['topic']}")
print(f"Intro: {parsed['intro']}")

# Test 6: Topic categories
print("\n=== Test 5: All topic categories ===")
topics = ["LLM架構", "LLM應用", "RAG改良", "RAG應用", "OCR", "LLM Router", "其他"]
for topic in topics:
    print(f"  • {topic}")

print("\n✅ Encoding test complete!")
