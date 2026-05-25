# Workflow Files Setup Instructions

This directory contains GitHub Actions workflow files that should be moved to `.github/workflows/`.

## Files

- `ci.yml` - Main CI/CD pipeline
- `security-scanning.yml` - Security scanning pipeline

## How to Move Them

### Option 1: Using GitHub UI

1. Go to your repository
2. Click "Add file" → "Create new file"
3. Enter path: `.github/workflows/ci.yml`
4. Copy content from `scripts/workflows/ci.yml`
5. Commit
6. Repeat for `security-scanning.yml`

### Option 2: Using Git CLI

```bash
git clone https://github.com/AshishTalpada/samvid-trading-core.git
cd samvid-trading-core

# Copy files to correct location
mkdir -p .github/workflows
cp scripts/workflows/ci.yml .github/workflows/
cp scripts/workflows/security-scanning.yml .github/workflows/

# Commit and push
git add .github/workflows/
git commit -m "ci: Add GitHub Actions workflows"
git push origin main
```

### Option 3: Manual Copy-Paste

1. Open `.github/workflows/ci.yml` in GitHub UI
2. Copy content from `scripts/workflows/ci.yml`
3. Paste and commit
4. Repeat for `security-scanning.yml`

## Verification

After moving files, verify:

1. Go to your repository's Actions tab
2. You should see "CI/CD Pipeline" and "Security Scanning" workflows
3. They should appear as available workflows

## Status Checks

Once workflows are in place and run, these status checks become available:
- `lint`
- `test`
- `security`
- `build`

These can then be configured as required status checks in branch protection rules.
