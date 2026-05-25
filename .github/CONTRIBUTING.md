# Contributing to Samvid Trading Core

Thank you for your interest in contributing to Samvid Trading Core! To maintain code quality, reliability, and security for high-frequency trading, please follow these guidelines.

## Branch Protection & Development Flow

1. **No Direct Pushes to `main`**: All features, bug fixes, and modifications must be developed on separate branches and merged via Pull Requests (PRs).
2. **Branch Protection Rules**:
   - The `main` branch is protected.
   - Requires at least one approving review from a code owner (defined in [CODEOWNERS](file:///c:/Users/talpa/Desktop/System_Beta/TradingSystem/.github/CODEOWNERS)) before merge.
   - Requires all automated status checks to pass before merging.
3. **Commit Granularity**: Commit and push changes incrementally, isolating logical modifications to separate, clean commits.

## Automated Testing & CI

Before submitting a Pull Request, run the local test suites and linters:

### 1. Python Style and Linting
We use **Ruff** for linting. All checks must pass:
```bash
uv run ruff check src tests scripts tools
```

### 2. Run Test Suite
Validate that all tests pass:
```bash
uv run pytest tests/
```

### 3. Rust/Native Verification
Ensure native components compile and tests pass:
```bash
cargo test
make
```

## How to Open a Pull Request

1. Create a descriptive branch: `feature/your-feature-name` or `bugfix/issue-description`.
2. Push your branch and open a PR against `main`.
3. Provide a clear explanation of changes, testing performed, and any architectural implications in the PR description.
4. Ensure the GitHub Actions CI workflow runs successfully.
5. Request review from the code owners.
