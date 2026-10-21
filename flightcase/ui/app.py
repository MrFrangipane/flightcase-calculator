"""Main PySide6 Application Window for Flightcase Calculator."""

from __future__ import annotations
import sys
import os
from typing import Optional, List
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QAction, QCloseEvent, QSurfaceFormat
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
    QScrollArea,
    QFrame,
)

from ..domain.exceptions import FlightCaseDomainError
from ..application import (
    CaseInputDTO,
    UISettingsDTO,
    CalculateFlightCaseUseCase,
    GenerateSchema3DUseCase,
    SaveProjectUseCase,
    LoadProjectUseCase,
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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        restore_settings: bool = True,
        load_last_project: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle("Flightcase Calculator — Untitled")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._current_result: Optional[CalculationResultDTO] = None
        self._current_project_path: Optional[str] = None

        self._init_ui()
        self._init_menus()
        self._connect_signals()

        # Restore window geometry and splitter state
        if restore_settings:
            self._restore_settings()

        # Load last project or perform initial calculation
        if load_last_project:
            self._load_startup_project()
        else:
            self.recalculate()
            self._update_window_title()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Main horizontal splitter with 3 sections:
        # [ Left: Output Tables | Center: 3D Viewport | Right: Dimensions & Inside Walls Config ]
        self.main_splitter = QSplitter(Qt.Horizontal, self)

        # 1. Left Pane: Tabs containing dimensions / cutlist output tables
        self.tabs = QTabWidget(self)
        self.cutlist_widget = CutListTableWidget(self)
        self.alu_widget = AluProfilesWidget(self)

        self.tabs.addTab(self.cutlist_widget, "Wood Cut List")
        self.tabs.addTab(self.alu_widget, "Alu Profiles")
        self.main_splitter.addWidget(self.tabs)

        # 2. Center Pane: 3D Viewport (always visible)
        self.schema_widget = Schema3DWidget(self)
        self.main_splitter.addWidget(self.schema_widget)

        # 3. Right Pane: Permanent Configuration Panel (Dimensions & Specs + Inside Walls)
        self.input_panel = CaseInputPanel(self)
        self.walls_widget = InsideWallsWidget(self)

        self.config_scroll = QScrollArea(self)
        self.config_scroll.setWidgetResizable(True)
        self.config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.config_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.config_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.config_container = QWidget()
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(12)
        config_layout.addWidget(self.input_panel)
        config_layout.addWidget(self.walls_widget)
        config_layout.addStretch(1)

        self.config_scroll.setWidget(self.config_container)
        self.main_splitter.addWidget(self.config_scroll)

        # Set splitter proportions (32% left output tables, 44% center 3D schema, 24% right config panel)
        self.main_splitter.setStretchFactor(0, 32)
        self.main_splitter.setStretchFactor(1, 44)
        self.main_splitter.setStretchFactor(2, 24)

        main_layout.addWidget(self.main_splitter)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. All domain invariants verified.")

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()

        # File Menu
        self.file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut("Ctrl+N")
        new_action.setStatusTip("Create a new flightcase project")
        new_action.triggered.connect(self._new_project)
        self.file_menu.addAction(new_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Open an existing flightcase project file")
        open_action.triggered.connect(self._open_project)
        self.file_menu.addAction(open_action)

        save_action = QAction("&Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("Save the current flightcase project")
        save_action.triggered.connect(self._save_project)
        self.file_menu.addAction(save_action)

        save_as_action = QAction("Save Project &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.setStatusTip("Save the flightcase project to a new file")
        save_as_action.triggered.connect(self._save_project_as)
        self.file_menu.addAction(save_as_action)

        # Open Recent Section (up to 5 recent files, directly in the menu, no submenu)
        self.recent_section_action = self.file_menu.addSection("Open Recent")
        self.recent_file_actions: List[QAction] = []
        for _ in range(5):
            act = QAction(self)
            act.setVisible(False)
            self.file_menu.addAction(act)
            self.recent_file_actions.append(act)

        self._update_recent_files_menu()

        self.file_menu.addSeparator()

        export_action = QAction("&Export Full Cut List...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip("Export comprehensive Bill of Materials to CSV")
        export_action.triggered.connect(self._export_full_report)
        self.file_menu.addAction(export_action)

        self.file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit Flightcase Calculator")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

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

    def _get_recent_files(self) -> List[str]:
        """Returns the list of up to 5 recently opened/saved project file paths."""
        settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
        raw = settings.value("recentProjects", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        elif not isinstance(raw, list):
            raw = []

        seen = set()
        valid: List[str] = []
        for p in raw:
            if isinstance(p, str) and p and p not in seen:
                seen.add(p)
                if os.path.isfile(p):
                    valid.append(p)
        return valid[:5]

    def _add_recent_file(self, file_path: str) -> None:
        """Adds a project file path to the recent files list and refreshes the menu."""
        if not file_path:
            return
        abs_path = os.path.abspath(file_path)
        recent = self._get_recent_files()
        if abs_path in recent:
            recent.remove(abs_path)
        recent.insert(0, abs_path)
        recent = recent[:5]

        settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
        settings.setValue("recentProjects", recent)
        self._update_recent_files_menu()

    def _update_recent_files_menu(self) -> None:
        """Updates the 5 recent file actions directly in the File menu (no submenu)."""
        if not hasattr(self, "recent_file_actions"):
            return

        recent_files = self._get_recent_files()
        if not recent_files:
            if hasattr(self, "recent_section_action"):
                self.recent_section_action.setVisible(False)
            for act in self.recent_file_actions:
                act.setVisible(False)
            return

        if hasattr(self, "recent_section_action"):
            self.recent_section_action.setVisible(True)

        for i in range(5):
            act = self.recent_file_actions[i]
            if i < len(recent_files):
                file_path = recent_files[i]
                file_name = os.path.basename(file_path)
                act.setText(f"&{i + 1} {file_name}")
                act.setStatusTip(file_path)
                act.setToolTip(file_path)
                try:
                    act.triggered.disconnect()
                except Exception:
                    pass
                act.triggered.connect(lambda checked=False, p=file_path: self._load_project_file(p))
                act.setEnabled(True)
                act.setVisible(True)
            else:
                act.setVisible(False)

    def _get_current_ui_settings(self) -> UISettingsDTO:
        """Gathers active UI settings including 3D camera transform, toggles, active tab, and compartment settings."""
        ui_dto = self.schema_widget.get_ui_settings()
        ui_dto.active_tab_index = self.tabs.currentIndex()
        ui_dto.compartment_orientation = self.walls_widget.get_compartment_orientation()
        ui_dto.auto_equalize_flags = self.walls_widget.get_auto_equalize_flags()
        return ui_dto

    def _apply_ui_settings(self, settings: UISettingsDTO) -> None:
        """Applies UI settings into 3D schema widget, active tab, and inside walls controls."""
        self.schema_widget.set_ui_settings(settings)
        if 0 <= settings.active_tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(settings.active_tab_index)
        if hasattr(settings, "compartment_orientation") and settings.compartment_orientation:
            self.walls_widget.set_compartment_orientation(settings.compartment_orientation)
        if hasattr(settings, "auto_equalize_flags") and settings.auto_equalize_flags:
            self.walls_widget.set_auto_equalize_flags(settings.auto_equalize_flags)

    def _save_settings(self) -> None:
        """Saves window geometry, splitter sizes, tabs, and project state to QSettings."""
        settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        if hasattr(self, "main_splitter"):
            settings.setValue("mainSplitter", self.main_splitter.saveState())
        if hasattr(self, "tabs"):
            settings.setValue("currentTab", self.tabs.currentIndex())
        if self._current_project_path:
            settings.setValue("lastProjectPath", self._current_project_path)
        try:
            input_dto = self.input_panel.get_input_dto()
            input_dto.walls = self.walls_widget.get_walls()
            input_dto.ui_settings = self._get_current_ui_settings()
            settings.setValue("lastProjectSnapshot", input_dto.to_json())
        except Exception:
            pass

    def _restore_settings(self) -> None:
        """Restores window geometry, state, and splitter states from QSettings."""
        settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)

        state = settings.value("windowState")
        if state:
            self.restoreState(state)

        splitter_state = settings.value("mainSplitter")
        if splitter_state and hasattr(self, "main_splitter"):
            self.main_splitter.restoreState(splitter_state)

        tab_idx = settings.value("currentTab")
        if tab_idx is not None and hasattr(self, "tabs"):
            try:
                self.tabs.setCurrentIndex(int(tab_idx))
            except (ValueError, TypeError):
                pass

    def _load_startup_project(self) -> None:
        """Loads last project from file or snapshot at startup."""
        settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
        last_path = settings.value("lastProjectPath")
        if last_path and isinstance(last_path, str) and os.path.isfile(last_path):
            try:
                self._load_project_file(last_path, update_settings=False)
                return
            except Exception:
                pass

        last_snapshot = settings.value("lastProjectSnapshot")
        if last_snapshot and isinstance(last_snapshot, str):
            try:
                dto = CaseInputDTO.from_json(last_snapshot)
                self._apply_project_dto(dto)
                self._update_window_title()
                return
            except Exception:
                pass

        self.recalculate()
        self._update_window_title()

    def _update_window_title(self) -> None:
        if self._current_project_path:
            name = os.path.basename(self._current_project_path)
            self.setWindowTitle(f"Flightcase Calculator — {name}")
        else:
            self.setWindowTitle("Flightcase Calculator — Untitled")

    def _apply_project_dto(self, dto: CaseInputDTO) -> None:
        self.input_panel.set_input_dto(dto)
        self.walls_widget.set_walls(dto.walls)
        if dto.ui_settings:
            self._apply_ui_settings(dto.ui_settings)
        self.recalculate()

    def _new_project(self) -> None:
        default_dto = CaseInputDTO()
        self._current_project_path = None
        self._apply_project_dto(default_dto)
        self.schema_widget.canvas.reset_view(45.0, 30.0)
        self._update_window_title()
        self.status_bar.showMessage("New project created with default dimensions.")

    def _open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Flightcase Project",
            "",
            "Flightcase Project (*.fcproj *.json);;All Files (*)",
        )
        if file_path:
            self._load_project_file(file_path)

    def _load_project_file(self, file_path: str, update_settings: bool = True) -> None:
        try:
            dto = LoadProjectUseCase.execute(file_path)
            self._current_project_path = file_path
            self._apply_project_dto(dto)
            self._update_window_title()
            if update_settings:
                settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
                settings.setValue("lastProjectPath", file_path)
            self._add_recent_file(file_path)
            self.status_bar.showMessage(f"Project loaded from {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Load Project Error", f"Failed to load project from {file_path}:\n{str(e)}")

    def _save_project(self) -> None:
        if self._current_project_path:
            self._save_project_file(self._current_project_path)
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        default_name = os.path.basename(self._current_project_path) if self._current_project_path else "my_flightcase.fcproj"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Flightcase Project As",
            default_name,
            "Flightcase Project (*.fcproj *.json);;All Files (*)",
        )
        if file_path:
            self._save_project_file(file_path)

    def _save_project_file(self, file_path: str) -> None:
        try:
            input_dto = self.input_panel.get_input_dto()
            input_dto.walls = self.walls_widget.get_walls()
            input_dto.ui_settings = self._get_current_ui_settings()
            SaveProjectUseCase.execute(input_dto, file_path)
            self._current_project_path = file_path
            self._update_window_title()
            settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
            settings.setValue("lastProjectPath", file_path)
            self._add_recent_file(file_path)
            self.status_bar.showMessage(f"Project saved to {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Project Error", f"Failed to save project to {file_path}:\n{str(e)}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()
        super().closeEvent(event)

    def _connect_signals(self) -> None:
        self.input_panel.input_changed.connect(self.recalculate)
        self.walls_widget.walls_changed.connect(self.recalculate)
        self.schema_widget.lid_exploded_changed.connect(self._update_schema_geometry)
        self.schema_widget.toggles_changed.connect(self._update_schema_geometry)

        # Highlight synchronization across dimension tables and 3D schema
        self.walls_widget.wall_selection_changed.connect(self._on_wall_selection_changed)
        self.cutlist_widget.piece_selection_changed.connect(self._on_piece_selection_changed)
        self.alu_widget.profile_selection_changed.connect(self._on_profile_selection_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_wall_selection_changed(self, indices: List[int], labels: List[str]) -> None:
        self.schema_widget.set_highlights(wall_indices=indices, labels=labels)

    def _on_piece_selection_changed(self, names: List[str]) -> None:
        self.schema_widget.set_highlights(labels=names)

    def _on_profile_selection_changed(self, names: List[str]) -> None:
        self.schema_widget.set_highlights(labels=names)

    def _on_tab_changed(self, index: int) -> None:
        current_widget = self.tabs.widget(index)
        if current_widget == self.walls_widget:
            self.walls_widget.emit_current_selection()
        elif current_widget == self.cutlist_widget:
            self.cutlist_widget.emit_current_selection()
        elif current_widget == self.alu_widget:
            self.alu_widget.emit_current_selection()
        else:
            self.schema_widget.clear_highlights()

    def recalculate(self) -> None:
        """Executes application use cases to update all outputs live."""
        input_dto = self.input_panel.get_input_dto()
        input_dto.walls = self.walls_widget.get_walls()

        try:
            # 1. Calculate flightcase
            result = CalculateFlightCaseUseCase.execute(input_dto)
            self._current_result = result

            # 2. Update UI widgets
            self.walls_widget.set_case_dimensions(
                inner_length=result.inner_length,
                inner_width=result.inner_width,
                wood_thickness=input_dto.wood_thickness,
            )
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
    # Configure surface format for hardware antialiasing (4x MSAA)
    gl_format = QSurfaceFormat()
    gl_format.setSamples(4)
    gl_format.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(gl_format)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyleSheet(DARK_THEME_QSS)
    window = FlightCaseMainWindow()
    window.show()
    return app.exec()
