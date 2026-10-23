"""Inside Walls & Partitions Manager Widget with Compartment Space Configuration."""

from __future__ import annotations
from typing import List, Optional
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QGroupBox,
    QAbstractItemView,
)
from ...application import InsideWallDTO


def _create_centered_checkbox(checked: bool = False) -> tuple[QWidget, QCheckBox]:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chk = QCheckBox()
    chk.setChecked(checked)
    layout.addWidget(chk)
    return container, chk


class InsideWallsWidget(QWidget):
    """
    Widget managing interior divider walls configuration by Compartment Available Spaces,
    using the wood material thickness specified in material specifications.
    """

    walls_changed = Signal()
    wall_selection_changed = Signal(list, list)  # (selected_indices, selected_labels)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.walls: List[InsideWallDTO] = []
        self.inner_length = 782.0
        self.inner_width = 482.0
        self.wood_thickness = 9.0
        self._is_updating = False

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        group_box = QGroupBox("Inside Walls & Compartments", self)
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(8, 12, 8, 8)
        group_layout.setSpacing(8)

        # Orientation Selector
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Orientation:"))
        self.combo_comp_orient = QComboBox(self)
        self.combo_comp_orient.addItem("Width-wise (Divides Length)", "width_wise")
        self.combo_comp_orient.addItem("Length-wise (Divides Width)", "length_wise")
        self.combo_comp_orient.currentIndexChanged.connect(self._on_comp_orient_changed)
        header_row.addWidget(self.combo_comp_orient)
        header_row.addStretch(1)
        group_layout.addLayout(header_row)

        # Compartments Table (3 columns: Compartment, Auto-Equalize, Available Space)
        self.table_comps = QTableWidget(0, 3, self)
        self.table_comps.setMinimumHeight(220)
        self.table_comps.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table_comps.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table_comps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table_comps.setHorizontalHeaderLabels([
            "Compartment",
            "Auto-Equalize",
            "Available Space (mm)",
        ])
        self.table_comps.horizontalHeader().setMinimumSectionSize(60)
        self.table_comps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_comps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_comps.setColumnWidth(0, 120)
        self.table_comps.setAlternatingRowColors(True)
        self.table_comps.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_comps.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table_comps.itemSelectionChanged.connect(self.emit_current_selection)
        self.table_comps.currentCellChanged.connect(lambda r, c, pr, pc: self.emit_current_selection())
        self.table_comps.cellClicked.connect(lambda r, c: self._on_cell_clicked(r))
        group_layout.addWidget(self.table_comps)

        # Alias for backwards compatibility
        self.table = self.table_comps

        # Compartment actions
        btn_comp_row = QHBoxLayout()
        btn_comp_add = QPushButton("+ Add Compartment", self)
        btn_comp_add.clicked.connect(self._on_comp_tab_add)
        btn_comp_remove = QPushButton("- Remove Compartment", self)
        btn_comp_remove.clicked.connect(self._on_comp_tab_remove)

        btn_comp_row.addWidget(btn_comp_add)
        btn_comp_row.addWidget(btn_comp_remove)
        group_layout.addLayout(btn_comp_row)

        self.lbl_comp_summary = QLabel(self)
        group_layout.addWidget(self.lbl_comp_summary)

        main_layout.addWidget(group_box)

    def set_case_dimensions(self, inner_length: float, inner_width: float, wood_thickness: float) -> None:
        """Updates internal dimension references and wood thickness from material specifications."""
        self.inner_length = max(10.0, inner_length)
        self.inner_width = max(10.0, inner_width)
        self.wood_thickness = max(1.0, wood_thickness)
        for wall in self.walls:
            wall.thickness_mm = self.wood_thickness
        self._refresh_compartment_table()

    def _on_comp_orient_changed(self) -> None:
        self._refresh_compartment_table()

    # --- Compartments Logic ---

    def _get_comp_tab_auto_checkbox(self, row: int) -> Optional[QCheckBox]:
        w = self.table_comps.cellWidget(row, 1)
        if isinstance(w, QCheckBox):
            return w
        if w:
            return w.findChild(QCheckBox)
        return None

    def _get_comp_tab_space_spinbox(self, row: int) -> Optional[QDoubleSpinBox]:
        w = self.table_comps.cellWidget(row, 2)
        return w if isinstance(w, QDoubleSpinBox) else None

    def _get_comp_tab_auto_flags(self) -> List[bool]:
        flags = []
        for r in range(self.table_comps.rowCount()):
            chk = self._get_comp_tab_auto_checkbox(r)
            flags.append(chk.isChecked() if chk else False)
        return flags

    def _get_comp_tab_clearances(self) -> List[float]:
        clearances = []
        for r in range(self.table_comps.rowCount()):
            w = self._get_comp_tab_space_spinbox(r)
            if w is not None:
                clearances.append(w.value())
            else:
                clearances.append(100.0)
        return clearances if clearances else [100.0]

    def _get_comp_tab_thicknesses(self) -> List[float]:
        num_walls = max(0, self.table_comps.rowCount() - 1)
        return [self.wood_thickness] * num_walls

    def _auto_equalize_comp_tab_rows(self) -> None:
        num_rows = self.table_comps.rowCount()
        if num_rows == 0:
            return

        orient = self.combo_comp_orient.currentData() or "width_wise"
        span = self.inner_length if orient == "width_wise" else self.inner_width
        num_walls = max(0, num_rows - 1)
        total_walls = num_walls * self.wood_thickness

        checked_rows = []
        unchecked_space_sum = 0.0

        for r in range(num_rows):
            chk = self._get_comp_tab_auto_checkbox(r)
            is_checked = chk.isChecked() if chk else False
            spin = self._get_comp_tab_space_spinbox(r)
            if is_checked:
                checked_rows.append(r)
                if spin:
                    spin.setEnabled(False)
            else:
                if spin:
                    spin.setEnabled(True)
                    unchecked_space_sum += spin.value()

        if checked_rows:
            remaining = max(0.0, span - total_walls - unchecked_space_sum)
            each_space = round(remaining / len(checked_rows), 1)
            for r in checked_rows:
                spin = self._get_comp_tab_space_spinbox(r)
                if spin:
                    spin.blockSignals(True)
                    spin.setValue(each_space)
                    spin.blockSignals(False)

    def _refresh_compartment_table(self, auto_flags: Optional[List[bool]] = None) -> None:
        if self._is_updating:
            return

        self._is_updating = True
        self.table_comps.blockSignals(True)

        if auto_flags is None:
            auto_flags = self._get_comp_tab_auto_flags()

        orient = self.combo_comp_orient.currentData() or "width_wise"
        active_walls = [w for w in self.walls if w.orientation == orient]
        active_walls.sort(key=lambda w: w.position_mm)
        span = self.inner_length if orient == "width_wise" else self.inner_width
        t_wall = self.wood_thickness

        clearances = []
        if not active_walls:
            clearances = [span]
        else:
            clearances.append(max(0.0, active_walls[0].position_mm - (t_wall / 2.0)))

            for i in range(1, len(active_walls)):
                clearances.append(max(0.0, (active_walls[i].position_mm - t_wall / 2.0) - (active_walls[i-1].position_mm + t_wall / 2.0)))

            clearances.append(max(0.0, span - (active_walls[-1].position_mm + t_wall / 2.0)))

        num_comps = len(clearances)
        num_walls = max(0, num_comps - 1)
        self.table_comps.setRowCount(num_comps)

        for row, c_val in enumerate(clearances):
            # 0: Name
            it_name = QTableWidgetItem(f"Compartment {row + 1}")
            it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
            self.table_comps.setItem(row, 0, it_name)

            # 1: Auto-Equalize
            is_auto = bool(auto_flags[row]) if auto_flags and row < len(auto_flags) else False
            chk_container, chk = _create_centered_checkbox(is_auto)
            chk.toggled.connect(lambda _: self._on_comp_table_edited())
            self.table_comps.setCellWidget(row, 1, chk_container)

            # 2: Available Space
            spin_c = QDoubleSpinBox()
            spin_c.setRange(0.0, 5000.0)
            spin_c.setDecimals(1)
            spin_c.setValue(round(c_val, 1))
            spin_c.setEnabled(not is_auto)
            spin_c.valueChanged.connect(self._on_comp_table_edited)
            self.table_comps.setCellWidget(row, 2, spin_c)

        self._auto_equalize_comp_tab_rows()
        self.table_comps.blockSignals(False)
        self._is_updating = False

    def _on_comp_table_edited(self) -> None:
        if self._is_updating:
            return

        self._is_updating = True
        try:
            self._auto_equalize_comp_tab_rows()

            num_comps = self.table_comps.rowCount()
            if num_comps <= 0:
                return

            clearances = self._get_comp_tab_clearances()
            orient = self.combo_comp_orient.currentData() or "width_wise"
            span = self.inner_length if orient == "width_wise" else self.inner_width
            num_walls = max(0, len(clearances) - 1)
            t_wall = self.wood_thickness

            new_walls: List[InsideWallDTO] = []
            accum_pos = 0.0
            for i in range(num_walls):
                c_space = clearances[i]
                pos = accum_pos + c_space + (t_wall / 2.0)
                accum_pos = pos + (t_wall / 2.0)

                lbl_prefix = "Width" if orient == "width_wise" else "Length"
                new_walls.append(InsideWallDTO(
                    orientation=orient,
                    position_mm=round(pos, 1),
                    thickness_mm=round(t_wall, 1),
                    label=f"{lbl_prefix} Wall #{i + 1}"
                ))

            # Keep walls of other orientation
            other_walls = [w for w in self.walls if w.orientation != orient]
            self.walls = other_walls + new_walls

        finally:
            self._is_updating = False

        self.walls_changed.emit()
        self.emit_current_selection()

    def _on_comp_tab_add(self) -> None:
        curr_clearances = self._get_comp_tab_clearances()
        curr_flags = self._get_comp_tab_auto_flags()
        orient = self.combo_comp_orient.currentData() or "width_wise"
        span = self.inner_length if orient == "width_wise" else self.inner_width
        num_walls = len(curr_clearances)
        t_wall = self.wood_thickness
        avail_space = max(10.0, span - num_walls * t_wall)

        new_comps = len(curr_clearances) + 1
        curr_flags.append(False)

        if any(curr_flags):
            curr_clearances.append(100.0)
        else:
            each_space = round(avail_space / new_comps, 1)
            curr_clearances = [each_space] * new_comps

        self._rebuild_walls_from_clearances(curr_clearances, auto_flags=curr_flags)

    def _on_comp_tab_remove(self) -> None:
        curr_clearances = self._get_comp_tab_clearances()
        curr_flags = self._get_comp_tab_auto_flags()
        if len(curr_clearances) > 1:
            curr_clearances.pop()
            if curr_flags:
                curr_flags.pop()
            orient = self.combo_comp_orient.currentData() or "width_wise"
            span = self.inner_length if orient == "width_wise" else self.inner_width
            num_walls = len(curr_clearances) - 1
            t_wall = self.wood_thickness
            avail_space = max(10.0, span - num_walls * t_wall)
            if not any(curr_flags):
                each_space = round(avail_space / len(curr_clearances), 1)
                curr_clearances = [each_space] * len(curr_clearances)
            self._rebuild_walls_from_clearances(curr_clearances, auto_flags=curr_flags)

    def _rebuild_walls_from_clearances(
        self,
        clearances: List[float],
        thicknesses: Optional[List[float]] = None,
        auto_flags: Optional[List[bool]] = None,
    ) -> None:
        orient = self.combo_comp_orient.currentData() or "width_wise"
        num_walls = max(0, len(clearances) - 1)
        new_walls: List[InsideWallDTO] = []
        accum_pos = 0.0
        t_wall = self.wood_thickness

        for i in range(num_walls):
            c_space = clearances[i]
            pos = accum_pos + c_space + (t_wall / 2.0)
            accum_pos = pos + (t_wall / 2.0)

            lbl_prefix = "Width" if orient == "width_wise" else "Length"
            new_walls.append(InsideWallDTO(
                orientation=orient,
                position_mm=round(pos, 1),
                thickness_mm=round(t_wall, 1),
                label=f"{lbl_prefix} Wall #{i + 1}"
            ))

        other_walls = [w for w in self.walls if w.orientation != orient]
        self.walls = other_walls + new_walls
        self._refresh_compartment_table(auto_flags=auto_flags)
        self.walls_changed.emit()
        self.emit_current_selection()

    def _on_add_wall(self) -> None:
        self._on_comp_tab_add()

    def _on_remove_wall(self) -> None:
        self._on_comp_tab_remove()

    def _on_clear_walls(self) -> None:
        self.walls.clear()
        self._refresh_compartment_table()
        self.walls_changed.emit()
        self.emit_current_selection()

    def _on_cell_clicked(self, row: int) -> None:
        self.table_comps.selectRow(row)
        self.emit_current_selection()

    def emit_current_selection(self) -> None:
        selected_rows = sorted(set(idx.row() for idx in self.table_comps.selectedIndexes()))
        if not selected_rows and self.table_comps.currentRow() >= 0:
            selected_rows = [self.table_comps.currentRow()]
        valid_indices = []
        for r in selected_rows:
            if 0 <= r < len(self.walls):
                valid_indices.append(r)
            elif r >= len(self.walls) and len(self.walls) > 0:
                valid_indices.append(len(self.walls) - 1)
        valid_indices = sorted(list(set(valid_indices)))
        valid_labels = [self.walls[r].label for r in valid_indices if self.walls[r].label]
        self.wall_selection_changed.emit(valid_indices, valid_labels)

    def get_walls(self) -> List[InsideWallDTO]:
        return list(self.walls)

    def set_walls(self, walls: List[InsideWallDTO]) -> None:
        self.walls = list(walls)
        for w in self.walls:
            if w.thickness_mm <= 0:
                w.thickness_mm = self.wood_thickness
        self._refresh_compartment_table()
        self.emit_current_selection()

    def get_compartment_orientation(self) -> str:
        """Returns the current orientation selected in the Compartment Spaces manager."""
        data = self.combo_comp_orient.currentData()
        return str(data) if data else "width_wise"

    def set_compartment_orientation(self, orient: str) -> None:
        """Sets the active orientation in the Compartment Spaces manager and refreshes."""
        idx = self.combo_comp_orient.findData(orient)
        if idx >= 0:
            self.combo_comp_orient.setCurrentIndex(idx)
        elif orient == "length_wise":
            self.combo_comp_orient.setCurrentIndex(1)
        else:
            self.combo_comp_orient.setCurrentIndex(0)

    def get_auto_equalize_flags(self) -> List[bool]:
        """Returns the current auto-equalize checkbox states in the Compartment Spaces table."""
        return self._get_comp_tab_auto_flags()

    def set_auto_equalize_flags(self, flags: List[bool]) -> None:
        """Applies auto-equalize checkbox states to the Compartment Spaces table."""
        if flags is None:
            return
        self._refresh_compartment_table(auto_flags=flags)
