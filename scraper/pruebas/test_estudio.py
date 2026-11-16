"""El calendario que muestra el Estudio (data/estudio-plan.json) debe coincidir con el del robot."""
import json
from pathlib import Path

import redes

PLAN = json.loads((Path(__file__).resolve().parents[2] / "data" / "estudio-plan.json").read_text(encoding="utf-8"))


def test_productos_coinciden():
    assert PLAN["producto_dia"] == redes.PRODUCTO_DIA
    assert PLAN["producto_reel"] == redes.PRODUCTO_REEL


def test_franjas_y_dias_coinciden():
    robot = {f: list(d) for f, _, _, d in redes.VENTANAS}
    assert {x["id"]: x["dias"] for x in PLAN["franjas"]} == robot


def test_herramientas_tienen_estado_valido():
    assert all(h["estado"] in ("activo", "pendiente") for h in PLAN["herramientas"])
