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
    QLineEdit,
    QTabWidget,
    QCheckBox,
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
    Widget managing interior divider walls configuration with dual workflows:
    1. By Compartment Available Spaces (taking wood thickness into account).
    2. By Direct Wall Positions & Coordinates.
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

        # Dual Tab Configuration: Compartment Spaces vs Wall Coordinates
        self.tabs_config = QTabWidget(self)

        # --- Tab 1: By Compartment Available Spaces ---
        self.tab_comps = QWidget()
        tab_comps_layout = QVBoxLayout(self.tab_comps)
        tab_comps_layout.setContentsMargins(4, 4, 4, 4)
        tab_comps_layout.setSpacing(8)

        # Orientation Selector
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Orientation:"))
        self.combo_comp_orient = QComboBox(self)
        self.combo_comp_orient.addItem("Width-wise (Divides Length)", "width_wise")
        self.combo_comp_orient.addItem("Length-wise (Divides Width)", "length_wise")
        self.combo_comp_orient.currentIndexChanged.connect(self._on_comp_orient_changed)
        header_row.addWidget(self.combo_comp_orient)
        header_row.addStretch(1)
        tab_comps_layout.addLayout(header_row)

        self.table_comps = QTableWidget(0, 4, self)
        self.table_comps.setMinimumHeight(220)
        self.table_comps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table_comps.setHorizontalHeaderLabels([
            "Compartment",
            "Auto-Equalize",
            "Available Space (mm)",
            "Wall Thick (mm)",
        ])
        self.table_comps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_comps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_comps.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_comps.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_comps.setColumnWidth(0, 110)
        self.table_comps.setAlternatingRowColors(True)
        tab_comps_layout.addWidget(self.table_comps)

        # Compartment actions
        btn_comp_row = QHBoxLayout()
        btn_comp_add = QPushButton("+ Add Compartment", self)
        btn_comp_add.clicked.connect(self._on_comp_tab_add)
        btn_comp_remove = QPushButton("- Remove Compartment", self)
        btn_comp_remove.clicked.connect(self._on_comp_tab_remove)

        btn_comp_row.addWidget(btn_comp_add)
        btn_comp_row.addWidget(btn_comp_remove)
        tab_comps_layout.addLayout(btn_comp_row)

        self.lbl_comp_summary = QLabel(self)
        tab_comps_layout.addWidget(self.lbl_comp_summary)

        self.tabs_config.addTab(self.tab_comps, "Compartment Spaces")

        # --- Tab 2: By Wall Positions (Direct Coordinates) ---
        self.tab_walls = QWidget()
        tab_walls_layout = QVBoxLayout(self.tab_walls)
        tab_walls_layout.setContentsMargins(4, 4, 4, 4)
        tab_walls_layout.setSpacing(8)

        self.table = QTableWidget(0, 5, self)
        self.table.setMinimumHeight(220)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Wall Label",
            "Orientation",
            "Position (mm)",
            "Thickness (mm)",
            "Height (mm)",
        ])
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 130)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_table_selection_changed())
        self.table.cellClicked.connect(lambda r, c: self._on_cell_clicked(r))
        tab_walls_layout.addWidget(self.table)

        # Wall action buttons
        btn_wall_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Custom Wall", self)
        btn_add.clicked.connect(self._on_add_wall)

        btn_remove = QPushButton("Remove Selected", self)
        btn_remove.setObjectName("secondaryButton")
        btn_remove.clicked.connect(self._on_remove_wall)

        btn_clear = QPushButton("Clear All", self)
        btn_clear.setObjectName("secondaryButton")
        btn_clear.clicked.connect(self._on_clear_walls)

        btn_wall_row.addWidget(btn_add)
        btn_wall_row.addWidget(btn_remove)
        btn_wall_row.addWidget(btn_clear)
        tab_walls_layout.addLayout(btn_wall_row)

        self.tabs_config.addTab(self.tab_walls, "Wall Positions")
        main_layout.addWidget(self.tabs_config)

    def set_case_dimensions(self, inner_length: float, inner_width: float, wood_thickness: float) -> None:
        """Updates internal dimension references from the flightcase domain calculation."""
        self.inner_length = max(10.0, inner_length)
        self.inner_width = max(10.0, inner_width)
        self.wood_thickness = max(1.0, wood_thickness)
        self._refresh_compartment_table()

    def _on_comp_orient_changed(self) -> None:
        self._refresh_compartment_table()

    # --- Compartments Tab Logic ---

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

    def _get_comp_tab_thick_spinbox(self, row: int) -> Optional[QDoubleSpinBox]:
        w = self.table_comps.cellWidget(row, 3)
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
        thicknesses = []
        num_walls = max(0, self.table_comps.rowCount() - 1)
        for r in range(num_walls):
            w = self._get_comp_tab_thick_spinbox(r)
            if w is not None:
                thicknesses.append(w.value())
            else:
                thicknesses.append(self.wood_thickness)
        return thicknesses

    def _auto_equalize_comp_tab_rows(self) -> None:
        num_rows = self.table_comps.rowCount()
        if num_rows == 0:
            return

        orient = self.combo_comp_orient.currentData() or "width_wise"
        span = self.inner_length if orient == "width_wise" else self.inner_width
        thicknesses = self._get_comp_tab_thicknesses()
        total_walls = sum(thicknesses)

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

        clearances = []
        thicknesses = []
        if not active_walls:
            clearances = [span]
        else:
            t0 = active_walls[0].thickness_mm if active_walls[0].thickness_mm > 0 else self.wood_thickness
            clearances.append(max(0.0, active_walls[0].position_mm - (t0 / 2.0)))
            thicknesses.append(t0)

            for i in range(1, len(active_walls)):
                tp = active_walls[i-1].thickness_mm if active_walls[i-1].thickness_mm > 0 else self.wood_thickness
                tc = active_walls[i].thickness_mm if active_walls[i].thickness_mm > 0 else self.wood_thickness
                clearances.append(max(0.0, (active_walls[i].position_mm - tc / 2.0) - (active_walls[i-1].position_mm + tp / 2.0)))
                thicknesses.append(tc)

            t_last = active_walls[-1].thickness_mm if active_walls[-1].thickness_mm > 0 else self.wood_thickness
            clearances.append(max(0.0, span - (active_walls[-1].position_mm + t_last / 2.0)))

        num_comps = len(clearances)
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

            # 3: Wall Thickness
            if row < num_comps - 1:
                t_val = thicknesses[row] if row < len(thicknesses) else self.wood_thickness
                spin_t = QDoubleSpinBox()
                spin_t.setRange(1.0, 50.0)
                spin_t.setDecimals(1)
                spin_t.setValue(round(t_val, 1))
                spin_t.valueChanged.connect(self._on_comp_table_edited)
                self.table_comps.setCellWidget(row, 3, spin_t)
            else:
                it_end = QTableWidgetItem("(End)")
                it_end.setTextAlignment(Qt.AlignCenter)
                it_end.setFlags(it_end.flags() & ~Qt.ItemIsEditable)
                self.table_comps.setItem(row, 3, it_end)

        self._auto_equalize_comp_tab_rows()

        tot_used = sum(clearances) + sum(thicknesses)
        rem = span - tot_used
        self.lbl_comp_summary.setText(
            f"Usable Span: {span:.1f} mm | Used: {tot_used:.1f} mm ({num_comps} comps + {len(thicknesses)} walls) | Rem: {rem:.1f} mm"
        )

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
            thicknesses = self._get_comp_tab_thicknesses()

            orient = self.combo_comp_orient.currentData() or "width_wise"
            span = self.inner_length if orient == "width_wise" else self.inner_width
            num_walls = max(0, len(clearances) - 1)

            new_walls: List[InsideWallDTO] = []
            accum_pos = 0.0
            for i in range(num_walls):
                c_space = clearances[i]
                t_wall = thicknesses[i] if i < len(thicknesses) else self.wood_thickness
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
            self._refresh_table()

            tot_used = sum(clearances) + sum(thicknesses)
            rem = span - tot_used
            self.lbl_comp_summary.setText(
                f"Usable Span: {span:.1f} mm | Used: {tot_used:.1f} mm ({num_comps} comps + {len(thicknesses)} walls) | Rem: {rem:.1f} mm"
            )
        finally:
            self._is_updating = False

        self.walls_changed.emit()
        self.emit_current_selection()

    def _on_comp_tab_add(self) -> None:
        curr_clearances = self._get_comp_tab_clearances()
        curr_thick = self._get_comp_tab_thicknesses()
        curr_flags = self._get_comp_tab_auto_flags()
        curr_clearances.append(100.0)
        curr_thick.append(self.wood_thickness)
        curr_flags.append(False)
        self._rebuild_walls_from_clearances(curr_clearances, curr_thick, curr_flags)

    def _on_comp_tab_remove(self) -> None:
        curr_clearances = self._get_comp_tab_clearances()
        curr_thick = self._get_comp_tab_thicknesses()
        curr_flags = self._get_comp_tab_auto_flags()
        if len(curr_clearances) > 1:
            curr_clearances.pop()
            if curr_thick:
                curr_thick.pop()
            if curr_flags:
                curr_flags.pop()
            self._rebuild_walls_from_clearances(curr_clearances, curr_thick, curr_flags)

    def _rebuild_walls_from_clearances(
        self,
        clearances: List[float],
        thicknesses: List[float],
        auto_flags: Optional[List[bool]] = None,
    ) -> None:
        orient = self.combo_comp_orient.currentData() or "width_wise"
        num_walls = max(0, len(clearances) - 1)
        new_walls: List[InsideWallDTO] = []
        accum_pos = 0.0

        for i in range(num_walls):
            c_space = clearances[i]
            t_wall = thicknesses[i] if i < len(thicknesses) else self.wood_thickness
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
        self._refresh_table()
        self._refresh_compartment_table(auto_flags=auto_flags)
        self.walls_changed.emit()
        self.emit_current_selection()

    # --- Wall Positions Table Logic ---

    def _on_add_wall(self) -> None:
        idx = len(self.walls) + 1
        self.walls.append(InsideWallDTO(
            orientation="width_wise",
            position_mm=100.0 * idx,
            thickness_mm=self.wood_thickness,
            label=f"Wall #{idx}"
        ))
        self._refresh_table()
        self._refresh_compartment_table()
        self.walls_changed.emit()
        self.emit_current_selection()

    def _on_remove_wall(self) -> None:
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if selected_rows:
            for r in selected_rows:
                if 0 <= r < len(self.walls):
                    self.walls.pop(r)
            self._refresh_table()
            self._refresh_compartment_table()
            self.walls_changed.emit()
            self.emit_current_selection()

    def _on_clear_walls(self) -> None:
        self.walls.clear()
        self._refresh_table()
        self._refresh_compartment_table()
        self.walls_changed.emit()
        self.emit_current_selection()

    def _refresh_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.walls))

        for row, wall in enumerate(self.walls):
            # 0: Label
            txt_label = QLineEdit(wall.label)
            txt_label.textChanged.connect(lambda txt, r=row: self._update_wall_label(r, txt))
            self.table.setCellWidget(row, 0, txt_label)

            # 1: Orientation
            combo_orient = QComboBox()
            combo_orient.addItem("Width-wise (Transverse)", "width_wise")
            combo_orient.addItem("Length-wise (Longitudinal)", "length_wise")
            combo_orient.setCurrentIndex(0 if wall.orientation == "width_wise" else 1)
            combo_orient.currentIndexChanged.connect(lambda idx, r=row, cb=combo_orient: self._update_wall_orient(r, cb.currentData()))
            self.table.setCellWidget(row, 1, combo_orient)

            # 2: Position (mm)
            spin_pos = QDoubleSpinBox()
            spin_pos.setRange(1.0, 5000.0)
            spin_pos.setValue(wall.position_mm)
            spin_pos.setDecimals(1)
            spin_pos.valueChanged.connect(lambda val, r=row: self._update_wall_pos(r, val))
            self.table.setCellWidget(row, 2, spin_pos)

            # 3: Thickness (mm)
            spin_thick = QDoubleSpinBox()
            spin_thick.setRange(1.0, 50.0)
            spin_thick.setValue(wall.thickness_mm)
            spin_thick.setDecimals(1)
            spin_thick.valueChanged.connect(lambda val, r=row: self._update_wall_thick(r, val))
            self.table.setCellWidget(row, 3, spin_thick)

            # 4: Height (mm)
            spin_h = QDoubleSpinBox()
            spin_h.setRange(0.0, 5000.0)
            spin_h.setSpecialValueText("Full Height")
            spin_h.setValue(wall.height_mm if wall.height_mm is not None else 0.0)
            spin_h.setDecimals(1)
            spin_h.valueChanged.connect(lambda val, r=row: self._update_wall_height(r, val))
            self.table.setCellWidget(row, 4, spin_h)

        self.table.blockSignals(False)

    def _on_cell_clicked(self, row: int) -> None:
        self.table.selectRow(row)
        self.emit_current_selection()

    def _on_table_selection_changed(self) -> None:
        self.emit_current_selection()

    def emit_current_selection(self) -> None:
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if not selected_rows and self.table.currentRow() >= 0:
            selected_rows = [self.table.currentRow()]
        valid_indices = [r for r in selected_rows if 0 <= r < len(self.walls)]
        valid_labels = [self.walls[r].label for r in valid_indices if self.walls[r].label]
        self.wall_selection_changed.emit(valid_indices, valid_labels)

    def _update_wall_label(self, row: int, label: str) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].label = label
            self.walls_changed.emit()
            self.emit_current_selection()

    def _update_wall_orient(self, row: int, orient: str) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].orientation = orient
            self._refresh_compartment_table()
            self.walls_changed.emit()
            self.emit_current_selection()

    def _update_wall_pos(self, row: int, pos: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].position_mm = pos
            self._refresh_compartment_table()
            self.walls_changed.emit()
            self.emit_current_selection()

    def _update_wall_thick(self, row: int, thick: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].thickness_mm = thick
            self._refresh_compartment_table()
            self.walls_changed.emit()
            self.emit_current_selection()

    def _update_wall_height(self, row: int, height: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].height_mm = height if height > 0 else None
            self.walls_changed.emit()
            self.emit_current_selection()

    def get_walls(self) -> List[InsideWallDTO]:
        return list(self.walls)

    def set_walls(self, walls: List[InsideWallDTO]) -> None:
        self.walls = list(walls)
        self._refresh_table()
        self._refresh_compartment_table()
        self.emit_current_selection()

    def get_compartment_orientation(self) -> str:
        """Returns the current orientation selected in the Compartment Spaces tab."""
        data = self.combo_comp_orient.currentData()
        return str(data) if data else "width_wise"

    def set_compartment_orientation(self, orient: str) -> None:
        """Sets the active orientation in the Compartment Spaces tab and refreshes."""
        idx = self.combo_comp_orient.findData(orient)
        if idx >= 0:
            self.combo_comp_orient.setCurrentIndex(idx)
        elif orient == "length_wise":
            self.combo_comp_orient.setCurrentIndex(1)
        else:
            self.combo_comp_orient.setCurrentIndex(0)

    def get_auto_equalize_flags(self) -> List[bool]:
        """Returns the current auto-equalize checkbox states in the Compartment Spaces tab."""
        return self._get_comp_tab_auto_flags()

    def set_auto_equalize_flags(self, flags: List[bool]) -> None:
        """Applies auto-equalize checkbox states to the Compartment Spaces table."""
        if flags is None:
            return
        self._refresh_compartment_table(auto_flags=flags)
