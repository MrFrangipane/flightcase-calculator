"""Pestañas de presupuesto (herrajes, barras, placas, precio) y de catálogo editable."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...production.catalog import (
    AluProfileSpec,
    Catalog,
    HardwareItem,
    save_alu_profiles,
    save_hardware,
)
from ...production.quote import ProductionSettings, Quote


def _eur(v: float) -> str:
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _readonly_table(headers: List[str], parent: QWidget) -> QTableWidget:
    t = QTableWidget(0, len(headers), parent)
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _set_row(table: QTableWidget, row: int, values: List[str], numeric_from: int = 1) -> None:
    for col, value in enumerate(values):
        item = QTableWidgetItem(value)
        if col >= numeric_from:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table.setItem(row, col, item)


class CostsWidget(QWidget):
    """Opciones de fabricación y precio, y resultado del presupuesto."""

    settings_changed = Signal()

    # (atributo, etiqueta, mínimo, máximo, decimales, sufijo)
    _NUMERIC_FIELDS = [
        ("labor_rate", "Precio de la hora", 0, 1000, 2, " €/h"),
        ("labor_hours_base", "Horas fijas por caja", 0, 100, 2, " h"),
        ("labor_hours_per_m2", "Horas por m² exterior", 0, 20, 2, " h/m²"),
        ("consumables", "Consumibles por caja", 0, 1000, 2, " €"),
        ("margin_pct", "Margen", 0, 500, 1, " %"),
        ("vat_pct", "IVA", 0, 50, 1, " %"),
        ("wood_waste_pct", "Desperdicio de madera", 0, 100, 1, " %"),
        ("sheet_length_mm", "Largo de placa", 500, 5000, 0, " mm"),
        ("sheet_width_mm", "Ancho de placa", 300, 3000, 0, " mm"),
        ("saw_kerf_mm", "Grosor de sierra", 0, 10, 1, " mm"),
        ("sheet_trim_mm", "Saneado de borde de placa", 0, 50, 1, " mm"),
        ("profile_kerf_mm", "Grosor de corte de perfil", 0, 10, 1, " mm"),
    ]
    _BOOL_FIELDS = [
        ("lid_hinged", "Tapa con bisagras"),
        ("castors", "Base con ruedas (4, dos con freno)"),
        ("stacking_cups", "Tazas de apilado en la tapa"),
        ("extra_handles", "Asas también en los laterales largos"),
        ("allow_rotation", "Permitir girar paneles en la placa (sin veta)"),
        ("charge_full_sheets", "Cobrar placas enteras"),
        ("charge_full_bars", "Cobrar barras de perfil enteras"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._loading = False
        self._spins = {}
        self._checks = {}
        self._init_ui()
        self.set_settings(ProductionSettings())

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget(scroll)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Totales
        totals = QGroupBox("Resumen", body)
        tl = QFormLayout(totals)
        self.lbl_total = QLabel("—")
        self.lbl_total.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.lbl_net = QLabel("—")
        self.lbl_cost = QLabel("—")
        self.lbl_weight = QLabel("—")
        self.lbl_sheets = QLabel("—")
        tl.addRow("Precio final (con IVA):", self.lbl_total)
        tl.addRow("Precio sin IVA:", self.lbl_net)
        tl.addRow("Coste (materiales + mano de obra):", self.lbl_cost)
        tl.addRow("Peso total estimado:", self.lbl_weight)
        tl.addRow("Placas necesarias:", self.lbl_sheets)
        self.lbl_warnings = QLabel("")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet("color: #f87171;")
        tl.addRow(self.lbl_warnings)
        layout.addWidget(totals)

        # Opciones
        opts = QGroupBox("Opciones de construcción", body)
        ol = QVBoxLayout(opts)
        for attr, label in self._BOOL_FIELDS:
            cb = QCheckBox(label, opts)
            cb.toggled.connect(self._on_changed)
            self._checks[attr] = cb
            ol.addWidget(cb)
        layout.addWidget(opts)

        # Desglose de precio
        cost_box = QGroupBox("Desglose de precio", body)
        cl = QVBoxLayout(cost_box)
        self.table_costs = _readonly_table(["Concepto", "Importe"], cost_box)
        self.table_costs.setMinimumHeight(340)
        cl.addWidget(self.table_costs)
        layout.addWidget(cost_box)

        # Herrajes
        hw_box = QGroupBox("Herrajes calculados", body)
        hl = QVBoxLayout(hw_box)
        self.table_hardware = _readonly_table(["Herraje", "Cant.", "Precio u.", "Total", "Ubicación"], hw_box)
        self.table_hardware.setMinimumHeight(220)
        hl.addWidget(self.table_hardware)
        layout.addWidget(hw_box)

        # Barras y placas
        mat_box = QGroupBox("Barras de perfil y placas", body)
        ml = QVBoxLayout(mat_box)
        self.table_bars = _readonly_table(["Perfil", "Barras", "Metros usados", "Aprovechamiento", "Precio"], mat_box)
        self.table_bars.setMinimumHeight(130)
        ml.addWidget(self.table_bars)
        self.table_sheets = _readonly_table(["Espesor", "Placas", "Aprovechamiento"], mat_box)
        self.table_sheets.setMinimumHeight(110)
        ml.addWidget(self.table_sheets)
        layout.addWidget(mat_box)

        # Precios y parámetros
        price_box = QGroupBox("Mano de obra, precio y corte", body)
        pl = QFormLayout(price_box)
        for attr, label, lo, hi, dec, suffix in self._NUMERIC_FIELDS:
            sb = QDoubleSpinBox(price_box)
            sb.setRange(lo, hi)
            sb.setDecimals(dec)
            sb.setSuffix(suffix)
            sb.valueChanged.connect(self._on_changed)
            self._spins[attr] = sb
            pl.addRow(label + ":", sb)
        layout.addWidget(price_box)
        layout.addStretch(1)

    # --- ajustes ---
    def _on_changed(self, *_args) -> None:
        if not self._loading:
            self.settings_changed.emit()

    def set_settings(self, settings: ProductionSettings) -> None:
        self._loading = True
        try:
            for attr, sb in self._spins.items():
                sb.setValue(float(getattr(settings, attr)))
            for attr, cb in self._checks.items():
                cb.setChecked(bool(getattr(settings, attr)))
        finally:
            self._loading = False

    def get_settings(self) -> ProductionSettings:
        s = ProductionSettings()
        for attr, sb in self._spins.items():
            setattr(s, attr, float(sb.value()))
        for attr, cb in self._checks.items():
            setattr(s, attr, cb.isChecked())
        return s

    # --- resultado ---
    def set_quote(self, quote: Optional[Quote]) -> None:
        if quote is None:
            return
        self.lbl_total.setText(_eur(quote.total_price))
        self.lbl_net.setText(_eur(quote.net_price))
        self.lbl_cost.setText(_eur(quote.subtotal))
        self.lbl_weight.setText(
            f"{quote.total_weight_kg:.1f} kg (madera {quote.weight_wood_kg:.1f}, "
            f"perfiles {quote.weight_profiles_kg:.1f}, herrajes {quote.weight_hardware_kg:.1f})"
        )
        self.lbl_sheets.setText(str(quote.total_sheets))
        self.lbl_warnings.setText("\n".join(f"⚠ {w}" for w in quote.warnings))

        self.table_costs.setRowCount(len(quote.cost_lines))
        for r, line in enumerate(quote.cost_lines):
            _set_row(self.table_costs, r, [line.concept, _eur(line.amount)])

        self.table_hardware.setRowCount(len(quote.hardware))
        for r, h in enumerate(quote.hardware):
            _set_row(self.table_hardware, r, [h.name, str(h.quantity), _eur(h.unit_price), _eur(h.total_price), h.placement])
            self.table_hardware.item(r, 4).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.table_bars.setRowCount(len(quote.profiles))
        for r, p in enumerate(quote.profiles):
            _set_row(self.table_bars, r, [
                p.name, f"{p.bars} × {p.bar_length_mm / 1000:.1f} m", f"{p.total_length_m:.2f} m",
                f"{p.utilization_pct:.0f} %", _eur(p.price),
            ])

        self.table_sheets.setRowCount(len(quote.sheet_plans))
        for r, sp in enumerate(quote.sheet_plans):
            _set_row(self.table_sheets, r, [f"{sp.thickness_mm:g} mm", str(sp.sheet_count), f"{sp.utilization_pct:.0f} %"])


class CatalogWidget(QWidget):
    """Edición de los catálogos de herrajes y perfiles (se guardan en los JSON de recursos)."""

    catalog_changed = Signal()

    _HW_COLS = ["Id", "Nombre", "Categoría", "Precio u. (€)", "Peso (kg)", "Remaches por unidad"]
    _PR_COLS = ["Id", "Nombre", "Tipo", "Precio (€/m)", "Peso (kg/m)", "Largo de barra (mm)"]

    def __init__(self, catalog: Catalog, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.catalog = catalog
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel(
            "Precios y pesos de tus herrajes y perfiles. El tipo de perfil debe ser "
            "<b>lid_male</b>, <b>lid_female</b> o <b>edge_angle</b>. Los ids de herraje los usa el conteo automático."
        ))
        hw_box = QGroupBox("Herrajes", self)
        hl = QVBoxLayout(hw_box)
        self.table_hw = QTableWidget(0, len(self._HW_COLS), hw_box)
        self.table_hw.setHorizontalHeaderLabels(self._HW_COLS)
        self.table_hw.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_hw.horizontalHeader().setStretchLastSection(True)
        hl.addWidget(self.table_hw)
        layout.addWidget(hw_box, 2)

        pr_box = QGroupBox("Perfiles de aluminio", self)
        pl = QVBoxLayout(pr_box)
        self.table_pr = QTableWidget(0, len(self._PR_COLS), pr_box)
        self.table_pr.setHorizontalHeaderLabels(self._PR_COLS)
        self.table_pr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_pr.horizontalHeader().setStretchLastSection(True)
        pl.addWidget(self.table_pr)
        layout.addWidget(pr_box, 1)

        buttons = QHBoxLayout()
        self.btn_add_hw = QPushButton("Añadir herraje")
        self.btn_add_hw.clicked.connect(lambda: self.table_hw.insertRow(self.table_hw.rowCount()))
        self.btn_save = QPushButton("Guardar catálogo")
        self.btn_save.clicked.connect(self.save)
        buttons.addWidget(self.btn_add_hw)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_save)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        self.table_hw.setRowCount(len(self.catalog.hardware))
        for r, h in enumerate(self.catalog.hardware):
            for c, v in enumerate([h.id, h.name, h.category, f"{h.unit_price:.2f}", f"{h.weight_kg:.3f}", str(h.rivets_per_unit)]):
                self.table_hw.setItem(r, c, QTableWidgetItem(v))
        self.table_pr.setRowCount(len(self.catalog.profiles))
        for r, p in enumerate(self.catalog.profiles):
            for c, v in enumerate([p.id, p.name, p.kind, f"{p.price_per_m:.2f}", f"{p.weight_kg_per_m:.3f}", f"{p.bar_length_mm:.0f}"]):
                self.table_pr.setItem(r, c, QTableWidgetItem(v))

    @staticmethod
    def _cell(table: QTableWidget, r: int, c: int) -> str:
        item = table.item(r, c)
        return item.text().strip() if item else ""

    @staticmethod
    def _num(text: str) -> float:
        return float(text.replace(",", ".")) if text else 0.0

    def read_tables(self) -> None:
        hardware: List[HardwareItem] = []
        for r in range(self.table_hw.rowCount()):
            g = lambda c: self._cell(self.table_hw, r, c)
            if not g(0):
                continue
            hardware.append(HardwareItem(g(0), g(1) or g(0), g(2) or "Varios", self._num(g(3)), self._num(g(4)), int(self._num(g(5)))))
        profiles: List[AluProfileSpec] = []
        for r in range(self.table_pr.rowCount()):
            g = lambda c: self._cell(self.table_pr, r, c)
            if not g(0):
                continue
            profiles.append(AluProfileSpec(g(0), g(1) or g(0), g(2), self._num(g(3)), self._num(g(4)), self._num(g(5)) or 4000.0))
        self.catalog.hardware = hardware
        self.catalog.profiles = profiles

    def save(self, show_message: bool = True) -> None:
        try:
            self.read_tables()
            save_hardware(self.catalog.hardware)
            save_alu_profiles(self.catalog.profiles)
        except ValueError as e:
            QMessageBox.warning(self, "Catálogo", f"Hay un valor numérico no válido:\n{e}")
            return
        self.catalog_changed.emit()
        if show_message:
            QMessageBox.information(self, "Catálogo", "Catálogo guardado.")
