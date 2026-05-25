# Samvid Trading Core - Governance Framework

## Overview

This document establishes the governance structure, decision-making processes, and operational guidelines for the Samvid Trading Core project.

## Repository Protection Rules

### Branch Protection: `main`
- **Require pull request reviews before merging**
  - Required number of approvals: 1
  - Dismiss stale PR approvals when new commits are pushed: Yes
  
- **Require status checks to pass before merging**
  - CI/CD pipeline must pass
  - Required checks:
    - Lint
    - Unit Tests
    - Integration Tests
    - Security Scanning
    - Build

- **Require branches to be up to date before merging**
  - Yes

- **Require code review from code owners**
  - Yes (enforced via CODEOWNERS file)

- **Require conversation resolution before merging**
  - Yes

- **Require signed commits**
  - Recommended (not enforced, but encouraged)

### Branch Protection: `develop`
- Same rules as `main` with 1 required approval
- Staging branch for validated features

### Default Branch
- Primary: `main`
- All PRs target `main` by default

## Release Management

### Version Numbering
Follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes or significant architectural updates
- **MINOR**: New features, agent enhancements, algorithm improvements
- **PATCH**: Bug fixes, performance improvements, documentation

### Release Process

1. **Feature Development**
   - Create feature branch from `develop`
   - Submit PR with full test coverage
   - Code review and approval required

2. **Release Staging**
   - Merge features to `develop`
   - Run full test suite and performance benchmarks
   - Create release notes draft

3. **Release Candidate**
   - Tag `develop` as `vX.Y.Z-rc1`
   - Deploy to staging environment
   - Conduct UAT and performance testing
   - Fix critical issues found

4. **Release**
   - Merge `develop` to `main`
   - Tag with `vX.Y.Z`
   - Build and publish artifacts
   - Deploy to production
   - Update documentation

5. **Post-Release**
   - Monitor system health
   - Create hotfix branch if critical issues found
   - Backport critical fixes to `main`

## Code Review Policy

### Mandatory Review Criteria

Before a PR can be merged:

1. **Automated Checks**
   - All CI/CD pipelines pass
   - Code coverage maintained or improved
   - No security vulnerabilities detected

2. **Code Quality**
   - Follows code style guidelines
   - Type hints present for Python code
   - Documentation updated

3. **Functional Testing**
   - Unit tests added for new code
   - Integration tests pass
   - No regression in existing functionality

4. **Trading-Specific Reviews**
   - Risk calculations validated
   - Compliance implications assessed
   - Performance benchmarks acceptable

### Reviewer Responsibilities

- **Maintainers**: Full code review authority
- **Subject Matter Experts**: Specialized domain reviews
- **CODEOWNERS**: Automatic notification and required approval

### Review Timeline
- Response within 24 hours expected
- Resolution of comments within 48 hours
- Blocking issues resolved before merge

## Access Control

### Team Structure

| Role | Permissions | Responsibilities |
|------|-------------|------------------|
| **Owner** | Admin | Overall governance, release decisions, security policy |
| **Maintainer** | Write | Code review, PR merging, issue triage |
| **Contributor** | Pull | Code submissions, issue reporting, documentation |
| **Viewer** | Read | Documentation, code review |

### Current Structure
- **Owner**: @AshishTalpada
- **Maintainers**: (To be assigned)
- **Contributors**: Community members with merged PRs

### Onboarding New Maintainers
1. Demonstrated 5+ meaningful contributions
2. Deep understanding of codebase
3. Agreement to governance rules
4. Owner approval

## Security Policy

### Vulnerability Reporting
- **Do not** open public issues for security vulnerabilities
- Email security concerns to: (to be configured)
- Allow 48 hours for acknowledgment
- Coordinate responsible disclosure

### Security Updates
- Security fixes prioritized over features
- Fast-track review process for security PRs
- Security advisories published with releases

### Access Management
- Credentials managed via GitHub Secrets
- API keys rotated quarterly
- Access revoked immediately upon contributor departure

## Contribution Guidelines

### Types of Contributions Welcomed

1. **Code Contributions**
   - Bug fixes
   - Performance improvements
   - New features
   - Test enhancements

2. **Documentation**
   - Architecture documentation
   - API documentation
   - Tutorial content
   - Example code

3. **Issue Triage**
   - Bug reporting
   - Feature requests
   - Discussion participation

### Contribution Size Guidelines

- **Small** (<100 LOC): 1 review, faster merge
- **Medium** (100-500 LOC): 1 review, standard timeline
- **Large** (>500 LOC): 2 reviews, extended timeline
- **Critical Trading Logic**: Senior maintainer review required

## Issue Management

### Issue Triage

#### Priority Levels
- **Critical**: Production outage, security vulnerability
- **High**: Broken functionality, major bug
- **Medium**: Feature request, moderate bug
- **Low**: Minor issues, documentation

#### Severity for Trading System
- **Sev-0**: Execution failures, risk system failure → Immediate action
- **Sev-1**: Consensus failures, data corruption → 1-hour response
- **Sev-2**: Performance degradation → 24-hour response
- **Sev-3**: Minor issues → Standard process

### Stale Issue Management
- Issues inactive for 30 days: "awaiting response" label
- Issues inactive for 60 days: Closed if no activity
- Reopenable upon new information

## Decision-Making Process

### Minor Decisions
- Single maintainer authority
- Examples: Bug fixes, refactoring, minor feature enhancements

### Major Decisions
- Require 2+ maintainer consensus
- Examples: Architecture changes, new consensus algorithms, breaking changes

### Strategic Decisions
- Require owner approval
- Examples: Project direction, institutional partnerships, major releases

## Conflict Resolution

### Code Review Disagreements
1. **Technical Discussion**: 24-hour discussion period
2. **Escalation**: Involve additional maintainers
3. **Owner Decision**: If consensus not reached, owner decides

### Conduct Issues
1. **Initial Discussion**: Private message to address concern
2. **Escalation**: Owner involvement if unresolved
3. **Action**: Warning, temporary restriction, or removal as appropriate

## Metrics & Reporting

### Key Metrics
- PR merge time (target: <48 hours for non-blocking)
- Code review cycle time
- Test coverage percentage (target: >80%)
- Security vulnerability response time
- Release frequency

### Regular Reports
- Weekly: Merged PRs, open issues, CI/CD status
- Monthly: Contributor activity, performance trends
- Quarterly: Release schedule, strategic roadmap

## Communication Channels

- **GitHub Issues**: Bug reports, features, discussions
- **Pull Requests**: Code review, feedback
- **GitHub Discussions**: General questions, brainstorming
- **Email**: Security issues, private matters

## Policy Changes

### Governance Updates
1. Propose changes via issue or discussion
2. Community feedback period: 7 days
3. Owner approval required
4. Update this document
5. Announce in release notes

## Appendix

### Useful Links
- [Contributing Guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [GitHub Settings](https://github.com/AshishTalpada/samvid-trading-core/settings)

### Template Review Checklist
```
- [ ] Code follows style guidelines
- [ ] All tests passing
- [ ] No new warnings
- [ ] Documentation updated
- [ ] Performance acceptable
- [ ] No security risks
- [ ] Ready to merge
```

---

**Last Updated**: 2026-05-25
**Governance Version**: 1.0