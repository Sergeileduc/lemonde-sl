FROM python:3.13-slim

# Dépendances système pour WeasyPrint
RUN apt-get update && apt-get install -y \
    libcairo2 \
    pango1.0-tools \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    libharfbuzz0b \
    libfribidi0 \
    && apt-get clean

# Copier ton projet
WORKDIR /app
COPY . .

# Installer ton package via pyproject.toml
RUN pip install .

# Commande par défaut
CMD ["python", "main.py"]
