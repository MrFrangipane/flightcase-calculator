"""Inside Walls & Partitions Manager Widget."""

from __future__ import annotations
from typing import List, Optional
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
)
from ...application import InsideWallDTO


class InsideWallsWidget(QWidget):
    """Widget managing interior divider walls configuration and equispaced generation."""

    walls_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.walls: List[InsideWallDTO] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # 1. Quick Equispaced Divider Generator
        gen_box = QGroupBox("Quick Equispaced Walls Generator", self)
        gen_layout = QGridLayout(gen_box)
        gen_layout.setSpacing(8)

        gen_layout.addWidget(QLabel("Number of Walls:"), 0, 0)
        self.spin_count = QSpinBox(self)
        self.spin_count.setRange(1, 20)
        self.spin_count.setValue(2)
        gen_layout.addWidget(self.spin_count, 0, 1)

        gen_layout.addWidget(QLabel("Orientation:"), 0, 2)
        self.combo_gen_orient = QComboBox(self)
        self.combo_gen_orient.addItem("Width-wise (Transverse, ⟂ Length)", "width_wise")
        self.combo_gen_orient.addItem("Length-wise (Longitudinal, ⟂ Width)", "length_wise")
        gen_layout.addWidget(self.combo_gen_orient, 0, 3)

        btn_generate = QPushButton("Generate Equispaced", self)
        btn_generate.clicked.connect(self._on_generate_equispaced)
        gen_layout.addWidget(btn_generate, 1, 0, 1, 4)

        main_layout.addWidget(gen_box)

        # 2. Inside Walls Table
        table_box = QGroupBox("Partition Walls Configuration", self)
        table_layout = QVBoxLayout(table_box)
        table_layout.setSpacing(8)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            "Wall Label",
            "Orientation",
            "Position (mm)",
            "Thickness (mm)",
            "Height (mm)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Custom Wall", self)
        btn_add.clicked.connect(self._on_add_wall)

        btn_remove = QPushButton("Remove Selected", self)
        btn_remove.setObjectName("secondaryButton")
        btn_remove.clicked.connect(self._on_remove_wall)

        btn_clear = QPushButton("Clear All", self)
        btn_clear.setObjectName("secondaryButton")
        btn_clear.clicked.connect(self._on_clear_walls)

        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_clear)
        table_layout.addLayout(btn_row)

        main_layout.addWidget(table_box)

    def _on_generate_equispaced(self) -> None:
        count = self.spin_count.value()
        orient = self.combo_gen_orient.currentData()
        
        # We will clear existing and generate equispaced with approximate positions
        # Let's say default case length 782, we emit signal or generate proportional walls
        self.walls.clear()
        # Positions will be populated based on case dimensions in controller or estimated
        # We store placeholder relative step which will be synced
        for i in range(1, count + 1):
            lbl = f"{'Width' if orient == 'width_wise' else 'Length'} Wall #{i}"
            # Initial estimate: 200 * i
            self.walls.append(InsideWallDTO(
                orientation=orient,
                position_mm=150.0 * i,
                thickness_mm=9.0,
                label=lbl
            ))
        self._refresh_table()
        self.walls_changed.emit()

    def set_equispaced_from_span(self, count: int, orientation_str: str, span_mm: float, thickness_mm: float = 9.0) -> None:
        self.walls.clear()
        if count > 0 and span_mm > 0:
            step = span_mm / (count + 1)
            for i in range(1, count + 1):
                lbl = f"{'Width' if orientation_str == 'width_wise' else 'Length'} Wall #{i}"
                self.walls.append(InsideWallDTO(
                    orientation=orientation_str,
                    position_mm=round(step * i, 1),
                    thickness_mm=thickness_mm,
                    label=lbl
                ))
        self._refresh_table()
        self.walls_changed.emit()

    def _on_add_wall(self) -> None:
        idx = len(self.walls) + 1
        self.walls.append(InsideWallDTO(
            orientation="width_wise",
            position_mm=100.0 * idx,
            thickness_mm=9.0,
            label=f"Wall #{idx}"
        ))
        self._refresh_table()
        self.walls_changed.emit()

    def _on_remove_wall(self) -> None:
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if selected_rows:
            for r in selected_rows:
                if 0 <= r < len(self.walls):
                    self.walls.pop(r)
            self._refresh_table()
            self.walls_changed.emit()

    def _on_clear_walls(self) -> None:
        self.walls.clear()
        self._refresh_table()
        self.walls_changed.emit()

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

    def _update_wall_label(self, row: int, label: str) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].label = label
            self.walls_changed.emit()

    def _update_wall_orient(self, row: int, orient: str) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].orientation = orient
            self.walls_changed.emit()

    def _update_wall_pos(self, row: int, pos: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].position_mm = pos
            self.walls_changed.emit()

    def _update_wall_thick(self, row: int, thick: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].thickness_mm = thick
            self.walls_changed.emit()

    def _update_wall_height(self, row: int, height: float) -> None:
        if 0 <= row < len(self.walls):
            self.walls[row].height_mm = height if height > 0 else None
            self.walls_changed.emit()

    def get_walls(self) -> List[InsideWallDTO]:
        return list(self.walls)

    def set_walls(self, walls: List[InsideWallDTO]) -> None:
        self.walls = list(walls)
        self._refresh_table()
