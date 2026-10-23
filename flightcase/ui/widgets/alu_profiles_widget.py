"""Aluminum profiles required length and internal compartments analysis widget."""

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
    QMessageBox, QAbstractItemView,
)
from ...application import CalculationResultDTO, CutPieceDTO


class AluProfilesWidget(QWidget):
    """Widget displaying required aluminum profile lengths, breakdown, and compartments."""

    profile_selection_changed = Signal(list)  # List of selected profile names

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_result: Optional[CalculationResultDTO] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 1. Prominently Highlighted KPI Cards for Aluminum Profiles
        kpi_box = QGroupBox("Alu Profile Lengths", self)
        kpi_layout = QGridLayout(kpi_box)

        # Highlighted Lid Mating Profile Length
        kpi_layout.addWidget(QLabel("<b>Lid Alu Length:</b>"), 0, 0)
        self.lbl_lid_profile_len = QLabel("0.0 mm (0.00 m)")
        kpi_layout.addWidget(self.lbl_lid_profile_len, 0, 1)

        # Edge Angle Protection Profiles Length
        kpi_layout.addWidget(QLabel("<b>Edge Protection:</b>"), 1, 0)
        self.lbl_edge_profile_len = QLabel("0.0 mm (0.00 m)")
        kpi_layout.addWidget(self.lbl_edge_profile_len, 1, 1)

        layout.addWidget(kpi_box)

        # 2. Detailed Profiles Cut List Table
        table_box = QGroupBox("Aluminum Extrusion Cut List", self)
        t_layout = QVBoxLayout(table_box)
        t_layout.setSpacing(8)

        self.table_profiles = QTableWidget(0, 6, self)
        self.table_profiles.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table_profiles.setHorizontalHeaderLabels([
            "Profile Description",
            "Category",
            "Qty",
            "Cut Length (mm)",
            "Total Length (m)",
            "Mounting Location / Notes",
        ])
        self.table_profiles.horizontalHeader().setMinimumSectionSize(60)
        self.table_profiles.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_profiles.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_profiles.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_profiles.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_profiles.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_profiles.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.table_profiles.setColumnWidth(0, 180)
        self.table_profiles.setColumnWidth(5, 240)
        self.table_profiles.setAlternatingRowColors(True)
        self.table_profiles.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_profiles.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table_profiles.itemSelectionChanged.connect(self._on_selection_changed)
        t_layout.addWidget(self.table_profiles)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy Profiles to Clipboard", self)
        btn_copy.clicked.connect(self._copy_profiles_clipboard)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        t_layout.addLayout(btn_row)

        layout.addWidget(table_box)

        # 3. Internal Compartments Analysis Table
        comp_box = QGroupBox("Calculated Internal Compartments Breakdown", self)
        c_layout = QVBoxLayout(comp_box)
        c_layout.setSpacing(8)

        self.table_comps = QTableWidget(0, 5, self)
        self.table_comps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table_comps.setHorizontalHeaderLabels([
            "Compartment Name",
            "Usable Length (mm)",
            "Usable Width (mm)",
            "Usable Height (mm)",
            "Volume (Liters)",
        ])
        self.table_comps.horizontalHeader().setMinimumSectionSize(60)
        self.table_comps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_comps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.setColumnWidth(0, 180)
        self.table_comps.setAlternatingRowColors(True)
        c_layout.addWidget(self.table_comps)

        layout.addWidget(comp_box)

    def set_calculation_result(self, result: CalculationResultDTO) -> None:
        self.current_result = result

        # 1. Update KPI Highlights
        lid_m = result.total_lid_mating_profile_length_mm / 1000.0
        edge_m = result.total_edge_angle_profile_length_mm / 1000.0
        self.lbl_lid_profile_len.setText(
            f"{result.total_lid_mating_profile_length_mm:.1f} mm ({lid_m:.2f} m)"
        )
        self.lbl_edge_profile_len.setText(
            f"{result.total_edge_angle_profile_length_mm:.1f} mm ({edge_m:.2f} m)"
        )

        # 2. Update Profiles Table
        self.table_profiles.blockSignals(True)
        self.table_profiles.setRowCount(len(result.alu_profiles_list))
        for row, item in enumerate(result.alu_profiles_list):
            it_name = QTableWidgetItem(item.name)
            it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 0, it_name)

            it_cat = QTableWidgetItem(item.category)
            it_cat.setFlags(it_cat.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 1, it_cat)

            it_qty = QTableWidgetItem(str(item.quantity))
            it_qty.setTextAlignment(Qt.AlignCenter)
            it_qty.setFlags(it_qty.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 2, it_qty)

            it_len = QTableWidgetItem(f"{item.length_mm:.1f}")
            it_len.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_len.setFlags(it_len.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 3, it_len)

            it_tot_m = QTableWidgetItem(f"{item.total_length_m:.2f}")
            it_tot_m.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot_m.setFlags(it_tot_m.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 4, it_tot_m)

            it_notes = QTableWidgetItem(item.notes)
            it_notes.setFlags(it_notes.flags() & ~Qt.ItemIsEditable)
            self.table_profiles.setItem(row, 5, it_notes)
        self.table_profiles.blockSignals(False)
        self.emit_current_selection()

        # 3. Update Compartments Table
        self.table_comps.setRowCount(len(result.compartments))
        for row, comp in enumerate(result.compartments):
            it_cname = QTableWidgetItem(comp.name)
            it_cname.setFlags(it_cname.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 0, it_cname)

            it_cl = QTableWidgetItem(f"{comp.length_mm:.1f}")
            it_cl.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_cl.setFlags(it_cl.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 1, it_cl)

            it_cw = QTableWidgetItem(f"{comp.width_mm:.1f}")
            it_cw.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_cw.setFlags(it_cw.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 2, it_cw)

            it_ch = QTableWidgetItem(f"{comp.height_mm:.1f}")
            it_ch.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_ch.setFlags(it_ch.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 3, it_ch)

            it_vol = QTableWidgetItem(f"{comp.volume_liters:.2f} L")
            it_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_vol.setFlags(it_vol.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 4, it_vol)

    def _on_selection_changed(self) -> None:
        self.emit_current_selection()

    def emit_current_selection(self) -> None:
        if not self.current_result:
            self.profile_selection_changed.emit([])
            return

        selected_rows = sorted(set(idx.row() for idx in self.table_profiles.selectedIndexes()))
        selected_profiles = [
            self.current_result.alu_profiles_list[r].name
            for r in selected_rows
            if 0 <= r < len(self.current_result.alu_profiles_list)
        ]
        self.profile_selection_changed.emit(selected_profiles)

    def _copy_profiles_clipboard(self) -> None:
        if not self.current_result:
            return
        lines = [
            f"Lid Alu Profile Total Length: {self.current_result.total_lid_mating_profile_length_mm:.1f} mm ({self.current_result.total_lid_mating_profile_length_mm/1000.0:.2f} m)",
            f"Edge Angle Profiles Total Length: {self.current_result.total_edge_angle_profile_length_mm:.1f} mm ({self.current_result.total_edge_angle_profile_length_mm/1000.0:.2f} m)",
            "",
            "Profile Description\tCategory\tQty\tCut Length (mm)\tTotal Length (m)\tNotes"
        ]
        for p in self.current_result.alu_profiles_list:
            lines.append(f"{p.name}\t{p.category}\t{p.quantity}\t{p.length_mm:.1f}\t{p.total_length_m:.2f}\t{p.notes}")
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Clipboard", "Aluminum profiles cut list copied to clipboard.")
