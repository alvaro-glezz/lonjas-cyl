"""Configuración común de las pruebas: carga los módulos del robot sin tocar la red."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRAPER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRAPER))


def _cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, SCRAPER / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def act():
    mod = _cargar("actualizar")
    def sin_red(*a, **k):
        raise AssertionError("Las pruebas no deben descargar nada")
    mod.bajar = sin_red
    return mod


@pytest.fixture(scope="session")
def avisar():
    return _cargar("avisar")


@pytest.fixture(scope="session")
def jcyl():
    return _cargar("importar_jcyl")
