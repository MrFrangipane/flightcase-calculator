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
    GenerateWoodPanelsSvgUseCase,
    SaveProjectUseCase,
    LoadProjectUseCase,
    CalculationResultDTO,
)
from ..i18n import tr
from .theme import DARK_THEME_QSS
from .widgets import (
    CaseInputPanel,
    InsideWallsWidget,
    Schema3DWidget,
    CutListTableWidget,
    AluProfilesWidget,
    WoodPanelsSvgWidget,
    WoodTypesWidget,
    CostsWidget,
    CatalogWidget,
)
from ..application import CalculateQuoteUseCase, ExportProductionPackUseCase
from ..production.catalog import Catalog
from ..production.pack import full_report_csv


class FlightCaseMainWindow(QMainWindow):
    """Main window coordinating inputs, domain calculations, 3D schema, and cut lists."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        restore_settings: bool = True,
        load_last_project: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle("Calculadora de Flightcases — Sin título")
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

        # Main horizontal layout:
        # [ Left/Center: Splitter with Output Tables & 3D/2D Schema | Right: Fixed Configuration Panel ]
        self.main_splitter = QSplitter(Qt.Horizontal, self)

        # 1. Left Pane: Tabs containing dimensions / cutlist output tables
        self.tabs = QTabWidget(self)
        self.cutlist_widget = CutListTableWidget(self)
        self.alu_widget = AluProfilesWidget(self)
        self.wood_types_widget = WoodTypesWidget(self)
        self.catalog = Catalog()
        self._current_quote = None
        self.costs_widget = CostsWidget(self)
        self.catalog_widget = CatalogWidget(self.catalog, self)

        self.tabs.addTab(self.cutlist_widget, "Lista de cortes")
        self.tabs.addTab(self.alu_widget, "Perfiles de aluminio")
        self.tabs.addTab(self.costs_widget, "Presupuesto y herrajes")
        self.tabs.addTab(self.wood_types_widget, "Tipos de madera")
        self.tabs.addTab(self.catalog_widget, "Catálogo de herrajes y perfiles")
        self.main_splitter.addWidget(self.tabs)

        # 2. Center Pane: Central tabs containing 3D Schema and 2D Wood Panels Diagram
        self.center_tabs = QTabWidget(self)
        self.schema_widget = Schema3DWidget(self)
        self.svg_widget = WoodPanelsSvgWidget(self)

        self.center_tabs.addTab(self.schema_widget, "Vista 3D")
        self.center_tabs.addTab(self.svg_widget, "Paneles 2D (SVG)")
        self.main_splitter.addWidget(self.center_tabs)

        # Set splitter proportions (40% left output tables, 60% center 3D schema)
        self.main_splitter.setStretchFactor(0, 40)
        self.main_splitter.setStretchFactor(1, 60)

        # 3. Right Pane: Permanent Configuration Panel (Dimensions & Specs + Inside Walls)
        self.input_panel = CaseInputPanel(self)
        self.walls_widget = InsideWallsWidget(self)

        self.config_container = QWidget(self)
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(12)
        config_layout.addWidget(self.input_panel)
        config_layout.addWidget(self.walls_widget)
        config_layout.addStretch(1)

        main_layout.addWidget(self.main_splitter, stretch=1)
        main_layout.addWidget(self.config_container, stretch=0)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo. Todas las validaciones del modelo son correctas.")

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()

        # File Menu
        self.file_menu = menu_bar.addMenu("&Archivo")

        new_action = QAction("&Nuevo proyecto", self)
        new_action.setShortcut("Ctrl+N")
        new_action.setStatusTip("Crear un proyecto de flightcase nuevo")
        new_action.triggered.connect(self._new_project)
        self.file_menu.addAction(new_action)

        open_action = QAction("A&brir proyecto...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Abrir un archivo de proyecto existente")
        open_action.triggered.connect(self._open_project)
        self.file_menu.addAction(open_action)

        save_action = QAction("&Guardar proyecto", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("Guardar el proyecto actual")
        save_action.triggered.connect(self._save_project)
        self.file_menu.addAction(save_action)

        save_as_action = QAction("Guardar proyecto &como...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.setStatusTip("Guardar el proyecto en un archivo nuevo")
        save_as_action.triggered.connect(self._save_project_as)
        self.file_menu.addAction(save_as_action)

        # Open Recent Section (up to 5 recent files, directly in the menu, no submenu)
        self.recent_section_action = self.file_menu.addSection("Recientes")
        self.recent_file_actions: List[QAction] = []
        for _ in range(5):
            act = QAction(self)
            act.setVisible(False)
            self.file_menu.addAction(act)
            self.recent_file_actions.append(act)

        self._update_recent_files_menu()

        self.file_menu.addSeparator()

        export_action = QAction("&Exportar lista de cortes completa...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip("Exportar el listado completo de materiales a CSV")
        export_action.triggered.connect(self._export_full_report)
        self.file_menu.addAction(export_action)

        export_svg_action = QAction("Exportar &paneles de madera a SVG...", self)
        export_svg_action.setShortcut("Ctrl+Shift+E")
        export_svg_action.setStatusTip("Exportar el plano de todos los paneles de madera a un archivo SVG")
        export_svg_action.triggered.connect(self._export_wood_panels_svg)
        self.file_menu.addAction(export_svg_action)

        export_pack_action = QAction("Exportar paquete de &producción (PDF, DXF, CSV, SVG)...", self)
        export_pack_action.setShortcut("Ctrl+P")
        export_pack_action.triggered.connect(self._export_production_pack)
        self.file_menu.addAction(export_pack_action)

        self.file_menu.addSeparator()

        exit_action = QAction("&Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Salir de la Calculadora de Flightcases")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu_bar.addMenu("&Ver")

        view_3d_action = QAction("Vista &3D", self)
        view_3d_action.setShortcut("Ctrl+1")
        view_3d_action.setStatusTip("Cambiar a la vista 3D interactiva")
        view_3d_action.triggered.connect(lambda: self.center_tabs.setCurrentWidget(self.schema_widget))
        view_menu.addAction(view_3d_action)

        reset_view_action = QAction("&Restablecer vista 3D", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.setStatusTip("Volver la cámara 3D a la vista isométrica predeterminada")
        reset_view_action.triggered.connect(self._reset_3d_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

        view_wood_types_action = QAction("Editar &tipos de madera", self)
        view_wood_types_action.setStatusTip("Ir a la pestaña de gestión de tipos de madera")
        view_wood_types_action.triggered.connect(lambda: self.tabs.setCurrentWidget(self.wood_types_widget))
        view_menu.addAction(view_wood_types_action)

        view_menu.addSeparator()

        view_svg_action = QAction("Ver plano 2D de &paneles (SVG)", self)
        view_svg_action.setShortcut("Ctrl+2")
        view_svg_action.setStatusTip("Cambiar al plano técnico 2D de los paneles de madera")
        view_svg_action.triggered.connect(lambda: self.center_tabs.setCurrentWidget(self.svg_widget))
        view_menu.addAction(view_svg_action)

        fit_svg_action = QAction("&Ajustar plano 2D a la ventana", self)
        fit_svg_action.setShortcut("Ctrl+D")
        fit_svg_action.setStatusTip("Ajustar el plano 2D de paneles a la ventana")
        fit_svg_action.triggered.connect(self._fit_svg_view)
        view_menu.addAction(fit_svg_action)

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

    def _reset_3d_view(self) -> None:
        """Switches to 3D schema tab and resets camera view angles."""
        if hasattr(self, "center_tabs"):
            self.center_tabs.setCurrentWidget(self.schema_widget)
        self.schema_widget.canvas.reset_view(45.0, 30.0)

    def _fit_svg_view(self) -> None:
        """Switches to 2D SVG tab and fits diagram into viewport."""
        if hasattr(self, "center_tabs"):
            self.center_tabs.setCurrentWidget(self.svg_widget)
        self.svg_widget.fit_to_view()

    def _get_current_ui_settings(self) -> UISettingsDTO:
        """Gathers active UI settings including 3D camera transform, toggles, active tab, and compartment settings."""
        ui_dto = self.schema_widget.get_ui_settings()
        ui_dto.active_tab_index = self.tabs.currentIndex()
        if hasattr(self, "center_tabs"):
            ui_dto.active_center_tab_index = self.center_tabs.currentIndex()
        ui_dto.compartment_orientation = self.walls_widget.get_compartment_orientation()
        ui_dto.auto_equalize_flags = self.walls_widget.get_auto_equalize_flags()
        return ui_dto

    def _apply_ui_settings(self, settings: UISettingsDTO) -> None:
        """Applies UI settings into 3D schema widget, active tab, and inside walls controls."""
        self.schema_widget.set_ui_settings(settings)
        if 0 <= settings.active_tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(settings.active_tab_index)
        if hasattr(settings, "active_center_tab_index") and hasattr(self, "center_tabs"):
            if 0 <= settings.active_center_tab_index < self.center_tabs.count():
                self.center_tabs.setCurrentIndex(settings.active_center_tab_index)
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
        if hasattr(self, "center_tabs"):
            settings.setValue("currentCenterTab", self.center_tabs.currentIndex())
        if self._current_project_path:
            settings.setValue("lastProjectPath", self._current_project_path)
        try:
            input_dto = self._collect_input_dto()
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

        center_tab_idx = settings.value("currentCenterTab")
        if center_tab_idx is not None and hasattr(self, "center_tabs"):
            try:
                self.center_tabs.setCurrentIndex(int(center_tab_idx))
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
        title = self.input_panel.edit_title.text().strip() if hasattr(self, "input_panel") else ""
        if title:
            if self._current_project_path:
                file_name = os.path.basename(self._current_project_path)
                self.setWindowTitle(f"Calculadora de Flightcases — {title} ({file_name})")
            else:
                self.setWindowTitle(f"Calculadora de Flightcases — {title}")
        elif self._current_project_path:
            name = os.path.basename(self._current_project_path)
            self.setWindowTitle(f"Calculadora de Flightcases — {name}")
        else:
            self.setWindowTitle("Calculadora de Flightcases — Sin título")

    def _apply_project_dto(self, dto: CaseInputDTO) -> None:
        self.input_panel.set_input_dto(dto)
        self.walls_widget.set_walls(dto.walls)
        self.costs_widget.set_settings(dto.production)
        if dto.ui_settings:
            self._apply_ui_settings(dto.ui_settings)
        self.recalculate()

    def _new_project(self) -> None:
        default_dto = CaseInputDTO()
        self._current_project_path = None
        self._apply_project_dto(default_dto)
        self.schema_widget.canvas.reset_view(45.0, 30.0)
        self._update_window_title()
        self.status_bar.showMessage("Proyecto nuevo creado con las medidas predeterminadas.")

    def _open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto de flightcase",
            "",
            "Proyecto de flightcase (*.fcproj *.json);;Todos los archivos (*)",
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
            self.status_bar.showMessage(f"Proyecto cargado desde {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error al abrir el proyecto", f"No se pudo abrir el proyecto {file_path}:\n{tr(str(e))}")

    def _save_project(self) -> None:
        if self._current_project_path:
            self._save_project_file(self._current_project_path)
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        title = self.input_panel.edit_title.text().strip()
        if self._current_project_path:
            default_name = os.path.basename(self._current_project_path)
        elif title:
            import re
            slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()
            default_name = f"{slug}.fcproj" if slug else "mi_flightcase.fcproj"
        else:
            default_name = "mi_flightcase.fcproj"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto de flightcase como",
            default_name,
            "Proyecto de flightcase (*.fcproj *.json);;Todos los archivos (*)",
        )
        if file_path:
            self._save_project_file(file_path)

    def _save_project_file(self, file_path: str) -> None:
        try:
            input_dto = self._collect_input_dto()
            input_dto.ui_settings = self._get_current_ui_settings()
            SaveProjectUseCase.execute(input_dto, file_path)
            self._current_project_path = file_path
            self._update_window_title()
            settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
            settings.setValue("lastProjectPath", file_path)
            self._add_recent_file(file_path)
            self.status_bar.showMessage(f"Proyecto guardado en {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar el proyecto", f"No se pudo guardar el proyecto en {file_path}:\n{str(e)}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()
        super().closeEvent(event)

    def _connect_signals(self) -> None:
        self.input_panel.input_changed.connect(self.recalculate)
        self.walls_widget.walls_changed.connect(self.recalculate)
        self.schema_widget.lid_exploded_changed.connect(self._update_schema_geometry)
        self.schema_widget.explode_changed.connect(self._update_schema_geometry)
        self.schema_widget.lid_rotation_changed.connect(self._update_schema_geometry)
        self.schema_widget.toggles_changed.connect(self._update_schema_geometry)
        self.cutlist_widget.export_svg_requested.connect(self._export_wood_panels_svg)
        self.wood_types_widget.materials_changed.connect(self._on_wood_materials_changed)
        self.costs_widget.settings_changed.connect(self.recalculate)
        self.catalog_widget.catalog_changed.connect(self.recalculate)

        # Highlight synchronization across dimension tables and 3D schema
        self.walls_widget.wall_selection_changed.connect(self._on_wall_selection_changed)
        self.cutlist_widget.piece_selection_changed.connect(self._on_piece_selection_changed)
        self.alu_widget.profile_selection_changed.connect(self._on_profile_selection_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_wood_materials_changed(self, materials: List[WoodMaterial]) -> None:
        """Handles wood materials update from the Wood Types tab."""
        self.input_panel.set_wood_materials(materials)
        self.recalculate()

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

    def _collect_input_dto(self) -> CaseInputDTO:
        input_dto = self.input_panel.get_input_dto()
        input_dto.walls = self.walls_widget.get_walls()
        input_dto.production = self.costs_widget.get_settings()
        return input_dto

    def recalculate(self) -> None:
        """Executes application use cases to update all outputs live."""
        input_dto = self.input_panel.get_input_dto()
        input_dto.production = self.costs_widget.get_settings()
        self.walls_widget.set_case_dimensions(
            inner_length=input_dto.inner_length,
            inner_width=input_dto.inner_width,
            wood_thickness=input_dto.wood_thickness,
        )
        input_dto.walls = self.walls_widget.get_walls()

        try:
            # 1. Calculate flightcase
            result = CalculateFlightCaseUseCase.execute(input_dto)
            self._current_result = result

            # 2. Update UI widgets
            self.cutlist_widget.set_calculation_result(result)
            self.alu_widget.set_calculation_result(result)
            self._current_quote = CalculateQuoteUseCase.execute(input_dto, self.catalog)
            self.costs_widget.set_quote(self._current_quote)

            # Generate and update wood panels SVG diagram
            svg_data = GenerateWoodPanelsSvgUseCase.execute(input_dto)
            self.svg_widget.set_svg(svg_data, project_title=input_dto.title)

            self._update_schema_geometry()
            self._update_window_title()

            # 3. Status Bar
            lid_m = result.total_lid_mating_profile_length_mm / 1000.0
            self.status_bar.showMessage(
                f"✓ Interior: {input_dto.inner_length:.0f}×{input_dto.inner_width:.0f}×{input_dto.inner_total_height:.0f} mm | "
                f"Exterior: {input_dto.outer_length:.0f}×{input_dto.outer_width:.0f}×{input_dto.total_height:.0f} mm | "
                f"Perfil de cierre necesario: {result.total_lid_mating_profile_length_mm:.1f} mm ({lid_m:.2f} m) | "
                f"Paneles de madera: {len(result.wood_cut_list)} piezas ({result.total_wood_area_m2:.2f} m²) | "
                f"Precio: {self._current_quote.total_price:.2f} € | Peso: {self._current_quote.total_weight_kg:.1f} kg"
            )
        except FlightCaseDomainError as e:
            self.status_bar.showMessage(f"⚠ Error de validación: {str(e)}")
        except Exception as e:
            self.status_bar.showMessage(f"⚠ Error: {str(e)}")

    def _update_schema_geometry(self) -> None:
        input_dto = self.input_panel.get_input_dto()
        input_dto.walls = self.walls_widget.get_walls()

        try:
            mesh = GenerateSchema3DUseCase.execute(
                input_dto=input_dto,
                lid_exploded_gap_mm=self.schema_widget.exploded_gap_mm,
                explode_gap_mm=self.schema_widget.explode_gap_mm,
                lid_rotation_angle_deg=self.schema_widget.rotation_angle_deg,
                lid_hinge_side=self.schema_widget.hinge_side,
                show_inside_walls=self.schema_widget.show_inside_walls,
                show_dimensions=self.schema_widget.show_dimensions,
            )
            self.schema_widget.set_mesh(mesh)
        except FlightCaseDomainError:
            pass

    def _export_wood_panels_svg(self) -> None:
        self.svg_widget.export_svg()

    def _export_full_report(self) -> None:
        if not self._current_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar listado de materiales", "flightcase_listado_materiales.csv", "Archivos CSV (*.csv)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(full_report_csv(self._current_result, self._current_quote))

                QMessageBox.information(self, "Exportación correcta", f"Informe completo exportado a:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error de exportación", f"No se pudo guardar el archivo CSV:\n{str(e)}")

    def _export_production_pack(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Carpeta para el paquete de producción")
        if not folder:
            return
        input_dto = self._collect_input_dto()
        title = input_dto.title.strip() or "flightcase"
        import re
        sub = re.sub(r"[^\w\-]+", "_", title).strip("_") or "flightcase"
        target = os.path.join(folder, f"{sub}_produccion")
        try:
            files = ExportProductionPackUseCase.execute(input_dto, target, self.catalog)
            QMessageBox.information(
                self, "Paquete de producción",
                f"Se generaron {len(files)} archivos en:\n{target}\n\n" + "\n".join(os.path.basename(f) for f in files),
            )
        except Exception as e:
            QMessageBox.critical(self, "Paquete de producción", f"No se pudo generar el paquete:\n{e}")


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
