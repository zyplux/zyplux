up:
    ./src/main.py

_prime-sudo:
    sudo -v

lint:
    ruff check --fix
    ruff format

tc: lint
    uvx pyright src
