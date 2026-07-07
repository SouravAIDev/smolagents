# Contributing to Book Finder Agent

Thank you for your interest in contributing to the Book Finder Agent! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Making Changes](#making-changes)
5. [Testing](#testing)
6. [Code Style](#code-style)
7. [Git Workflow](#git-workflow)
8. [Submitting Changes](#submitting-changes)
9. [Documentation](#documentation)
10. [Troubleshooting](#troubleshooting)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful, constructive, and professional in all interactions.

## Getting Started

Before you begin:

1. Fork the repository on GitHub
2. Clone your fork locally: `git clone https://github.com/your-username/book-finder-agent.git`
3. Add the upstream remote: `git remote add upstream https://github.com/original-repo/book-finder-agent.git`
4. Create a new branch for your feature: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- PostgreSQL client tools (optional, for direct database access)
- Git

### Initial Setup

1. Copy the environment file:
   ```bash
   make env-setup
   ```

2. Update `.env` with your configuration:
   ```bash
   # Edit .env with your API keys and database settings
   nano .env
   ```

3. Install dependencies:
   ```bash
   make install-dev
   ```

4. Start the development environment:
   ```bash
   make dev-docker
   ```

5. Verify the setup:
   ```bash
   make health-check
   ```

## Making Changes

### Project Structure

```
book-finder-agent/
├── book_finder_agent.py          # Main agent orchestration logic
├── book_finder_agent_setup.py    # Configuration schema
├── book_finder_agent_trace.py    # Tracing schema
├── book_helper.py                # Filter definitions and mappings
├── database_retrieval_utils.py   # Database query utilities
├── book_finder_utilities.py      # Data processing utilities
├── citation_helpers.py           # Citation extraction and formatting
├── show_more_details_utilities.py # Session state management
├── ai_summary_utils.py           # Embedding operations
├── run.py                        # Flask application entry point
├── Config.py                     # Configuration management
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image definition
├── docker-compose.yml            # Local development stack
├── .env.example                  # Example environment configuration
├── k8s-deployment.yaml           # Kubernetes deployment manifest
├── Makefile                      # Development task automation
├── tests/                        # Test suite
├── queries/                      # SQL templates
├── scripts/                      # Utility scripts
└── README.md                     # Project documentation
```

### Code Organization Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **DRY (Don't Repeat Yourself)**: Reuse code across modules
3. **SOLID Principles**: Follow solid object-oriented design
4. **Type Hints**: Use Python type hints for clarity and IDE support
5. **Error Handling**: Comprehensive exception handling with informative messages

### Guidelines for Different File Types

#### Python Files

- Use type hints for function parameters and return values
- Add docstrings to all public functions and classes
- Maximum line length: 120 characters
- Use meaningful variable names
- Import statements should be organized (stdlib, third-party, local)

#### SQL Templates (queries/*.sql)

- Include descriptive comments explaining the query purpose
- Use parameterized queries to prevent SQL injection
- Format for readability with proper indentation
- Test query performance with realistic data volumes

#### Configuration Files

- Document all configuration options
- Provide sensible defaults
- Include examples of valid values
- Separate secrets from non-sensitive configuration

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run tests in watch mode
make test-watch
```

### Writing Tests

1. Place test files in the `tests/` directory
2. Name test files as `test_*.py`
3. Use descriptive test function names: `test_function_does_something_specific`
4. Include docstrings explaining test purpose
5. Use fixtures for common setup/teardown
6. Aim for at least 80% code coverage

#### Test Template

```python
import pytest
from unittest.mock import Mock, patch

class TestYourFeature:
    """Tests for YourFeature."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        # Your setup code
        yield
        # Your teardown code
    
    def test_feature_does_something(self, setup):
        """Test that feature performs expected behavior."""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = your_function(input_data)
        
        # Assert
        assert result is not None
        assert result["expected_key"] == "expected_value"
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

```bash
# Format code automatically
make format

# Check style compliance
make lint
```

### Tools Used

- **Black**: Code formatter (line length: 120)
- **isort**: Import statement organizer
- **pylint**: Code quality checker
- **flake8**: Style guide enforcement
- **bandit**: Security issue detection

### Example: Properly Formatted Function

```python
def calculate_book_relevance_score(
    similarity_score: float,
    document_count: int,
    keyword_matches: int,
    context_weight: float = 0.5,
    document_weight: float = 0.2,
    keyword_weight: float = 0.3
) -> float:
    """
    Calculate weighted relevance score for a book.
    
    Args:
        similarity_score: Semantic similarity [0-1]
        document_count: Number of matching documents
        keyword_matches: Count of keyword matches
        context_weight: Weight for context scoring
        document_weight: Weight for document count
        keyword_weight: Weight for keyword matches
    
    Returns:
        Weighted relevance score [0-1]
    
    Raises:
        ValueError: If weights don't sum to 1.0
    """
    total_weight = context_weight + document_weight + keyword_weight
    if abs(total_weight - 1.0) > 0.01:  # Allow for floating point error
        raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
    
    # Normalize document and keyword scores
    normalized_doc_score = min(document_count / 10.0, 1.0)
    normalized_keyword_score = min(keyword_matches / 5.0, 1.0)
    
    # Calculate weighted score
    final_score = (
        (similarity_score * context_weight) +
        (normalized_doc_score * document_weight) +
        (normalized_keyword_score * keyword_weight)
    )
    
    return max(0.0, min(final_score, 1.0))  # Clamp to [0-1]
```

## Git Workflow

### Branch Naming

Use descriptive branch names:

- `feature/short-description` - New feature
- `fix/short-description` - Bug fix
- `docs/short-description` - Documentation update
- `refactor/short-description` - Code refactoring
- `test/short-description` - Test additions

### Commit Messages

Write clear, descriptive commit messages:

```
[TYPE] Brief description of changes

More detailed explanation if needed. This section should explain
WHY the change was made, not WHAT was changed (the diff shows that).

Examples:
- [FEATURE] Add semantic similarity filtering
- [FIX] Resolve SQL injection vulnerability in query builder
- [DOCS] Update API endpoint documentation
- [REFACTOR] Extract utility functions from agent class
- [TEST] Add coverage for embedding generation
```

### Working with Branches

```bash
# Create and switch to feature branch
git checkout -b feature/add-book-genre-filter

# Make changes and commit
git add .
git commit -m "[FEATURE] Add book genre filter with semantic search"

# Keep branch updated with upstream changes
git fetch upstream
git rebase upstream/main

# Push to your fork
git push origin feature/add-book-genre-filter
```

## Submitting Changes

### Before Submitting

1. Update your branch with latest upstream:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. Run the full quality suite:
   ```bash
   make quality
   ```

3. Test in Docker environment:
   ```bash
   make docker-up
   make api-test
   ```

4. Write/update tests for your changes

5. Update documentation if needed

### Pull Request Process

1. Push your branch to your fork
2. Create a Pull Request with a clear title and description
3. Link related issues if applicable
4. Describe the changes and motivation
5. Include screenshots/examples for UI changes
6. Ensure CI/CD checks pass
7. Request review from maintainers
8. Address review feedback

### Pull Request Template

```markdown
## Description
Briefly describe the changes in this PR.

## Motivation and Context
Why is this change needed? What problem does it solve?

## Related Issues
Closes #123

## Type of Change
- [ ] Feature (new functionality)
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Testing
Describe tests added or modified.

## Screenshots (if applicable)
Add screenshots for UI changes.

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] All tests pass
```

## Documentation

### Updating Documentation

1. Update relevant `.md` files in the project root
2. Include docstrings in Python code
3. Update API documentation in README if endpoints change
4. Add examples for new features

### Documentation Standards

- Use clear, concise language
- Include code examples where applicable
- Link to related sections
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'book_finder_agent'"

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
make install-dev
```

#### Docker containers won't start

```bash
# Check Docker status
docker-compose ps

# View detailed logs
make docker-logs SERVICE=book_finder_agent FOLLOW=1

# Reset everything
make docker-reset
make docker-up
```

#### Database connection errors

```bash
# Verify database is running
make docker-logs SERVICE=postgres FOLLOW=1

# Reset database
make db-reset

# Connect directly to verify
make db-shell
```

#### Tests failing

```bash
# Run tests with verbose output
make test

# Check test coverage
make test-cov

# Run specific test
. .venv/bin/activate && pytest tests/test_book_finder_agent.py::TestBookFinderAgent::test_name -v
```

### Getting Help

1. Check the [README.md](README.md) for project documentation
2. Review existing issues for similar problems
3. Check error logs: `docker-compose logs`
4. Create a detailed issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs

## Recognition

Contributors are recognized in:

1. Project README contributors section
2. Release notes for merged PRs
3. GitHub insights/contributors page

Thank you for contributing to Book Finder Agent!

