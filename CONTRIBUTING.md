# Contributing to ApacheCon 2022 IoT Demo

Thank you for your interest in contributing to this project! This document provides guidelines for local development and testing.

## Development Environment

### Prerequisites

- Python 3.9+
- Docker 20.10+
- Docker Compose 2.0+
- Git

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ottlukas/ApacheCon_2022_IoT.git
   cd ApacheCon_2022_IoT
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/macOS
   # .venv\Scripts\activate   # On Windows
   ```

3. **Install development dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

## Local Testing with Docker

### Start All Services

```bash
docker-compose up -d
```

This starts:
- Zenoh router
- Apache IoTDB 2.x
- API service

### Test the API

```bash
# Health check
curl http://localhost:8080/health

# Publish to Zenoh
curl "http://localhost:8080/zenoh/publish?path=/myfactory/machine1/temp&value=25"

# Query from IoTDB
curl "http://localhost:8080/iotdb/query?limit=10"
```

### Stop Services

```bash
docker-compose down
```

### Clean Up

To remove volumes and start fresh:

```bash
docker-compose down -v
```

## Running Tests

### Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_api.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Integration Tests

Integration tests require Docker services to be running:

```bash
# Start services first
docker-compose up -d

# Run integration tests
python -m pytest tests/test_integration.py -v
```

## Code Quality

### Linting

```bash
pylint src/ tests/ --disable=C0114,C0115,C0116,W0613
```

### Code Formatting

```bash
black src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Git Workflow

### Branching

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Add your feature description"
   ```

3. Push to remote:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. Create a Pull Request to `main` branch.

### Commit Messages

- Use clear, descriptive commit messages
- Reference issue numbers if applicable
- Follow [Conventional Commits](https://www.conventionalcommits.org/) style

### Pull Requests

- Provide a clear description of changes
- Include screenshots if UI changes
- Reference related issues
- Ensure all tests pass
- Update documentation as needed

## Version Compatibility

This project targets the following versions:

- **Zenoh**: >= 0.11.0
- **Apache IoTDB**: >= 2.0.0
- **Panel**: >= 1.3.0
- **Python**: >= 3.9

### Updating Dependencies

To update dependencies:

1. Update version in `requirements.txt`
2. Update version in `pyproject.toml`
3. Update Dockerfile if needed
4. Test thoroughly
5. Update documentation

### Version Mismatch Handling

The API includes error handling for version mismatches. If you encounter compatibility issues:

1. Check the error message for version requirements
2. Update the dependency to a compatible version
3. Test the changes
4. Document any breaking changes

## Debugging

### Enable Debug Logging

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Docker Debugging

```bash
# View logs for a specific service
docker-compose logs api

# Enter a running container
docker-compose exec api bash

# View real-time logs
docker-compose logs -f
```

### Common Debug Commands

```bash
# Check Zenoh connection
curl http://localhost:8000/router/status

# Check IoTDB connection
./sbin/start-cli.sh -h 127.0.0.1 -p 6667 -u root -pw root
> SELECT * FROM root.myfactory.machine1

# Test API endpoints
curl -v http://localhost:8080/health
```

## Project Structure

```
ApacheCon_2022_IoT/
├── src/
│   ├── __init__.py
│   ├── api.py           # Main FastAPI application
│   ├── zenoh_client.py  # Zenoh client with version compatibility
│   └── iotdb_client.py  # IoTDB client with version compatibility
├── tests/
│   ├── __init__.py
│   ├── test_api.py       # API endpoint tests
│   ├── test_zenoh_client.py  # Zenoh client tests
│   └── test_iotdb_client.py  # IoTDB client tests
├── Dockerfile           # Multi-stage build configuration
├── docker-compose.yml   # Service orchestration
├── requirements.txt     # Production dependencies
├── pyproject.toml       # Project metadata and dev dependencies
├── README.md            # User documentation
└── CONTRIBUTING.md      # This file
```

## Best Practices

1. **Error Handling**: Always include proper error handling and logging
2. **Type Hints**: Use type hints for better code maintainability
3. **Documentation**: Update docstrings and comments
4. **Tests**: Add tests for new functionality
5. **Backward Compatibility**: Maintain backward compatibility where possible
6. **Security**: Never commit secrets or credentials
7. **Performance**: Consider performance implications of changes

## Reporting Issues

When reporting issues:

1. Include steps to reproduce
2. Provide error messages
3. Specify your environment (OS, Python version, Docker version, etc.)
4. Include relevant logs
5. Describe expected vs actual behavior

## Code Review Process

1. All PRs require at least one approval
2. CI checks must pass
3. Code must follow project style guidelines
4. Tests must cover new functionality
5. Documentation must be updated

## Continuous Integration

The project uses GitHub Actions for CI/CD:

- **Test Workflow**: Runs on every push and PR
  - Unit tests
  - Linting
  - Code formatting check

- **Build Workflow**: Runs on releases
  - Builds Docker image
  - Pushes to container registry

## Release Process

1. Update version in `pyproject.toml` and `requirements.txt`
2. Update CHANGELOG (if exists)
3. Create a Git tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
4. Create a GitHub Release
5. Docker image will be built automatically

## Additional Resources

- [Zenoh Documentation](https://zenoh.io/docs/)
- [Apache IoTDB Documentation](https://iotdb.apache.org/UserGuide/)
- [Panel Documentation](https://panel.holoviz.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
