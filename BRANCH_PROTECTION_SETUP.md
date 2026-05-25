# Branch Protection Setup Guide

## Overview

This guide walks you through setting up branch protection rules for the `main` branch of the Samvid Trading Core repository. These rules ensure code quality, security, and stability.

## Prerequisites

- Admin access to the repository
- GitHub account with appropriate permissions

## Step-by-Step Setup Instructions

### Step 1: Navigate to Branch Protection Settings

1. Go to your repository: [https://github.com/AshishTalpada/samvid-trading-core](https://github.com/AshishTalpada/samvid-trading-core)
2. Click **Settings** (top menu)
3. Click **Branches** (left sidebar)
4. Click **Add rule** button

### Step 2: Configure Branch Pattern

- **Branch name pattern**: `main`
- Click **Create**

### Step 3: Enable Pull Request Requirements

✅ **Check:** "Require a pull request before merging"
- **Number of required reviews before merging**: `1`
- ✅ **Check:** "Dismiss stale pull request approvals when new commits are pushed"
- ✅ **Check:** "Require review from code owners"
- ✅ **Check:** "Require approval of the most recent reviewable push"

### Step 4: Enable Status Checks

✅ **Check:** "Require status checks to pass before merging"
- ✅ **Check:** "Require branches to be up to date before merging"

**Add these required status checks:**
- `lint`
- `test`
- `security`
- `build`

### Step 5: Enable Restrictions

✅ **Check:** "Require conversation resolution before merging"
- ✅ **Check:** "Require signed commits"
- ✅ **Check:** "Require linear history" (optional but recommended)
- ✅ **Check:** "Dismiss stale pull request approvals when new commits are pushed"

### Step 6: Enforce Restrictions

✅ **Check:** "Allow force pushes"
- Select: **Do not allow force pushes**

✅ **Check:** "Allow deletions"
- Select: **Do not allow deletions**

### Step 7: Set Review Dismissal Permissions

- **Allows specified actors to dismiss pull request reviews:**
  - Leave unchecked (only admins can dismiss)

### Step 8: Save Rules

Click **Create** or **Save changes** button at the bottom

---

## Verification Checklist

After setup, verify these settings are enabled:

- [ ] Require a pull request before merging: **1 approval**
- [ ] Dismiss stale PR approvals when new commits pushed: **YES**
- [ ] Require review from code owners: **YES**
- [ ] Require branches to be up to date: **YES**
- [ ] Required status checks configured: **lint, test, security, build**
- [ ] Require conversation resolution: **YES**
- [ ] Require signed commits: **YES**
- [ ] Allow force pushes: **NO**
- [ ] Allow deletions: **NO**

---

## What This Protects Against

1. **Unreviewed Code**: All code must be reviewed before merging
2. **CI/CD Failures**: Tests and linting must pass
3. **Accidental Deletions**: Main branch cannot be deleted
4. **Force Pushes**: History cannot be rewritten
5. **Stale Reviews**: Reviews are dismissed if code changes
6. **Security Issues**: Security scans must pass
7. **Unsigned Commits**: All commits must be cryptographically signed

---

## How It Works in Practice

### For Contributors:

```
1. Create feature branch from main
   $ git checkout -b feature/my-feature

2. Make changes and commit
   $ git commit -m "feat: add new feature"

3. Push to GitHub
   $ git push origin feature/my-feature

4. Create Pull Request on GitHub
   - GitHub automatically runs CI/CD checks
   - Tests must pass
   - Linting must pass
   - Security scans must pass
   - Build must succeed

5. Request code review
   - At least 1 approval required
   - Code owners automatically notified (CODEOWNERS file)

6. Merge (when all checks pass and approved)
   - Only then can you merge to main
   - If new commits pushed, reviews are dismissed
   - Must be reviewed again
```

### For Administrators:

- Can bypass all checks if needed
- Can dismiss reviews
- Can force push (but shouldn't!)
- Can merge without approval (but shouldn't!)

---

## Testing the Protection

Once configured, test by:

1. Try to push directly to main (should be blocked)
   ```bash
   git push origin main
   # Error: This branch is protected from force pushes and deletions
   ```

2. Try to create PR with failing tests (should show as failing)
   - Tests must all pass before merge button appears

3. Try to merge without approval (should be blocked)
   - Merge button appears only after approval

4. Try to delete main branch (should be blocked)
   - Delete option unavailable

---

## Troubleshooting

### "I can't see the Branch Protection option"
- Ensure you have **Admin** access to the repository
- Go to Settings → Collaborators to verify your role

### "Status checks not showing up"
- Ensure CI/CD workflows are created and running
- Wait 5-10 minutes for GitHub Actions to initialize
- Check Actions tab to verify workflows exist

### "Can't merge even with approvals"
- Verify all status checks passed (check Actions tab)
- Verify branch is up to date with main
- Verify you have code owner approval (if required)

---

## Branch Protection Rules Configuration Summary

| Setting | Value | Purpose |
|---------|-------|---------|
| **Branch pattern** | `main` | Protects main branch only |
| **Pull request reviews** | 1 required | Ensures code review |
| **Code owner review** | Required | Ensures domain expert review |
| **Dismiss stale reviews** | Yes | Ensures fresh reviews on changes |
| **Up to date required** | Yes | Prevents merge conflicts |
| **Status checks** | lint, test, security, build | Ensures quality gates |
| **Conversation resolution** | Yes | Ensures all comments addressed |
| **Signed commits** | Yes | Ensures commit authenticity |
| **Force push** | Disabled | Prevents history rewriting |
| **Deletions** | Disabled | Prevents branch deletion |

---

## Additional Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#about-status-checks)
- [Code Owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub Actions](https://docs.github.com/en/actions)

---

**Last Updated**: 2026-05-25
**Repository**: AshishTalpada/samvid-trading-core
