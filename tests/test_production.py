"""Tests de catálogos, optimización de corte, presupuesto, DXF y paquete de producción."""

import json
import os

import pytest

from flightcase.application import (
    CaseInputDTO,
    InsideWallDTO,
    CalculateQuoteUseCase,
    ExportProductionPackUseCase,
)
from flightcase.production.catalog import Catalog, load_alu_profiles, load_hardware
from flightcase.production.dxf import sheet_plan_to_dxf
from flightcase.production.optimizer import BarCut, PanelPart, optimize_bars, optimize_sheets
from flightcase.production.quote import ProductionSettings, count_hardware


def _dto(**kw):
    base = dict(wood_density=700.0, wood_price=18.5, inner_length=800.0, inner_width=500.0, inner_total_height=400.0, inner_lid_height=100.0,
                wood_thickness=9.0, title="Prueba")
    base.update(kw)
    return CaseInputDTO(**base)


def test_default_catalogs_load():
    hw = load_hardware()
    profiles = load_alu_profiles()
    assert {"ball_corner", "butterfly_latch", "recessed_handle", "rivet"} <= {h.id for h in hw}
    assert {"lid_male", "lid_female", "edge_angle"} <= {p.kind for p in profiles}


def test_bar_optimizer_respects_bar_length_and_kerf():
    cuts = [BarCut("a", 1000)] * 4 + [BarCut("b", 1500)] * 2
    plan = optimize_bars(cuts, bar_length_mm=3000, kerf_mm=3)
    for bar in plan.bars:
        assert bar.used_mm <= 3000
    assert sum(len(b.cuts) for b in plan.bars) == 6
    assert plan.bar_count == 3  # 1500+1000 / 1500+1000 / 1000+1000


def test_bar_optimizer_reports_oversize():
    plan = optimize_bars([BarCut("largo", 5000)], bar_length_mm=4000)
    assert plan.bar_count == 0
    assert len(plan.oversize) == 1


def _overlap(a, b):
    return not (a.x_mm + a.length_mm <= b.x_mm or b.x_mm + b.length_mm <= a.x_mm or
                a.y_mm + a.width_mm <= b.y_mm or b.y_mm + b.width_mm <= a.y_mm)


def test_sheet_optimizer_no_overlap_and_inside_sheet():
    parts = [PanelPart(f"p{i}", 800, 500) for i in range(6)] + [PanelPart("s", 300, 200)] * 5
    plan = optimize_sheets(parts, 9.0, 2440, 1220, kerf_mm=4, trim_mm=10)
    placed = sum(len(s.placements) for s in plan.sheets)
    assert placed == len(parts)
    for sheet in plan.sheets:
        for p in sheet.placements:
            assert p.x_mm >= 10 - 1e-6 and p.y_mm >= 10 - 1e-6
            assert p.x_mm + p.length_mm <= 2430 + 1e-6
            assert p.y_mm + p.width_mm <= 1210 + 1e-6
        for i, a in enumerate(sheet.placements):
            for b in sheet.placements[i + 1:]:
                assert not _overlap(a, b)


def test_sheet_optimizer_rotation_toggle():
    part = PanelPart("alto", 1100, 2000)  # sólo entra girado
    assert optimize_sheets([part], 9.0, allow_rotation=True).sheet_count == 1
    assert len(optimize_sheets([part], 9.0, allow_rotation=False).oversize) == 1


def test_hardware_rules_scale_with_size_and_options():
    small = {i: q for i, q, _ in count_hardware(500, 300, 5, ProductionSettings())}
    assert small["ball_corner"] == 8
    assert small["butterfly_latch"] == 4  # 2 delante + 2 detrás, sin laterales
    assert small["recessed_handle"] == 2

    big = {i: q for i, q, _ in count_hardware(1200, 600, 50, ProductionSettings(castors=True, stacking_cups=True))}
    assert big["butterfly_latch"] == 3 * 2 + 2
    assert big["recessed_handle"] == 4
    assert big["castor_100"] == 2 and big["castor_100_brake"] == 2
    assert big["stacking_cup"] == 4

    hinged = {i: q for i, q, _ in count_hardware(1000, 500, 20, ProductionSettings(lid_hinged=True))}
    assert hinged["hinge"] == 3
    assert hinged["butterfly_latch"] == 3 + 2


def test_quote_totals_are_consistent():
    q = CalculateQuoteUseCase.execute(_dto(walls=[InsideWallDTO("width_wise", 250.0)]))
    lines = {c.concept.split(" (")[0]: c.amount for c in q.cost_lines}
    assert lines["Coste total"] == pytest.approx(q.materials_cost + q.labor_cost)
    assert q.net_price == pytest.approx(q.subtotal * 1.30)
    assert q.total_price == pytest.approx(q.net_price * 1.21)
    assert {p.kind for p in q.profiles} == {"lid_male", "lid_female", "edge_angle"}
    assert q.total_sheets == 1
    assert q.total_weight_kg > q.weight_wood_kg > 0
    assert not q.warnings


def test_quote_with_empty_catalog_warns_instead_of_failing():
    q = CalculateQuoteUseCase.execute(_dto(), catalog=Catalog(hardware=[], profiles=[]))
    assert q.hardware == [] and q.profiles == []
    assert q.warnings


def test_production_settings_roundtrip_in_project():
    dto = _dto()
    dto.production.castors = True
    dto.production.margin_pct = 45.0
    loaded = CaseInputDTO.from_json(dto.to_json())
    assert loaded.production.castors is True
    assert loaded.production.margin_pct == 45.0
    # Proyectos antiguos sin bloque de producción siguen abriendo
    data = json.loads(dto.to_json())
    del data["production"]
    assert CaseInputDTO.from_dict(data).production == ProductionSettings()


def test_dxf_is_readable_structure():
    plan = optimize_sheets([PanelPart("Piso", 818, 518)], 9.0)
    text = sheet_plan_to_dxf(plan, title="Prueba")
    assert text.startswith("0\nSECTION")
    assert text.rstrip().endswith("EOF")
    assert text.count("\nLINE\n") == 4 + 4  # placa + panel
    assert "CORTE" in text and "Piso" in text


def test_export_production_pack_writes_all_files(qapp, tmp_path):
    files = ExportProductionPackUseCase.execute(_dto(title="Mi caja"), str(tmp_path))
    names = sorted(os.path.basename(f) for f in files)
    assert "Mi_caja_9mm.dxf" in names
    assert "Mi_caja_hoja_montaje.pdf" in names
    assert "Mi_caja_presupuesto_interno.pdf" in names
    assert "Mi_caja_listado_materiales.csv" in names
    assert "Mi_caja_paneles.svg" in names
    for f in files:
        assert os.path.getsize(f) > 0
    with open(tmp_path / "Mi_caja_hoja_montaje.pdf", "rb") as fh:
        assert fh.read(4) == b"%PDF"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_shows_quote_and_persists_settings(qapp, tmp_path, monkeypatch):
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.application import LoadProjectUseCase

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    assert window._current_quote is not None
    price_before = window._current_quote.total_price
    assert window.costs_widget.lbl_total.text().endswith("€")

    window.costs_widget._checks["castors"].setChecked(True)
    assert window._current_quote.total_price > price_before
    assert any(h.item_id == "castor_100" for h in window._current_quote.hardware)

    project = tmp_path / "caja.fcproj"
    window._save_project_file(str(project))
    assert LoadProjectUseCase.execute(str(project)).production.castors is True

    from PySide6.QtWidgets import QFileDialog, QMessageBox
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    window._export_production_pack()
    assert any((tmp_path / "flightcase_produccion").glob("*.pdf"))
