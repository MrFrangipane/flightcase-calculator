"""Input panel widget for case dimensions, wood materials, thickness, density, price, and lid aluminum profile offset."""

from __future__ import annotations
from typing import Optional, List
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
)
from ...domain import load_wood_materials, WoodMaterial
from ...application import CaseInputDTO


class CaseInputPanel(QWidget):
    """Form panel for entering flightcase parameters."""

    input_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._wood_materials: List[WoodMaterial] = load_wood_materials()
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # 0. Project Title
        title_box = QGroupBox("Project Title", self)
        title_layout = QVBoxLayout(title_box)
        self.edit_title = QLineEdit(self)
        self.edit_title.setPlaceholderText("Project Title (e.g. Stage Rack 4U)...")
        self.edit_title.textChanged.connect(self._on_value_changed)
        title_layout.addWidget(self.edit_title)
        main_layout.addWidget(title_box)

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

        # 3. Wood Material & Profile Specifications Box
        spec_box = QGroupBox("Material & Extrusion Specifications", self)
        spec_layout = QGridLayout(spec_box)
        spec_layout.setSpacing(8)

        # Wood Material Selection Combo
        spec_layout.addWidget(QLabel("Wood material:"), 0, 0)
        self.combo_wood_material = QComboBox(self)
        for mat in self._wood_materials:
            self.combo_wood_material.addItem(mat.name, mat.id)
        self.combo_wood_material.addItem("Custom", "custom")
        self.combo_wood_material.currentIndexChanged.connect(self._on_material_selected)
        spec_layout.addWidget(self.combo_wood_material, 0, 1)

        # Wood Thickness
        spec_layout.addWidget(QLabel("Thickness:"), 1, 0)
        self.spin_wood_thickness = QDoubleSpinBox(self)
        self.spin_wood_thickness.setRange(1.0, 50.0)
        self.spin_wood_thickness.setValue(9.0)
        self.spin_wood_thickness.setSuffix(" mm")
        self.spin_wood_thickness.setDecimals(1)
        self.spin_wood_thickness.setReadOnly(True)
        self.spin_wood_thickness.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_wood_thickness, 1, 1)

        # Wood Density
        spec_layout.addWidget(QLabel("Density:"), 2, 0)
        self.spin_wood_density = QDoubleSpinBox(self)
        self.spin_wood_density.setRange(0.0, 5000.0)
        self.spin_wood_density.setValue(700.0)
        self.spin_wood_density.setSuffix(" kg/m³")
        self.spin_wood_density.setDecimals(1)
        self.spin_wood_density.setReadOnly(True)
        self.spin_wood_density.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_wood_density, 2, 1)

        # Wood Price
        spec_layout.addWidget(QLabel("Price:"), 3, 0)
        self.spin_wood_price = QDoubleSpinBox(self)
        self.spin_wood_price.setRange(0.0, 5000.0)
        self.spin_wood_price.setValue(18.50)
        self.spin_wood_price.setPrefix("€")
        self.spin_wood_price.setSuffix(" / m²")
        self.spin_wood_price.setDecimals(2)
        self.spin_wood_price.setReadOnly(True)
        self.spin_wood_price.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_wood_price, 3, 1)

        # Initialize defaults from default material if available
        if self._wood_materials:
            default_mat = self._wood_materials[0]
            self.spin_wood_thickness.setValue(default_mat.thickness_mm)
            self.spin_wood_density.setValue(default_mat.density_kg_m3)
            self.spin_wood_price.setValue(default_mat.price_per_m2)

        # Lid Aluminum Profile Added Dimension (to be subtracted from height)
        lbl_profile_offset = QLabel("Lid Profile Added Dim (-H):")
        lbl_profile_offset.setToolTip("Aluminum hybrid location profile added dimension subtracted from wood panel height")
        spec_layout.addWidget(lbl_profile_offset, 4, 0)
        self.spin_profile_offset = QDoubleSpinBox(self)
        self.spin_profile_offset.setRange(0.0, 100.0)
        self.spin_profile_offset.setValue(10.0)
        self.spin_profile_offset.setSuffix(" mm")
        self.spin_profile_offset.setDecimals(1)
        self.spin_profile_offset.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_profile_offset, 4, 1)

        # Edge Profile Width (e.g. 30x30mm)
        spec_layout.addWidget(QLabel("Edge Angle Width:"), 5, 0)
        self.spin_edge_width = QDoubleSpinBox(self)
        self.spin_edge_width.setRange(10.0, 100.0)
        self.spin_edge_width.setValue(30.0)
        self.spin_edge_width.setSuffix(" mm")
        self.spin_edge_width.setDecimals(1)
        self.spin_edge_width.valueChanged.connect(self._on_value_changed)
        spec_layout.addWidget(self.spin_edge_width, 5, 1)

        # Self-Cut Lid (6-wall uncut box) Checkbox
        self.chk_self_cut_lid = QCheckBox("Cut lid yourself (6-wall uncut box)", self)
        self.chk_self_cut_lid.setToolTip("Calculate wood cut list for a 6-sided uncut closed box to be sawn open by the builder")
        self.chk_self_cut_lid.toggled.connect(self._on_value_changed)
        spec_layout.addWidget(self.chk_self_cut_lid, 6, 0, 1, 2)

        main_layout.addWidget(spec_box)
        main_layout.addStretch()

    def _on_value_changed(self) -> None:
        self.input_changed.emit()

    def _on_material_selected(self, index: int) -> None:
        selected_text = self.combo_wood_material.currentText()
        if selected_text == "Custom" or index < 0 or index >= len(self._wood_materials):
            self.spin_wood_thickness.setReadOnly(False)
            self.spin_wood_density.setReadOnly(False)
            self.spin_wood_price.setReadOnly(False)
        else:
            mat = self._wood_materials[index]
            self.spin_wood_thickness.blockSignals(True)
            self.spin_wood_density.blockSignals(True)
            self.spin_wood_price.blockSignals(True)

            self.spin_wood_thickness.setValue(mat.thickness_mm)
            self.spin_wood_density.setValue(mat.density_kg_m3)
            self.spin_wood_price.setValue(mat.price_per_m2)

            self.spin_wood_thickness.blockSignals(False)
            self.spin_wood_density.blockSignals(False)
            self.spin_wood_price.blockSignals(False)

            self.spin_wood_thickness.setReadOnly(True)
            self.spin_wood_density.setReadOnly(True)
            self.spin_wood_price.setReadOnly(True)

        self._on_value_changed()

    def set_self_cut_lid(self, value: bool) -> None:
        self.chk_self_cut_lid.setChecked(value)

    def set_wood_materials(self, materials: List[WoodMaterial]) -> None:
        """Updates the list of available wood materials and refreshes the combo box."""
        current_data = self.combo_wood_material.currentData()
        current_text = self.combo_wood_material.currentText()
        self._wood_materials = list(materials)

        self.combo_wood_material.blockSignals(True)
        self.combo_wood_material.clear()
        for mat in self._wood_materials:
            self.combo_wood_material.addItem(mat.name, mat.id)
        self.combo_wood_material.addItem("Custom", "custom")

        # Try to restore selection by ID, then name
        matched_idx = -1
        if current_data == "custom" or current_text == "Custom":
            matched_idx = self.combo_wood_material.count() - 1
        elif current_data:
            for i, mat in enumerate(self._wood_materials):
                if mat.id == current_data:
                    matched_idx = i
                    break
        if matched_idx < 0 and current_text:
            for i, mat in enumerate(self._wood_materials):
                if mat.name.lower() == current_text.lower():
                    matched_idx = i
                    break

        if matched_idx >= 0 and matched_idx < len(self._wood_materials):
            self.combo_wood_material.setCurrentIndex(matched_idx)
            mat = self._wood_materials[matched_idx]
            self.spin_wood_thickness.blockSignals(True)
            self.spin_wood_density.blockSignals(True)
            self.spin_wood_price.blockSignals(True)

            self.spin_wood_thickness.setValue(mat.thickness_mm)
            self.spin_wood_density.setValue(mat.density_kg_m3)
            self.spin_wood_price.setValue(mat.price_per_m2)

            self.spin_wood_thickness.blockSignals(False)
            self.spin_wood_density.blockSignals(False)
            self.spin_wood_price.blockSignals(False)

            self.spin_wood_thickness.setReadOnly(True)
            self.spin_wood_density.setReadOnly(True)
            self.spin_wood_price.setReadOnly(True)
        elif matched_idx == len(self._wood_materials):  # Custom
            self.combo_wood_material.setCurrentIndex(matched_idx)
            self.spin_wood_thickness.setReadOnly(False)
            self.spin_wood_density.setReadOnly(False)
            self.spin_wood_price.setReadOnly(False)
        else:
            if self._wood_materials:
                self.combo_wood_material.setCurrentIndex(0)
                mat = self._wood_materials[0]
                self.spin_wood_thickness.blockSignals(True)
                self.spin_wood_density.blockSignals(True)
                self.spin_wood_price.blockSignals(True)

                self.spin_wood_thickness.setValue(mat.thickness_mm)
                self.spin_wood_density.setValue(mat.density_kg_m3)
                self.spin_wood_price.setValue(mat.price_per_m2)

                self.spin_wood_thickness.blockSignals(False)
                self.spin_wood_density.blockSignals(False)
                self.spin_wood_price.blockSignals(False)

                self.spin_wood_thickness.setReadOnly(True)
                self.spin_wood_density.setReadOnly(True)
                self.spin_wood_price.setReadOnly(True)
            else:
                self.combo_wood_material.setCurrentIndex(self.combo_wood_material.count() - 1)
                self.spin_wood_thickness.setReadOnly(False)
                self.spin_wood_density.setReadOnly(False)
                self.spin_wood_price.setReadOnly(False)

        self.combo_wood_material.blockSignals(False)
        self.input_changed.emit()

    def set_input_dto(self, dto: CaseInputDTO) -> None:
        """Sets all input field values from a CaseInputDTO."""
        self.edit_title.blockSignals(True)
        self.spin_length.blockSignals(True)
        self.spin_width.blockSignals(True)
        self.spin_total_height.blockSignals(True)
        self.spin_lid_height.blockSignals(True)
        self.combo_wood_material.blockSignals(True)
        self.spin_wood_thickness.blockSignals(True)
        self.spin_wood_density.blockSignals(True)
        self.spin_wood_price.blockSignals(True)
        self.spin_profile_offset.blockSignals(True)
        self.spin_edge_width.blockSignals(True)
        self.chk_self_cut_lid.blockSignals(True)

        self.edit_title.setText(dto.title or "")
        self.spin_length.setValue(dto.inner_length)
        self.spin_width.setValue(dto.inner_width)
        self.spin_total_height.setValue(dto.inner_total_height)
        self.spin_lid_height.setValue(dto.inner_lid_height)

        # Match material name or properties
        target_name = (dto.wood_material or "").strip()
        matched_idx = -1
        for i, m in enumerate(self._wood_materials):
            if m.name.lower() == target_name.lower():
                matched_idx = i
                break

        if matched_idx < 0 and target_name and target_name.lower() != "custom":
            for i, m in enumerate(self._wood_materials):
                if (
                    abs(m.thickness_mm - dto.wood_thickness) < 1e-3
                    and abs(m.density_kg_m3 - dto.wood_density) < 1e-2
                    and abs(m.price_per_m2 - dto.wood_price) < 1e-2
                ):
                    matched_idx = i
                    break

        if matched_idx >= 0:
            self.combo_wood_material.setCurrentIndex(matched_idx)
            mat = self._wood_materials[matched_idx]
            self.spin_wood_thickness.setValue(mat.thickness_mm)
            self.spin_wood_density.setValue(mat.density_kg_m3)
            self.spin_wood_price.setValue(mat.price_per_m2)
            self.spin_wood_thickness.setReadOnly(True)
            self.spin_wood_density.setReadOnly(True)
            self.spin_wood_price.setReadOnly(True)
        else:
            self.combo_wood_material.setCurrentText("Custom")
            self.spin_wood_thickness.setValue(dto.wood_thickness)
            self.spin_wood_density.setValue(dto.wood_density)
            self.spin_wood_price.setValue(dto.wood_price)
            self.spin_wood_thickness.setReadOnly(False)
            self.spin_wood_density.setReadOnly(False)
            self.spin_wood_price.setReadOnly(False)

        self.spin_profile_offset.setValue(dto.lid_alu_profile_offset)
        self.spin_edge_width.setValue(dto.edge_profile_width)
        self.chk_self_cut_lid.setChecked(dto.self_cut_lid)

        self.edit_title.blockSignals(False)
        self.spin_length.blockSignals(False)
        self.spin_width.blockSignals(False)
        self.spin_total_height.blockSignals(False)
        self.spin_lid_height.blockSignals(False)
        self.combo_wood_material.blockSignals(False)
        self.spin_wood_thickness.blockSignals(False)
        self.spin_wood_density.blockSignals(False)
        self.spin_wood_price.blockSignals(False)
        self.spin_profile_offset.blockSignals(False)
        self.spin_edge_width.blockSignals(False)
        self.chk_self_cut_lid.blockSignals(False)

        self.input_changed.emit()

    def get_input_dto(self) -> CaseInputDTO:
        return CaseInputDTO(
            title=self.edit_title.text().strip(),
            inner_length=self.spin_length.value(),
            inner_width=self.spin_width.value(),
            inner_total_height=self.spin_total_height.value(),
            inner_lid_height=self.spin_lid_height.value(),
            wood_thickness=self.spin_wood_thickness.value(),
            wood_material=self.combo_wood_material.currentText(),
            wood_density=self.spin_wood_density.value(),
            wood_price=self.spin_wood_price.value(),
            lid_alu_profile_offset=self.spin_profile_offset.value(),
            edge_profile_width=self.spin_edge_width.value(),
            self_cut_lid=self.chk_self_cut_lid.isChecked(),
        )
