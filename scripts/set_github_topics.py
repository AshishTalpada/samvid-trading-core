"""
Set GitHub repository topics for SEO discoverability.

Usage:
    pip install PyGithub
    export GITHUB_TOKEN=ghp_your_token_here
    python scripts/set_github_topics.py

Or set topics manually at: https://github.com/AshishTalpada/samvid-trading-core
Go to repo Settings > General > Topics and paste these topics one by one.
"""

# These are the optimal GitHub topics for maximum discoverability.
# GitHub allows up to 20 topics per repository.
TOPICS = [
    "algorithmic-trading",
    "trading-bot",
    "automated-trading",
    "interactive-brokers",
    "metatrader5",
    "quantitative-finance",
    "python-trading",
    "ai-agents",
    "multi-agent-system",
    "fastapi",
    "rust",
    "risk-management",
    "market-data",
    "real-time-trading",
    "stock-trading",
    "forex-trading",
    "questdb",
    "machine-learning",
    "trading-system",
    "open-source-finance",
]

REPO = "AshishTalpada/samvid-trading-core"


def main():
    import os

    try:
        from github import Github
    except ImportError:
        print("PyGithub not installed. Install with: pip install PyGithub")
        print(f"\nManual alternative: Go to https://github.com/{REPO}")
        print("Click the gear icon next to 'About' and add these topics:\n")
        for t in TOPICS:
            print(f"  {t}")
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN environment variable first.")
        print(f"\nManual alternative: Go to https://github.com/{REPO}")
        print("Click the gear icon next to 'About' and add these topics:\n")
        for t in TOPICS:
            print(f"  {t}")
        return

    g = Github(token)
    repo = g.get_repo(REPO)
    repo.replace_topics(TOPICS)
    print(f"Successfully set {len(TOPICS)} topics on {REPO}")
    print("Topics:", ", ".join(TOPICS))


if __name__ == "__main__":
    main()
