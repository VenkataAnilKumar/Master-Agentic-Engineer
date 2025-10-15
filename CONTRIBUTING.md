# Contributing to Master Agentic AI Engineer Program

Thank you for your interest in contributing to the Master Agentic AI Engineer Program! This document provides guidelines and instructions for contributing to this project.

## 🌟 How to Contribute

We welcome contributions in many forms:
- 📝 Documentation improvements
- 🐛 Bug fixes and issue reports
- ✨ New features and enhancements
- 🧪 Tests and quality assurance
- 📚 Educational content and examples
- 🎨 Design and user experience improvements

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Master-Agentic-Engineer.git
cd Master-Agentic-Engineer

# Add upstream remote
git remote add upstream https://github.com/VenkataAnilKumar/Master-Agentic-Engineer.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

## 📋 Contribution Guidelines

### Code Standards

All code contributions must follow our [Engineering Standards](engineering-standards.md):

#### Python Code
- **Python Version**: 3.11+
- **Formatting**: Black (line length 88)
- **Linting**: Flake8
- **Type Hints**: Required for all functions
- **Docstrings**: Google-style for all public APIs

#### Code Quality Checks

```bash
# Format code
black .

# Check linting
flake8 src tests

# Sort imports
isort src tests

# Type checking
mypy src

# Run tests
pytest tests/ --cov=src --cov-report=term-missing
```

### Commit Messages

Follow conventional commit format:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(agent): add memory compression capability

Implement memory compression using summarization to reduce
context window usage and improve performance.

Closes #123
```

```
docs(week-01): add advanced prompt engineering examples

fix(security): patch authentication vulnerability
```

### Pull Request Process

1. **Update Documentation**: Ensure README and relevant docs are updated
2. **Add Tests**: Include tests for new functionality
3. **Pass CI Checks**: All automated checks must pass
4. **Request Review**: Request review from maintainers
5. **Address Feedback**: Respond to review comments promptly

#### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
Describe testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No breaking changes (or documented)
```

## 🧪 Testing Guidelines

### Writing Tests

```python
"""Test module for agent functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent_lib.core import BaseAgent, AgentConfig


class TestBaseAgent:
    """Test suite for BaseAgent."""
    
    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return AgentConfig(
            name="test_agent",
            model="gpt-4",
            temperature=0.7
        )
    
    @pytest.mark.asyncio
    async def test_agent_execution(self, agent_config):
        """Test successful agent execution."""
        # Arrange
        agent = TestAgent(agent_config)
        task = "Test task"
        
        # Act
        result = await agent.execute(task)
        
        # Assert
        assert result["success"] is True
        assert "result" in result
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests
pytest tests/integration/

# Run performance tests
pytest tests/performance/ --benchmark-only
```

## 📚 Documentation Guidelines

### Documentation Structure

- **README Files**: Every module/package should have a README
- **Docstrings**: All public functions, classes, and modules
- **Examples**: Include working code examples
- **API Documentation**: Auto-generated from docstrings

### Docstring Format

```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """Brief description of function.
    
    Longer description explaining functionality, behavior,
    and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param2 is negative
        RuntimeError: When operation fails
        
    Example:
        ```python
        result = function_name("test", 42)
        print(result["value"])
        ```
    """
    pass
```

## 🎓 Weekly Module Contributions

### Module Structure

Each weekly module should include:

```
week-XX-module-name/
├── README.md              # Theory, objectives, instructions
├── notebook.ipynb         # Hands-on implementation
├── exercises/             # Practice exercises
│   ├── exercise_1.py
│   ├── exercise_2.py
│   └── solution_guide.md
└── production-configs/    # Deployment configurations
    ├── Dockerfile
    ├── docker-compose.yml
    └── config.yaml
```

### Module README Template

```markdown
# Week X: Module Name

## 🎯 Learning Objectives
- Objective 1
- Objective 2
- Objective 3

## 📚 Theory & Concepts
Content here...

## 🛠️ Technical Implementation
Code examples and explanations...

## 📋 Assignments & Exercises
Exercise descriptions...

## 🔧 Production Configuration
Production setup guide...

## 📊 Evaluation Metrics
Success criteria...

## 📚 Additional Resources
Links and references...

## 🎯 Week X Deliverables
List of deliverables...

## 🚀 Next Week Preview
Preview of next week...
```

## 🐛 Reporting Issues

### Bug Reports

Use this template for bug reports:

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Step 1
2. Step 2
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Windows 11, macOS 14, Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- Package Version: [e.g., 1.0.0]

**Additional Context**
Any other relevant information
```

### Feature Requests

Use this template for feature requests:

```markdown
**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should it work?

**Alternatives Considered**
What other solutions were considered?

**Additional Context**
Any other relevant information
```

## 🎨 Example Projects

### Project Structure

```
project-name/
├── README.md
├── src/
│   ├── agents/
│   ├── tools/
│   ├── utils/
│   └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── config/
│   ├── development.yaml
│   ├── production.yaml
│   └── test.yaml
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   └── usage.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

### Project README Template

```markdown
# Project Name

## Overview
Brief project description

## Features
- Feature 1
- Feature 2

## Architecture
Architecture overview

## Installation
Setup instructions

## Usage
Usage examples

## Configuration
Configuration guide

## Deployment
Deployment instructions

## Testing
Testing guide

## Performance
Performance metrics and benchmarks

## Contributing
Contribution guidelines

## License
License information
```

## 🔒 Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email: security@masteragenticai.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## 📞 Community

### Communication Channels

- **GitHub Discussions**: General questions and discussions
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time community chat
- **Email**: support@masteragenticai.com

### Code of Conduct

We are committed to providing a welcoming and inclusive environment:

- **Be Respectful**: Treat everyone with respect and kindness
- **Be Collaborative**: Work together constructively
- **Be Professional**: Maintain professional standards
- **Be Inclusive**: Welcome diverse perspectives and contributions

## 🏆 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Featured on project website (with permission)
- Invited to join the core team (for significant contributions)

## ❓ Questions?

If you have questions about contributing:

1. Check existing documentation
2. Search GitHub Discussions
3. Ask in Discord
4. Open a GitHub Discussion
5. Email the maintainers

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to the Master Agentic AI Engineer Program!** 🚀