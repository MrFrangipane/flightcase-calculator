"""Input panel widget for case dimensions, wood thickness, and lid aluminum profile offset."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
)
from ...application import CaseInputDTO


class CaseInputPanel(QWidget):
    """Form panel for entering flightcase parameters."""

    input_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # 1. Preset Selector
        preset_box = QGroupBox("Preset Configurations", self)
        preset_layout = QHBoxLayout(preset_box)
        self.combo_presets = QComboBox(self)
        self.combo_presets.addItems([
            "Standard Road Trunk (800 x 500 x 400 mm, Lid 100mm)",
            "Large Production Case (1200 x 600 x 600 mm, Lid 150mm)",
            "Compact Tool / Mic Case (600 x 400 x 300 mm, Lid 80mm)",
            "Cable Trunk (1000 x 500 x 500 mm, Lid 120mm)",
            "Custom Dimensions",
        ])
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.combo_presets)
        main_layout.addWidget(preset_box)

        # 2. Case Inner Dimensions Box
        dim_box = QGroupBox("Inner Case Dimensions", self)
        dim_layout = QGridLayout(dim_box)
        dim_layout.setSpacing(8)

        # Length
        dim_layout.addWidget(QLabel("Inner Length (L):"), 0, 0)
        self.spin_length = QDoubleSpinBox(self)
        self.spin_length.setRange(100.0, 5000.0)
        self.spin_length.setValue(800.0)
        self.spin_length.setSuffix(" mm")
        self.spin_length.setDecimals(1)
        self.spin_length.valueChanged.connect(self._on_value_changed)
        dim_layout.addWidget(self.spin_length, 0, 1)

        # Width
        dim_layout.addWidget(QLabel("Inner Width (W):"), 1, 0)
        self.spin_width = QDoubleSpinBox(self)
        self.spin_width.setRange(100.0, 5000.0)
        self.spin_width.setValue(500.0)
        self.spin_width.setSuffix(" mm")
        self.spin_width.setDecimals(1)
        self.spin_width.valueChanged.connect(self._on_value_changed)
        dim_layout.addWidget(self.spin_width, 1, 1)

        # Total Height
        dim_layout.addWidget(QLabel("Inner Height (H):"), 2, 0)
        self.spin_total_height = QDoubleSpinBox(self)
        self.spin_total_height.setRange(100.0, 5000.0)
        self.spin_total_height.setValue(400.0)
        self.spin_total_height.setSuffix(" mm")
        self.spin_total_height.setDecimals(1)
        self.spin_total_height.valueChanged.connect(self._on_value_changed)
        dim_layout.addWidget(self.spin_total_height, 2, 1)

        # Lid Height
        dim_layout.addWidget(QLabel("Inner Lid Height (H_lid):"), 3, 0)
        self.spin_lid_height = QDoubleSpinBox(self)
        self.spin_lid_height.setRange(20.0, 2000.0)
        self.spin_lid_height.setValue(100.0)
        self.spin_lid_height.setSuffix(" mm")
        self.spin_lid_height.setDecimals(1)
        self.spin_lid_height.valueChanged.connect(self._on_value_changed)
        dim_layout.addWidget(self.spin_lid_height, 3, 1)

        main_layout.addWidget(dim_box)

        # 3. Wood & Profile Specifications Box
        spec_box = QGroupBox("Material & Extrusion Specifications", self)
        spec_layout = QGridLayout(spec_box)
        spec_layout.setSpacing(8)

        # Wood Panel Thickness
        spec_layout.addWidget(QLabel("Wood Panels Thickness:"), 0, 0)
        self.spin_wood_thickness = QDoubleSpinBox(self)
        self.spin_wood_thickness.setRange(4.0, 30.0)
        self.spin_wood_thickness.setValue(9.0)
        self.spin_wood_thickness.setSuffix(" mm")
        self.spin_wood_thickness.setDecimals(1)
        self.spin_wood_thickness.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_wood_thickness, 0, 1)

        # Lid Aluminum Profile Added Dimension (to be subtracted from height)
        lbl_profile_offset = QLabel("Lid Profile Added Dim (-H):")
        lbl_profile_offset.setToolTip("Aluminum hybrid location profile added dimension subtracted from wood panel height")
        spec_layout.addWidget(lbl_profile_offset, 1, 0)
        self.spin_profile_offset = QDoubleSpinBox(self)
        self.spin_profile_offset.setRange(0.0, 100.0)
        self.spin_profile_offset.setValue(10.0)
        self.spin_profile_offset.setSuffix(" mm")
        self.spin_profile_offset.setDecimals(1)
        self.spin_profile_offset.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_profile_offset, 1, 1)

        # Edge Profile Width (e.g. 30x30mm)
        spec_layout.addWidget(QLabel("Edge Angle Width:"), 2, 0)
        self.spin_edge_width = QDoubleSpinBox(self)
        self.spin_edge_width.setRange(10.0, 100.0)
        self.spin_edge_width.setValue(30.0)
        self.spin_edge_width.setSuffix(" mm")
        self.spin_edge_width.setDecimals(1)
        self.spin_edge_width.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_edge_width, 2, 1)

        # Self-Cut Lid (6-wall uncut box) Checkbox
        self.chk_self_cut_lid = QCheckBox("Cut lid yourself (6-wall uncut box)", self)
        self.chk_self_cut_lid.setToolTip("Calculate wood cut list for a 6-sided uncut closed box to be sawn open by the builder")
        self.chk_self_cut_lid.toggled.connect(self._on_value_changed)
        spec_layout.addWidget(self.chk_self_cut_lid, 3, 0, 1, 2)

        main_layout.addWidget(spec_box)
        main_layout.addStretch()

    def _on_value_changed(self) -> None:
        self.input_changed.emit()

    def _on_preset_selected(self, index: int) -> None:
        presets = [
            (800.0, 500.0, 400.0, 100.0, 9.0, 10.0),
            (1200.0, 600.0, 600.0, 150.0, 9.0, 12.0),
            (600.0, 400.0, 300.0, 80.0, 6.5, 10.0),
            (1000.0, 500.0, 500.0, 120.0, 9.0, 10.0),
        ]
        if 0 <= index < len(presets):
            l, w, h, lid_h, t_wood, p_off = presets[index]
            self.spin_length.blockSignals(True)
            self.spin_width.blockSignals(True)
            self.spin_total_height.blockSignals(True)
            self.spin_lid_height.blockSignals(True)
            self.spin_wood_thickness.blockSignals(True)
            self.spin_profile_offset.blockSignals(True)

            self.spin_length.setValue(l)
            self.spin_width.setValue(w)
            self.spin_total_height.setValue(h)
            self.spin_lid_height.setValue(lid_h)
            self.spin_wood_thickness.setValue(t_wood)
            self.spin_profile_offset.setValue(p_off)

            self.spin_length.blockSignals(False)
            self.spin_width.blockSignals(False)
            self.spin_total_height.blockSignals(False)
            self.spin_lid_height.blockSignals(False)
            self.spin_wood_thickness.blockSignals(False)
            self.spin_profile_offset.blockSignals(False)

            self.input_changed.emit()

    def set_self_cut_lid(self, value: bool) -> None:
        self.chk_self_cut_lid.setChecked(value)

    def set_input_dto(self, dto: CaseInputDTO) -> None:
        """Sets all input field values from a CaseInputDTO."""
        self.spin_length.blockSignals(True)
        self.spin_width.blockSignals(True)
        self.spin_total_height.blockSignals(True)
        self.spin_lid_height.blockSignals(True)
        self.spin_wood_thickness.blockSignals(True)
        self.spin_profile_offset.blockSignals(True)
        self.spin_edge_width.blockSignals(True)
        self.chk_self_cut_lid.blockSignals(True)

        self.spin_length.setValue(dto.inner_length)
        self.spin_width.setValue(dto.inner_width)
        self.spin_total_height.setValue(dto.inner_total_height)
        self.spin_lid_height.setValue(dto.inner_lid_height)
        self.spin_wood_thickness.setValue(dto.wood_thickness)
        self.spin_profile_offset.setValue(dto.lid_alu_profile_offset)
        self.spin_edge_width.setValue(dto.edge_profile_width)
        self.chk_self_cut_lid.setChecked(dto.self_cut_lid)

        self.spin_length.blockSignals(False)
        self.spin_width.blockSignals(False)
        self.spin_total_height.blockSignals(False)
        self.spin_lid_height.blockSignals(False)
        self.spin_wood_thickness.blockSignals(False)
        self.spin_profile_offset.blockSignals(False)
        self.spin_edge_width.blockSignals(False)
        self.chk_self_cut_lid.blockSignals(False)

        self.input_changed.emit()

    def get_input_dto(self) -> CaseInputDTO:
        return CaseInputDTO(
            inner_length=self.spin_length.value(),
            inner_width=self.spin_width.value(),
            inner_total_height=self.spin_total_height.value(),
            inner_lid_height=self.spin_lid_height.value(),
            wood_thickness=self.spin_wood_thickness.value(),
            lid_alu_profile_offset=self.spin_profile_offset.value(),
            edge_profile_width=self.spin_edge_width.value(),
            self_cut_lid=self.chk_self_cut_lid.isChecked(),
        )
