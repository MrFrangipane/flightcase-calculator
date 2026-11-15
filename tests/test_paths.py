"""Tests de rutas de datos editables (app instalada con recursos de solo lectura)."""

from flightcase import paths
from flightcase.production.catalog import HardwareItem, load_hardware, save_hardware
from flightcase.domain.materials import WoodMaterial, load_wood_materials, save_wood_materials


def test_user_copy_overrides_bundled_resources(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHTCASE_DATA_DIR", str(tmp_path))
    bundled = paths.bundled_resource("hardware.json")
    before = bundled.read_text(encoding="utf-8")

    assert paths.editable_resource("hardware.json") == bundled
    save_hardware([HardwareItem("x", "Herraje X", unit_price=1.0)])
    assert (tmp_path / "hardware.json").is_file()
    assert [h.id for h in load_hardware()] == ["x"]
    assert bundled.read_text(encoding="utf-8") == before  # el recurso incluido no se toca

    save_wood_materials([WoodMaterial("Madera X", 12.0, 600.0, 30.0)])
    assert [m.name for m in load_wood_materials()] == ["Madera X"]
