"""Main PySide6 Application Window for Flightcase Calculator."""

from __future__ import annotations
import sys
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QStatusBar,
    QMessageBox,
    QFileDialog,
)

from ..domain.exceptions import FlightCaseDomainError
from ..application import (
    CaseInputDTO,
    CalculateFlightCaseUseCase,
    GenerateSchema3DUseCase,
    CalculationResultDTO,
)
from .theme import DARK_THEME_QSS
from .widgets import (
    CaseInputPanel,
    InsideWallsWidget,
    Schema3DWidget,
    CutListTableWidget,
    AluProfilesWidget,
)


class FlightCaseMainWindow(QMainWindow):
    """Main window coordinating inputs, domain calculations, 3D schema, and cut lists."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Flightcase Calculator — DDD (PySide6)")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._current_result: Optional[CalculationResultDTO] = None

        self._init_ui()
        self._init_menus()
        self._connect_signals()

        # Initial calculation
        self.recalculate()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Main horizontal splitter
        splitter = QSplitter(Qt.Horizontal, self)

        # 1. Left Pane: Input Tabs
        left_tabs = QTabWidget(self)
        self.input_panel = CaseInputPanel(self)
        self.walls_widget = InsideWallsWidget(self)

        left_tabs.addTab(self.input_panel, "1. Dimensions & Specs")
        left_tabs.addTab(self.walls_widget, "2. Inside Walls / Partitions")
        splitter.addWidget(left_tabs)

        # 2. Right Pane: Output Tabs
        self.right_tabs = QTabWidget(self)
        self.schema_widget = Schema3DWidget(self)
        self.cutlist_widget = CutListTableWidget(self)
        self.alu_widget = AluProfilesWidget(self)

        self.right_tabs.addTab(self.schema_widget, "📐 3D Schema & Dimensions")
        self.right_tabs.addTab(self.cutlist_widget, "🪵 Wood Panels Dimensions")
        self.right_tabs.addTab(self.alu_widget, "🔩 Lid Alu Profile Lengths")
        splitter.addWidget(self.right_tabs)

        # Set splitter proportions (38% left, 62% right)
        splitter.setStretchFactor(0, 38)
        splitter.setStretchFactor(1, 62)

        main_layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. All domain invariants verified.")

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")

        export_action = QAction("&Export Full Cut List...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_full_report)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu_bar.addMenu("&View")
        reset_view_action = QAction("&Reset 3D Schema View", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.triggered.connect(lambda: self.schema_widget.canvas.reset_view(45.0, 30.0))
        view_menu.addAction(reset_view_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About Flightcase Calculator", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self) -> None:
        self.input_panel.input_changed.connect(self.recalculate)
        self.walls_widget.walls_changed.connect(self.recalculate)
        self.schema_widget.lid_exploded_changed.connect(self._update_schema_geometry)
        self.schema_widget.toggles_changed.connect(self._update_schema_geometry)

    def recalculate(self) -> None:
        """Executes application use cases to update all outputs live."""
        input_dto = self.input_panel.get_input_dto()
        input_dto.walls = self.walls_widget.get_walls()

        try:
            # 1. Calculate flightcase
            result = CalculateFlightCaseUseCase.execute(input_dto)
            self._current_result = result

            # 2. Update UI widgets
            self.cutlist_widget.set_calculation_result(result)
            self.alu_widget.set_calculation_result(result)
            self._update_schema_geometry()

            # 3. Status Bar
            lid_m = result.total_lid_mating_profile_length_mm / 1000.0
            self.status_bar.showMessage(
                f"✓ Outer: {input_dto.outer_length:.0f}×{input_dto.outer_width:.0f}×{input_dto.total_height:.0f} mm | "
                f"Inner: {result.inner_length:.0f}×{result.inner_width:.0f}×{result.inner_base_height:.0f} mm | "
                f"Lid Alu Profile Required Length: {result.total_lid_mating_profile_length_mm:.1f} mm ({lid_m:.2f} m) | "
                f"Wood Panels: {len(result.wood_cut_list)} pieces ({result.total_wood_area_m2:.2f} m²)"
            )
        except FlightCaseDomainError as e:
            self.status_bar.showMessage(f"⚠ Domain Validation Error: {str(e)}")
        except Exception as e:
            self.status_bar.showMessage(f"⚠ Error: {str(e)}")

    def _update_schema_geometry(self) -> None:
        input_dto = self.input_panel.get_input_dto()
        input_dto.walls = self.walls_widget.get_walls()

        try:
            mesh = GenerateSchema3DUseCase.execute(
                input_dto=input_dto,
                lid_exploded_gap_mm=self.schema_widget.exploded_gap_mm,
                show_inside_walls=self.schema_widget.show_inside_walls,
                show_dimensions=self.schema_widget.show_dimensions,
            )
            self.schema_widget.set_mesh(mesh)
        except FlightCaseDomainError:
            pass

    def _export_full_report(self) -> None:
        if not self._current_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Flightcase BOM", "flightcase_calculation_bom.csv", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("=== FLIGHTCASE CALCULATION REPORT ===\n\n")
                    f.write(f"Total Wood Area (m2),{self._current_result.total_wood_area_m2:.4f}\n")
                    f.write(f"Estimated Wood Weight (kg),{self._current_result.total_wood_weight_kg:.2f}\n")
                    f.write(f"Standard Sheets (2440x1220),{self._current_result.standard_sheets_required:.2f}\n")
                    f.write(f"Lid Alu Profile Required Length (mm),{self._current_result.total_lid_mating_profile_length_mm:.1f}\n")
                    f.write(f"Edge Angle Profiles Required Length (mm),{self._current_result.total_edge_angle_profile_length_mm:.1f}\n\n")

                    f.write("=== WOOD PANELS CUT LIST ===\n")
                    f.write("Panel Description,Category,Qty,Length_mm,Width_mm,Thickness_mm,TotalArea_m2,Notes\n")
                    for p in self._current_result.wood_cut_list:
                        f.write(f'"{p.name}","{p.category}",{p.quantity},{p.length_mm:.1f},{p.width_mm:.1f},{p.thickness_mm:.1f},{p.total_area_m2:.4f},"{p.notes}"\n')

                    f.write("\n=== ALUMINUM PROFILES CUT LIST ===\n")
                    f.write("Profile Description,Category,Qty,CutLength_mm,TotalLength_m,Notes\n")
                    for p in self._current_result.alu_profiles_list:
                        f.write(f'"{p.name}","{p.category}",{p.quantity},{p.length_mm:.1f},{p.total_length_m:.2f},"{p.notes}"\n')

                QMessageBox.information(self, "Export Successful", f"Full report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save CSV file:\n{str(e)}")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Flightcase Calculator",
            "<h3>Flightcase Calculator</h3>"
            "<p>A Python / PySide6 application built following <b>Domain-Driven Design (DDD)</b> principles.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>No-perspective parallel 3D wireframe schema with exact dimensions</li>"
            "<li>Wood panels cutting dimensions and BOM cut list</li>"
            "<li>Lid aluminum profile required lengths & edge protection angles</li>"
            "<li>Inside partition walls manager (equispaced and custom)</li>"
            "<li>Material efficiency & standard sheet estimates</li>"
            "</ul>"
        )


def run_app() -> int:
    """Entry point to start the PySide6 Qt Application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyleSheet(DARK_THEME_QSS)
    window = FlightCaseMainWindow()
    window.show()
    return app.exec()
