# Contributing to Samvid Trading Core

Thank you for your interest in contributing to Samvid! This document provides guidelines and instructions for contributing to our institutional-grade trading platform.

## Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Please read and adhere to our code of conduct when participating in this project.

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+ (for JavaScript components)
- Rust 1.70+ (for performance-critical modules)
- Git

### Development Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/AshishTalpada/samvid-trading-core.git
cd samvid-trading-core
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

### Branch Naming
- Feature: `feature/description`
- Bug fix: `fix/description`
- Documentation: `docs/description`
- Performance: `perf/description`

### Commit Messages
Follow conventional commits format:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

### Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** with clear, atomic commits
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Run linting and tests** before pushing
6. **Create a PR** with a clear description
7. **Ensure CI/CD passes** and address review feedback

### Code Quality Standards

#### Python Code
- Follow PEP 8 style guide
- Use type hints
- Minimum test coverage: 80%
- Use `black` for formatting
- Use `flake8` for linting
- Use `mypy` for type checking

```bash
black src/
flake8 src/
mypy src/
pytest --cov=src/
```

#### JavaScript Code
- Follow ESLint configuration
- Use Prettier for formatting
- Write unit tests for components

#### Rust Code
- Follow Rust naming conventions
- Run `cargo fmt` and `cargo clippy`
- Add documentation comments
- Ensure no unsafe code without justification

### Testing

All PRs must include tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ --cov-report=html

# Run specific test file
pytest tests/test_trading_engine.py

# Run with verbose output
pytest -v
```

## Areas for Contribution

### High Priority
- **Performance Optimizations**: Improve Dhatu macro-causation calculation
- **Agent Mesh Enhancements**: Improve consensus mechanisms
- **Risk Management**: Add new risk models and safeguards
- **Documentation**: Expand architecture and algorithm documentation

### Medium Priority
- **UI/Dashboard**: Enhance monitoring dashboards
- **Backtesting**: Improve backtesting framework
- **API Extensions**: Add new API endpoints
- **Integration Tests**: Expand integration test coverage

### Welcome Contributions
- Bug reports and fixes
- Performance improvements
- Documentation improvements
- Security vulnerability reports
- Test coverage expansion

## Reporting Issues

### Bugs
- Use clear, descriptive title
- Provide exact steps to reproduce
- Include expected vs actual behavior
- Attach logs/screenshots if applicable
- Specify version and environment

### Feature Requests
- Describe the motivation and use case
- Provide examples of expected behavior
- List any related issues or discussions

## Security Considerations

- **Never commit secrets** (API keys, tokens, credentials)
- **Report security issues privately** to the maintainers
- **Validate all external inputs** in trading code
- **Implement rate limiting** for API endpoints
- **Use HTTPS** for all external communications

## Performance and Compliance

For trading-related contributions:
- Include latency measurements
- Provide throughput benchmarks
- Document compliance implications
- Consider regulatory requirements
- Test under market stress conditions

## Documentation

All code should include:
- Docstrings for functions/classes
- Type hints for parameters and returns
- Example usage for public APIs
- Comments for complex logic
- Architecture diagrams for major components

## Review Process

1. **Automated checks** (linting, tests, coverage)
2. **Code review** by at least one maintainer
3. **Architecture review** for core trading logic
4. **Testing verification** across environments
5. **Approval and merge**

## Questions?

- Open an issue with your question
- Check existing documentation
- Review past issues and PRs
- Contact maintainers directly

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Samvid! Together we're building the future of collective intelligence trading.**