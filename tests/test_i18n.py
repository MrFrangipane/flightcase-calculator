"""Tests de la traducción al español de los textos generados por el dominio."""

from flightcase.i18n import tr
from flightcase.application import CaseInputDTO, InsideWallDTO, CalculateFlightCaseUseCase


def test_tr_textos_fijos_y_patrones():
    assert tr("Top & Bottom Panels") == "Piso y techo"
    assert tr("Wood Panel - Lid") == "Madera - Tapa"
    assert tr("Inside Walls (3 pcs, Width-wise)") == "Divisores (3 u., transversales)"
    assert tr("Width Wall #2 (Width-wise)") == "Divisor transversal #2 (transversal)"
    assert tr("Height adjusted for lid profile (-5.0mm)") == "Altura ajustada por el perfil de tapa (-5.0mm)"
    assert tr("Lid = 109 mm") == "Tapa = 109 mm"
    assert tr("Compartment 3 (Sec 1,3)") == "Compartimento 3 (sec. 1,3)"


def test_tr_deja_igual_lo_desconocido():
    assert tr("Mi divisor") == "Mi divisor"
    assert tr("") == ""


def test_tr_cubre_toda_la_lista_de_cortes():
    walls = [
        InsideWallDTO("width_wise", 200.0, label="Width Wall #1"),
        InsideWallDTO("width_wise", 400.0, label="Width Wall #2"),
        InsideWallDTO("length_wise", 250.0, label="Length Wall #1"),
    ]
    for self_cut in (False, True):
        result = CalculateFlightCaseUseCase.execute(CaseInputDTO(walls=walls, self_cut_lid=self_cut))
        for piece in result.wood_cut_list + result.alu_profiles_list:
            for text in (piece.name, piece.category, piece.notes):
                if text:
                    assert tr(text) != text, f"Sin traducir: {text!r}"
        for comp in result.compartments:
            assert tr(comp.name) != comp.name
