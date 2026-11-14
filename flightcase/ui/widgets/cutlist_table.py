"""Wood panels dimensions cut list table and material efficiency metrics."""

from __future__ import annotations
from typing import Optional, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QApplication,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
)
from ...application import CalculationResultDTO, CutPieceDTO
from ...i18n import tr


class CutListTableWidget(QWidget):
    """Widget displaying all wood panels cutting dimensions and metrics."""

    piece_selection_changed = Signal(list)  # List of selected panel/piece names
    export_svg_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_result: Optional[CalculationResultDTO] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 1. KPI Summary Cards Frame
        kpi_box = QGroupBox("Resumen de material", self)
        kpi_layout = QGridLayout(kpi_box)

        # Total Area
        kpi_layout.addWidget(QLabel("<b>Superficie total de madera:</b>"), 0, 0)
        self.lbl_total_area = QLabel("0.00 m²")
        kpi_layout.addWidget(self.lbl_total_area, 0, 1)

        # Estimated Weight
        kpi_layout.addWidget(QLabel("<b>Peso estimado:</b>"), 1, 0)
        self.lbl_weight = QLabel("0.0 kg")
        kpi_layout.addWidget(self.lbl_weight, 1, 1)

        # Standard Sheets (2440 x 1220 mm)
        kpi_layout.addWidget(QLabel("<b>Placas estándar (2440x1220):</b>"), 2, 0)
        self.lbl_sheets = QLabel("0.0 placas")
        kpi_layout.addWidget(self.lbl_sheets, 2, 1)

        # Sheet Utilization
        kpi_layout.addWidget(QLabel("<b>Aprovechamiento de placa:</b>"), 3, 0)
        self.lbl_utilization = QLabel("0.0 %")
        kpi_layout.addWidget(self.lbl_utilization, 3, 1)

        # Estimated Wood Cost
        kpi_layout.addWidget(QLabel("<b>Costo estimado de madera:</b>"), 4, 0)
        self.lbl_cost = QLabel("€0.00")
        kpi_layout.addWidget(self.lbl_cost, 4, 1)

        layout.addWidget(kpi_box)

        # 2. Wood Panels Cut List Table
        table_box = QGroupBox("Medidas de corte de los paneles de madera (lista de cortes)", self)
        t_layout = QVBoxLayout(table_box)
        t_layout.setSpacing(8)

        self.table = QTableWidget(0, 8, self)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Panel",
            "Categoría",
            "Cant.",
            "Largo de corte (mm)",
            "Ancho de corte (mm)",
            "Espesor (mm)",
            "Superficie total (m²)",
            "Notas / ubicación",
        ])
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(7, 240)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        t_layout.addWidget(self.table)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("Copiar lista de cortes", self)
        btn_copy.clicked.connect(self._copy_to_clipboard)

        btn_export = QPushButton("Exportar a CSV...", self)
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_csv)

        btn_export_svg = QPushButton("Exportar plano SVG...", self)
        btn_export_svg.setObjectName("secondaryButton")
        btn_export_svg.clicked.connect(self.export_svg_requested.emit)

        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_export_svg)
        btn_layout.addStretch()
        t_layout.addLayout(btn_layout)

        layout.addWidget(table_box)

    def set_calculation_result(self, result: CalculationResultDTO) -> None:
        self.current_result = result

        # Update KPIs
        self.lbl_total_area.setText(f"{result.total_wood_area_m2:.3f} m²")
        self.lbl_weight.setText(f"{result.total_wood_weight_kg:.1f} kg")
        self.lbl_sheets.setText(f"{result.standard_sheets_required:.2f} placas")
        self.lbl_utilization.setText(f"{result.sheet_utilization_pct:.1f} %")
        self.lbl_cost.setText(f"€{result.total_wood_cost:.2f}")

        # Update Table
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setRowCount(len(result.wood_cut_list))
        for row, item in enumerate(result.wood_cut_list):
            self._set_table_row(row, item)
        self.table.blockSignals(False)
        self.emit_current_selection()

    def _on_selection_changed(self) -> None:
        self.emit_current_selection()

    def emit_current_selection(self) -> None:
        if not self.current_result:
            self.piece_selection_changed.emit([])
            return

        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        selected_pieces = [
            self.current_result.wood_cut_list[r].name
            for r in selected_rows
            if 0 <= r < len(self.current_result.wood_cut_list)
        ]
        self.piece_selection_changed.emit(selected_pieces)

    def _set_table_row(self, row: int, item: CutPieceDTO) -> None:
        # 0: Name
        it_name = QTableWidgetItem(tr(item.name))
        it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, it_name)

        # 1: Category
        it_cat = QTableWidgetItem(tr(item.category))
        it_cat.setFlags(it_cat.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, it_cat)

        # 2: Qty
        it_qty = QTableWidgetItem(str(item.quantity))
        it_qty.setTextAlignment(Qt.AlignCenter)
        it_qty.setFlags(it_qty.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, it_qty)

        # 3: Cut Length
        it_len = QTableWidgetItem(f"{item.length_mm:.1f}")
        it_len.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_len.setFlags(it_len.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 3, it_len)

        # 4: Cut Width
        it_w = QTableWidgetItem(f"{item.width_mm:.1f}")
        it_w.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_w.setFlags(it_w.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 4, it_w)

        # 5: Thickness
        it_t = QTableWidgetItem(f"{item.thickness_mm:.1f}")
        it_t.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_t.setFlags(it_t.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 5, it_t)

        # 6: Total Area
        it_area = QTableWidgetItem(f"{item.total_area_m2:.4f}")
        it_area.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_area.setFlags(it_area.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 6, it_area)

        # 7: Notes
        it_notes = QTableWidgetItem(tr(item.notes))
        it_notes.setFlags(it_notes.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 7, it_notes)

    def _copy_to_clipboard(self) -> None:
        if not self.current_result:
            return
        lines = ["Panel\tCategoría\tCant.\tLargo (mm)\tAncho (mm)\tEspesor (mm)\tSuperficie total (m²)\tNotas"]
        for p in self.current_result.wood_cut_list:
            lines.append(f"{tr(p.name)}\t{tr(p.category)}\t{p.quantity}\t{p.length_mm:.1f}\t{p.width_mm:.1f}\t{p.thickness_mm:.1f}\t{p.total_area_m2:.4f}\t{tr(p.notes)}")
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Portapapeles", "Lista de cortes de madera copiada al portapapeles.")

    def _export_csv(self) -> None:
        if not self.current_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar lista de cortes en CSV", "flightcase_lista_cortes_madera.csv", "Archivos CSV (*.csv)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("Panel,Categoría,Cant.,Largo_mm,Ancho_mm,Espesor_mm,SuperficieTotal_m2,Notas\n")
                    for p in self.current_result.wood_cut_list:
                        f.write(f'"{tr(p.name)}","{tr(p.category)}",{p.quantity},{p.length_mm:.1f},{p.width_mm:.1f},{p.thickness_mm:.1f},{p.total_area_m2:.4f},"{tr(p.notes)}"\n')
                QMessageBox.information(self, "Exportación correcta", f"Lista de cortes guardada en:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error de exportación", f"No se pudo guardar el archivo CSV:\n{str(e)}")
