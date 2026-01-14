![Ruff](https://img.shields.io/badge/style-ruff-0a7bff?logo=ruff&logoColor=white)
![Ruff CI](https://github.com/Sergeileduc/lemonde-sl/actions/workflows/ruff.yml/badge.svg)

# lemonde-sl

A small, clean, typed Python client for interacting with **Le Monde** (login, PDF retrieval, etc.).  
The project uses a modern workflow based on **uv**, **ruff**, **mypy**, **invoke**, and **hatchling**, with a `src/` layout.

## ✨ Features

- Synchronous and asynchronous clients (`LeMonde`, `LeMondeAsync`)
- Email + password authentication
- PDF article download
- Strict type checking (mypy)
- Unified linting/formatting (ruff)
- Modern build system (hatchling)
- Automated tasks (invoke)
- Fully compatible with **uv** for fast, reproducible environments

## 📦 Installation

The package is not published on PyPI. Install it directly from GitHub:

### With uv

```bash
uv pip install git+https://github.com/Sergeileduc/lemonde-sl.git
```

### With pip

```bash
pip install git+https://github.com/Sergeileduc/lemonde-sl.git
```

## 🚀 Usage

```python
from lemonde_sl import LeMonde

with LeMonde() as lm:
    lm.fetch_pdf(url=URL1, email=email, password=password)
```

Asynchronous version:

```python
from lemonde_sl import LeMondeAsync

async with LeMondeAsync() as lm:
    await lm.fetch_pdf(url=URL1, email=email, password=password)
```

## 🛠 Development

Clone the repository:

```bash
git clone https://github.com/Sergeileduc/lemonde-sl.git
cd lemonde-sl
```

Install dependencies:

```bash
uv sync
```

### Available tasks

```bash
invoke lint     # Ruff checks
invoke format   # Format code
invoke test     # Run pytest
invoke build    # Build wheel + sdist
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

## 📁 Project structure

```shell
lemonde-sl/
│
├── src/
│   └── lemonde_sl/
│       ├── __init__.py
│       └── client.py
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

## 📄 License

MIT — see `LICENSE`.
