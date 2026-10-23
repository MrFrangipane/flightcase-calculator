"""Wood types and material specifications management and editing widget."""

from __future__ import annotations
import csv
import io
from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QApplication,
    QMessageBox,
    QAbstractItemView,
)
from ...domain import WoodMaterial, load_wood_materials, save_wood_materials


class WoodTypesWidget(QWidget):
    """Widget allowing users to view, add, edit, delete, reorder, and save wood material types."""

    materials_changed = Signal(list)  # List[WoodMaterial]
    materials_saved = Signal(list)    # List[WoodMaterial]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_updating = False
        self._init_ui()
        self.load_materials()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        group_box = QGroupBox("Wood Types & Material Specifications", self)
        g_layout = QVBoxLayout(group_box)
        g_layout.setContentsMargins(8, 12, 8, 8)
        g_layout.setSpacing(8)

        # Instruction note
        lbl_hint = QLabel(
            "Double-click any cell to edit properties. Changes automatically update the material presets.",
            self,
        )
        lbl_hint.setStyleSheet("color: #888888; font-size: 11px;")
        g_layout.addWidget(lbl_hint)

        # Materials Table
        self.table = QTableWidget(0, 5, self)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Name",
            "Thickness (mm)",
            "Density (kg/m³)",
            "Price (€/m²)",
        ])

        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 220)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        g_layout.addWidget(self.table)

        # Action Buttons Row 1: Add, Remove, Move Up, Move Down
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(6)

        self.btn_add = QPushButton("+ Add Wood Type", self)
        self.btn_add.setToolTip("Add a new wood material specification")
        self.btn_add.clicked.connect(self._on_add_material)
        btn_row1.addWidget(self.btn_add)

        self.btn_delete = QPushButton("- Delete Selected", self)
        self.btn_delete.setToolTip("Remove selected wood material(s)")
        self.btn_delete.clicked.connect(self._on_delete_material)
        btn_row1.addWidget(self.btn_delete)

        self.btn_move_up = QPushButton("▲ Move Up", self)
        self.btn_move_up.setToolTip("Move selected wood type up in the list")
        self.btn_move_up.clicked.connect(self._on_move_up)
        btn_row1.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("▼ Move Down", self)
        self.btn_move_down.setToolTip("Move selected wood type down in the list")
        self.btn_move_down.clicked.connect(self._on_move_down)
        btn_row1.addWidget(self.btn_move_down)

        btn_row1.addStretch(1)
        g_layout.addLayout(btn_row1)

        # Action Buttons Row 2: Save to File, Reload, Copy to Clipboard
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(6)

        self.btn_save = QPushButton("Save to File", self)
        self.btn_save.setToolTip("Save wood materials to resources/wood_types.json")
        self.btn_save.clicked.connect(self._on_save_materials)
        btn_row2.addWidget(self.btn_save)

        self.btn_reload = QPushButton("Reload from File", self)
        self.btn_reload.setToolTip("Reload wood materials from disk, discarding unsaved edits")
        self.btn_reload.clicked.connect(self._on_reload_materials)
        btn_row2.addWidget(self.btn_reload)

        self.btn_copy = QPushButton("Copy to Clipboard", self)
        self.btn_copy.setToolTip("Copy wood types table to clipboard as TSV")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_row2.addWidget(self.btn_copy)

        btn_row2.addStretch(1)
        g_layout.addLayout(btn_row2)

        # Status Label
        self.lbl_status = QLabel(self)
        self.lbl_status.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        g_layout.addWidget(self.lbl_status)

        layout.addWidget(group_box)

    def load_materials(self, materials: Optional[List[WoodMaterial]] = None) -> None:
        """Loads and displays wood materials in the table."""
        if materials is None:
            materials = load_wood_materials()
        self.set_materials(materials)

    def set_materials(self, materials: List[WoodMaterial]) -> None:
        """Populates the table with given WoodMaterial objects."""
        self._is_updating = True
        self.table.blockSignals(True)

        self.table.setRowCount(len(materials))
        for row, mat in enumerate(materials):
            self._set_row_items(row, mat)

        self.table.blockSignals(False)
        self._is_updating = False
        self.lbl_status.setText(f"{len(materials)} wood types loaded.")

    def _set_row_items(self, row: int, mat: WoodMaterial) -> None:
        """Helper to create and configure table items for a single material row."""
        item_id = QTableWidgetItem(mat.id)
        item_name = QTableWidgetItem(mat.name)
        item_thick = QTableWidgetItem(f"{mat.thickness_mm:.1f}")
        item_thick.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_density = QTableWidgetItem(f"{mat.density_kg_m3:.1f}")
        item_density.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_price = QTableWidgetItem(f"{mat.price_per_m2:.2f}")
        item_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.table.setItem(row, 0, item_id)
        self.table.setItem(row, 1, item_name)
        self.table.setItem(row, 2, item_thick)
        self.table.setItem(row, 3, item_density)
        self.table.setItem(row, 4, item_price)

    def get_materials(self) -> List[WoodMaterial]:
        """Parses current table rows into a list of WoodMaterial objects."""
        materials: List[WoodMaterial] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            thick_item = self.table.item(row, 2)
            density_item = self.table.item(row, 3)
            price_item = self.table.item(row, 4)

            name = name_item.text().strip() if name_item else ""
            mat_id = id_item.text().strip() if id_item else ""

            # Fallback for empty names / IDs
            if not name:
                name = f"Material {row + 1}"
            if not mat_id:
                mat_id = name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")

            try:
                raw_thick = thick_item.text().strip().replace(",", ".") if thick_item else "9.0"
                thickness = max(0.1, float(raw_thick))
            except ValueError:
                thickness = 9.0

            try:
                raw_density = density_item.text().strip().replace(",", ".") if density_item else "500.0"
                density = max(0.0, float(raw_density))
            except ValueError:
                density = 500.0

            try:
                raw_price = price_item.text().strip().replace("€", "").replace("$", "").replace(",", ".").strip() if price_item else "0.0"
                price = max(0.0, float(raw_price))
            except ValueError:
                price = 0.0

            materials.append(
                WoodMaterial(
                    name=name,
                    thickness_mm=thickness,
                    density_kg_m3=density,
                    price_per_m2=price,
                    id=mat_id,
                )
            )
        return materials

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handles cell edit events, normalizes inputs, and notifies listeners."""
        if self._is_updating:
            return

        row = item.row()
        col = item.column()

        # Sanitize numeric columns and auto-populate ID if empty
        self._is_updating = True
        self.table.blockSignals(True)

        if col == 1:  # Name edited
            id_item = self.table.item(row, 0)
            if id_item and not id_item.text().strip():
                new_id = item.text().strip().lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                id_item.setText(new_id)
        elif col == 2:  # Thickness
            try:
                val = max(0.1, float(item.text().strip().replace(",", ".")))
                item.setText(f"{val:.1f}")
            except ValueError:
                item.setText("9.0")
        elif col == 3:  # Density
            try:
                val = max(0.0, float(item.text().strip().replace(",", ".")))
                item.setText(f"{val:.1f}")
            except ValueError:
                item.setText("500.0")
        elif col == 4:  # Price
            try:
                val = max(0.0, float(item.text().strip().replace("€", "").replace("$", "").replace(",", ".").strip()))
                item.setText(f"{val:.2f}")
            except ValueError:
                item.setText("0.00")

        self.table.blockSignals(False)
        self._is_updating = False

        mats = self.get_materials()
        self.lbl_status.setText(f"Modified material '{mats[row].name}' (unsaved changes in session).")
        self.materials_changed.emit(mats)

    def _on_add_material(self) -> None:
        """Appends a new wood material row to the table."""
        count = self.table.rowCount()
        new_mat = WoodMaterial(
            name=f"Custom Wood {count + 1}",
            thickness_mm=9.0,
            density_kg_m3=500.0,
            price_per_m2=20.00,
            id=f"custom_wood_{count + 1}",
        )

        self._is_updating = True
        self.table.blockSignals(True)
        self.table.insertRow(count)
        self._set_row_items(count, new_mat)
        self.table.blockSignals(False)
        self._is_updating = False

        self.table.selectRow(count)
        self.table.scrollToItem(self.table.item(count, 1))

        mats = self.get_materials()
        self.lbl_status.setText(f"Added new material '{new_mat.name}'.")
        self.materials_changed.emit(mats)

    def _on_delete_material(self) -> None:
        """Deletes selected rows from the table."""
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return

        self._is_updating = True
        self.table.blockSignals(True)
        for r in selected_rows:
            self.table.removeRow(r)
        self.table.blockSignals(False)
        self._is_updating = False

        mats = self.get_materials()
        self.lbl_status.setText(f"Removed {len(selected_rows)} wood type(s).")
        self.materials_changed.emit(mats)

    def _on_move_up(self) -> None:
        """Moves selected row one position up."""
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not selected_rows or selected_rows[0] == 0:
            return

        target_row = selected_rows[0] - 1
        mats = self.get_materials()
        mats[target_row], mats[selected_rows[0]] = mats[selected_rows[0]], mats[target_row]
        self.set_materials(mats)
        self.table.selectRow(target_row)
        self.materials_changed.emit(mats)

    def _on_move_down(self) -> None:
        """Moves selected row one position down."""
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not selected_rows or selected_rows[-1] >= self.table.rowCount() - 1:
            return

        target_row = selected_rows[-1] + 1
        mats = self.get_materials()
        mats[target_row], mats[selected_rows[-1]] = mats[selected_rows[-1]], mats[target_row]
        self.set_materials(mats)
        self.table.selectRow(target_row)
        self.materials_changed.emit(mats)

    def _on_save_materials(self) -> None:
        """Persists current wood materials to the JSON file on disk."""
        mats = self.get_materials()
        try:
            save_wood_materials(mats)
            self.lbl_status.setText(f"Successfully saved {len(mats)} wood types to disk.")
            self.materials_saved.emit(mats)
            self.materials_changed.emit(mats)
        except Exception as e:
            QMessageBox.critical(self, "Save Wood Types Error", f"Failed to save wood types:\n{str(e)}")

    def _on_reload_materials(self) -> None:
        """Reloads wood materials from disk, discarding in-memory edits."""
        self.load_materials()
        mats = self.get_materials()
        self.lbl_status.setText(f"Reloaded {len(mats)} wood types from disk.")
        self.materials_changed.emit(mats)

    def _copy_to_clipboard(self) -> None:
        """Exports wood types table to clipboard as TSV format."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t")
        headers = ["ID", "Name", "Thickness (mm)", "Density (kg/m3)", "Price (EUR/m2)"]
        writer.writerow(headers)

        for mat in self.get_materials():
            writer.writerow([mat.id, mat.name, mat.thickness_mm, mat.density_kg_m3, mat.price_per_m2])

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(output.getvalue())
            self.lbl_status.setText("Wood types copied to clipboard.")
