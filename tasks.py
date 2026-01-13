import contextlib
import os
import shutil
import subprocess
import sys
import webbrowser
from itertools import chain
from pathlib import Path
from platform import uname

from invoke.tasks import task

# TASKS------------------------------------------------------------------------

@task
def sync(c):
    """Synchronize the environment and show installed versions."""
    c.run("uv sync --dev", echo=True)
    print("\nInstalled packages:")
    c.run("uv pip list", echo=True)

@task
def lint(c):
    c.run("ruff check .", echo=True)
    c.run("mypy", echo=True)


@task
def format(c):
    c.run("ruff format .", echo=True)


@task
def test(c):
    c.run("pytest -q", echo=True)


@task
def build(c):
    c.run("uv build")


@task
def publish(c):
    c.run("uv publish")


@task
def cleantest(c):
    """Clean artifacts like *.pyc, __pycache__, .pytest_cache, etc..."""
    # Find .pyc or .pyo files and delete them
    exclude = ("venv", ".venv")
    p = Path(".")
    genpyc = (i for i in p.rglob("*.pyc") if not str(i.parent).startswith(exclude))
    genpyo = (i for i in p.rglob("*.pyo") if not str(i.parent).startswith(exclude))
    artifacts = chain(genpyc, genpyo)
    for art in artifacts:
        os.remove(art)

    # Delete caches folders
    caches = [
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
    ]
    for name in caches:
        for folder in Path(".").rglob(name):
            shutil.rmtree(folder, ignore_errors=True)

    # Delete coverage artifacts
    with contextlib.suppress(FileNotFoundError):
        os.remove(".coverage")
        shutil.rmtree("htmlcov")


@task
def cleanbuild(c):
    """Clean dist and build"""
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree("build")
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree("dist")
    eggs = Path(".").glob("*.egg-info")
    with contextlib.suppress(FileNotFoundError):
        for egg in eggs:
            shutil.rmtree(egg)


@task
def cleandoc(c):
    """Clean documentation files."""
    p = Path(".").resolve() / "docs" / "build"
    print(p)
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(p)


@task(cleantest, cleanbuild, cleandoc)
def clean(c):
    """Equivalent to both cleanbuild and cleantest..."""
    print("Cleaning")
    pass

@task(clean)
def prune(c):
    """
    Remove all caches, virtual environments, and build artifacts.
    Equivalent to a full reset of the workspace.
    """
    root = Path(".")

    # 1. Remove .venv
    venv = root / ".venv"
    if venv.exists():
        print(f"Removing {venv}")
        shutil.rmtree(venv, ignore_errors=True)

    # 2. Remove tool caches
    caches = [
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".coverage",
        "htmlcov",
    ]
    for name in caches:
        path = root / name
        if path.exists():
            print(f"Removing {path}")
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)



@task
def coverage(c):
    """
    Run test coverage and generate HTML report.
    """
    c.run("coverage erase", echo=True)
    c.run("coverage run -m pytest", echo=True)
    c.run("coverage html", echo=True)
    print("\nHTML report generated in: htmlcov/index.html")
    index = get_index_path()
    webbrowser.open(index.as_uri())


@task(cleandoc)
def doc(c):
    docs = Path("docs")
    c.run("make html", echo=True, cwd=str(docs))
    path = docs / "build" / "html" / "index.html"
    webbrowser.open(path.resolve().as_uri())


# UTILS -----------------------------------------------------------------------


def get_platform():
    """Check the platform (Windows, Linux, or WSL)."""
    u = uname()
    if u.system == "Windows":
        return "windows"
    elif u.system == "Linux" and "microsoft" in u.release:
        return "wsl"
    else:
        return "linux"


def get_index_path() -> Path:
    """Return full path to htmlcov/index.html, handling Windows, Linux, and WSL."""
    platform = get_platform()

    # Windows or native Linux → simple path
    if platform != "wsl":
        return Path.cwd() / "htmlcov" / "index.html"

    # WSL → convert current directory to Windows path
    process = subprocess.run(
        ["wslpath", "-w", "."],
        capture_output=True,
        text=True,
        check=True,
    )
    win_path = process.stdout.strip().replace("\\", "/")
    return Path(win_path) / "htmlcov" / "index.html"


def _venv_name(py_version: str) -> str:
    """Return a venv folder name based on Python version."""
    return f".venv{py_version.replace('.', '')}"


def _find_python_executable(c, py: str) -> str:
    """
    Trouve un exécutable Python correspondant à la version demandée.
    Essaie dans cet ordre :
    1. python3.X
    2. py -3.X (Windows launcher)
    3. python (si version correspond)
    """
    major, minor = py.split(".")
    target = f"{major}.{minor}"

    # 1. python3.X
    exe = f"python{target}"
    try:
        out = c.run(f"{exe} --version", hide=True).stdout
        if target in out:
            return exe
    except Exception:
        pass

    # 2. py -3.X (Windows)
    try:
        out = c.run(f"py -{target} --version", hide=True).stdout
        if target in out:
            return f"py -{target}"
    except Exception:
        pass

    # 3. python (si version correspond)
    try:
        out = c.run("python --version", hide=True).stdout
        if target in out:
            return "python"
    except Exception:
        pass

    print(f"✖ Impossible de trouver Python {target} sur ce système.")
    sys.exit(1)
