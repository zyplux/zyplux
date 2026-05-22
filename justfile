up: _prime-sudo urls cargo uv apt gpu apps

_prime-sudo:
    sudo -v

urls:
    ./src/install_from_urls.py

cargo:
    ./src/install_cargo_packages.py

uv:
    ./src/install_uv_packages.py

apt:
    ./src/configure_with_apt.py

gpu:
    ./src/configure_gpu.py

apps:
    ./src/configure_apps.py
