# name-of-package-sl

A clean, modern Python package built with **uv**, **ruff**, **invoke**, and **hatchling**.  
This project follows a strict, reproducible workflow with a `src/` layout, type checking, and automated tasks.

## Features

- Modern Python packaging with **Hatchling**
- Strict type checking with **mypy**
- Unified linting/formatting with **ruff**
- Task automation with **invoke**
- `src/` layout for clean imports
- Fully compatible with **uv** for fast, isolated environments

## Installation

```bash
uv pip install name-of-package-sl
```

Or with pip:

```bash
pip install name-of-package-sl
```

## Usage

```python
import name_of_package_sl

print(name_of_package_sl.__version__)
```

## Development

Clone the repository:

```bash
git clone https://github.com/your/repo.git
cd name-of-package-sl
```

Install dependencies:

```bash
uv sync
```

### Available tasks

```bash
invoke lint     # Run ruff checks
invoke format   # Format code with ruff
invoke test     # Run pytest
invoke build    # Build wheel + sdist
invoke publish  # Publish to PyPI
invoke clean    # Remove build artifacts
```

### Running tests

```bash
invoke test
```

### Linting & formatting

```bash
invoke lint
invoke format
```

## Project structure

```shell
name-of-package-sl/
│
├── src/
│   └── name_of_package_sl/
│       └── __init__.py
│
├── tests/
│   └── test_basic.py
│
├── tasks.py
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
└── docs/
```

## License

MIT License. See `LICENSE` for details.
