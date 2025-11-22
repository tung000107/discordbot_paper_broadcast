#!/usr/bin/env python3
"""Verify Discord Research Assistant setup."""
import sys
from pathlib import Path


def check_file(path: str, required: bool = True) -> bool:
    """Check if file exists."""
    exists = Path(path).exists()
    status = "✅" if exists else ("❌" if required else "⚠️")
    req_text = " (required)" if required else " (optional)"
    print(f"{status} {path}{req_text if required or not exists else ''}")
    return exists or not required


def check_directory(path: str) -> bool:
    """Check if directory exists."""
    exists = Path(path).is_dir()
    status = "✅" if exists else "❌"
    print(f"{status} {path}/")
    return exists


def main():
    """Run setup verification."""
    print("Discord Research Assistant - Setup Verification")
    print("=" * 50)

    all_good = True

    # Check core files
    print("\n📄 Core Files:")
    all_good &= check_file("README.md")
    all_good &= check_file("requirements.txt")
    all_good &= check_file("docker-compose.yml")
    all_good &= check_file("Dockerfile")
    all_good &= check_file(".env", required=False)
    all_good &= check_file(".env.example")

    # Check source structure
    print("\n📁 Source Structure:")
    all_good &= check_directory("src")
    all_good &= check_directory("src/bot")
    all_good &= check_directory("src/llm")
    all_good &= check_directory("src/retriever")
    all_good &= check_directory("src/exporter")
    all_good &= check_directory("src/config")

    # Check key modules
    print("\n🐍 Key Modules:")
    all_good &= check_file("src/bot/main.py")
    all_good &= check_file("src/bot/commands/summarize.py")
    all_good &= check_file("src/llm/client.py")
    all_good &= check_file("src/llm/pipeline.py")
    all_good &= check_file("src/retriever/arxiv.py")
    all_good &= check_file("src/config/settings.py")
    all_good &= check_file("src/config/cache.py")
    all_good &= check_file("src/exporter/pdf.py")

    # Check data directories
    print("\n📊 Data Directories:")
    all_good &= check_directory("data")
    all_good &= check_directory("data/cache")
    all_good &= check_directory("data/reports")

    # Check environment
    print("\n🔧 Environment:")
    env_exists = Path(".env").exists()
    if env_exists:
        print("✅ .env file exists")
        print("   → Please verify DISCORD_TOKEN and OPENAI_API_KEY are set")
    else:
        print("⚠️  .env file not found")
        print("   → Run: cp .env.example .env")
        print("   → Then edit .env with your credentials")

    # Summary
    print("\n" + "=" * 50)
    if all_good and env_exists:
        print("✅ Setup verification passed!")
        print("\nNext steps:")
        print("  1. Configure .env with your API keys")
        print("  2. Run: docker-compose up -d")
        print("  3. Or use: ./run.sh")
        return 0
    else:
        print("⚠️  Some issues detected. Please review above.")
        if not env_exists:
            print("\nMissing .env file - this is required to run the bot.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
