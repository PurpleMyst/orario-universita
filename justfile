set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

run:
    uv run python -m orario_universita

format:
    uvx isort orario_universita
    uvx ruff format orario_universita
