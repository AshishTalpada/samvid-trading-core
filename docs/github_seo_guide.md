# GitHub SEO & Discoverability Guide

To ensure **Samvid Trading Core** is discoverable across GitHub search, Google indexing, and developer channels, follow this step-by-step checklist to configure the repository settings.

---

## 1. Optimize the "About" Section
The "About" section on the right side of the GitHub repository page is the most critical piece of metadata for search engine indexing.

1. Go to the home page of your repository on GitHub.
2. Click the gear icon (**⚙️**) next to **About** (right sidebar).
3. Update the fields as follows:
   - **Description**: `Consensus-driven multi-agent AI algorithmic trading system for Interactive Brokers (IBKR) & MetaTrader 5 (MT5) with 11 specialized voting agents, async pub/sub TCP bus, and institutional risk management.`
   - **Website**: Paste the link to your repository or your hosted dashboard (e.g., `https://github.com/AshishTalpada/samvid-trading-core`).
   - **Topics**: Add the topics one by one. You can run `python scripts/set_github_topics.py` (which requires a `GITHUB_TOKEN`), or manually copy-paste the topics below.

---

## 2. Set Repository Topics (Tags)
GitHub uses topics to group repositories and show them in topic-specific explorer pages. Add these exact tags to your repository:

`algorithmic-trading`, `trading-bot`, `automated-trading`, `interactive-brokers`, `metatrader5`, `quantitative-finance`, `python-trading`, `ai-agents`, `multi-agent-system`, `fastapi`, `rust`, `risk-management`, `market-data`, `real-time-trading`, `stock-trading`, `forex-trading`, `questdb`, `machine-learning`, `trading-system`, `open-source-finance`

---

## 3. Upload a Social Preview Image (Open Graph)
When you share your repository link on Twitter/X, LinkedIn, Reddit, or Discord, a social preview image makes the link stand out, dramatically increasing click-through rates.

1. Go to **Settings** (top tab of the repository).
2. Under the **General** section, scroll down to **Social preview**.
3. Click **Edit** > **Upload an image...**.
4. Select the generated image: **`docs/images/social_preview.png`** (or download it from the workspace).

---

## 4. Enable Discussions & Wikis
Interactive communities attract more traffic, which signals activity to search engines and ranks the repository higher.

1. In **Settings** > **General**, scroll down to the **Features** section.
2. Check the box for **Wikis** (for long-form documentation).
3. Check the box for **Discussions** (creates a community Q&A forum).

---

## 5. Enable GitHub Pages (Critical for Google Indexing)

GitHub Pages turns your `docs/` folder into a public website that Google can crawl independently of the GitHub repo page. This doubles your search real estate.

1. Go to **Settings** -> **Pages** (left sidebar).
2. Under **Build and deployment** -> **Source**, select **Deploy from a branch**.
3. Choose the `main` branch and `/docs` folder, then click **Save**.
4. Your site will be published at `https://ashishtalpada.github.io/samvid-trading-core/`.

### Files already prepared for you:
- **`docs/_config.yml`** — Jekyll config with SEO plugin, sitemap, and social preview image
- **`docs/index.md`** — A dedicated landing page with dense keyword coverage, architecture diagrams, and quick-start steps

Wait 5-10 minutes after enabling Pages, then verify the live site loads.

---

## 6. Add a Release

GitHub repositories with active releases get indexed with a dedicated "Releases" sub-link in Google Search results.

1. On the home page of your repository, click **Create a new release** (right sidebar).
2. Set the tag version (e.g., `v1.0.0`).
3. Set the release title (e.g., `v1.0.0 - Production-Ready Multi-Agent Algorithmic Trading Core`).
4. Click **Generate release notes** to automatically pull pull request descriptions.
5. Click **Publish release**.

---

## 7. Cross-Platform Package Metadata SEO

Search engines also index package manifests. The following files have already been optimized:

- **`pyproject.toml`** — Keywords and classifiers for PyPI
- **`Cargo.toml`** — Keywords, description, categories, and repository URL for crates.io
- **`frontend/package.json`** — Keywords, description, and repository URL for npm
- **`CITATION.cff`** — Academic indexing (Zenodo, Google Scholar); abstract and keywords optimized

Make sure the `repository` and `homepage` fields in all three files point exactly to `https://github.com/AshishTalpada/samvid-trading-core`.

---

## 8. Submit Your Site to Search Engines

After enabling GitHub Pages, tell Google and Bing to crawl it:

1. **Google Search Console**: https://search.google.com/search-console
   - Add property: `https://ashishtalpada.github.io/samvid-trading-core/`
   - Submit the sitemap: `https://ashishtalpada.github.io/samvid-trading-core/sitemap.xml`

2. **Bing Webmaster Tools**: https://www.bing.com/webmasters
   - Submit the same URL and sitemap.

3. **GitHub Profile SEO**: Paste the markdown from `docs/profile_showcase.md` into your personal GitHub profile README (`AshishTalpada/AshishTalpada`). This creates a backlink from your profile to the repo, which GitHub's internal search algorithm weights heavily.

---

## 9. Social Sharing Checklist

Before posting the repo on Reddit, LinkedIn, Twitter/X, or Discord:

- The **Social preview** image (`docs/images/social_preview.png`) is already uploaded.
- The **About** description is already optimized (see Step 1).
- Include these hashtags for maximum reach:
  `#AlgorithmicTrading` `#QuantitativeFinance` `#TradingBot` `#OpenSource` `#Python` `#Rust` `#AIAgents` `#InteractiveBrokers` `#MetaTrader5` `#FinTech`
