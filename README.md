# Flightcase Calculator

A desktop CAD/CAM estimation and design tool built with Python, PySide6, and OpenGL to streamline the design, calculation, and fabrication of custom flightcases and road trunks.

![Screenshot 3D](screenshot-3d.jpg)

![Screenshot 2D](screenshot-2d.jpg)

---

## Features

- **Precise Material Calculations & Cost/Weight Estimation**:
  - Automatically computes exact cut dimensions, surface areas, and quantities for wood panels (sides, lid, base, top) and aluminum profiles (corner extrusions, lid mating profiles).
  - Calculates total wood area ($m^2$), estimated wood weight ($kg$), total estimated material cost ($€$), and standard $2440 \times 1220\text{ mm}$ sheet count.
- **Wood Material Library & Custom Presets**:
  - Built-in material presets from JSON resources (Birch plywood 4–18mm, Hexa textured birch, lightweight Poplar, and Astroboard / Con-Pearl panels).
  - Automatically loads and synchronizes thickness, density ($\text{kg/m}^3$), and unit price ($€/\text{m}^2$).
  - Full support for custom material specifications.
- **Interactive 3D OpenGL Visualizer**:
  - Full 3D orbit, pan, and zoom navigation with hardware-accelerated anti-aliased wireframe and solid rendering.
  - Exploded view slider with automatic panel dimension callouts.
  - Interactive lid opening simulation with selectable hinge sides (Back, Front, Left, Right) and 0°–180° rotation.
  - Dynamic inner partition wall rendering and bidirectional selection highlighting with cut list tables.
  - Support for both standard split-lid construction and self-cut lid (6-wall uncut box) workflows with cut markings.
- **2D Wood Panels Technical Drawings (SVG)**:
  - Generates printer-friendly, high-contrast vector cut sheets.
  - Interactive 2D viewport with smooth pan and zoom.
  - One-click SVG export formatted for physical print or laser/CNC cut prep.
- **Dynamic Compartment & Partition Wall Management**:
  - Configure inside dividing walls along X and Y axes with real-time recalculation.
  - One-click auto-equalize distribution or custom width allocation per compartment.
  - Partition wall thickness automatically synchronized with the active wood material specification.
- **Bill of Materials (BOM) & Cut Lists**:
  - Detailed wood cut list and aluminum profile tables with smooth pixel-level scrolling.
  - Full BOM export to CSV for workshop cut lists and supplier orders.
- **Project Management & Ergonomic UI**:
  - Save and load `.fcproj` project files with automatic window state and project snapshot restoration.
  - Quick access to recently opened project files.
  - Workshop-optimized dark theme with a streamlined, fixed configuration panel layout.

---

## Requirements

- Python >= 3.14
- Supported operating systems: Windows, macOS, Linux

### Core Dependencies

- `PySide6`: Modern Qt-based desktop UI
- `PyOpenGL`: Hardware-accelerated 3D wireframe and solid surface rendering
- `numpy`: Fast 3D vector and matrix geometric transformations
- `pytest`: Automated test suite

---

## Getting Started

### 1. Installation

Clone or download the repository, then install dependencies:

```bash
# Using uv (recommended)
uv sync

# Or using standard pip
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

pip install -e .
```

### 2. Running the Application

- **Windows Shortcut**: Double-click `run.cmd` or execute:
  ```cmd
  run.cmd
  ```
- **Direct CLI Execution**:
  ```bash
  python main.py
  # or with uv
  uv run python main.py
  ```

### 3. Running Automated Tests

Run the complete test suite:

```bash
uv run pytest
# or with active virtual environment:
pytest
```

---

## AI Attribution & Development Note

This software was developed with the assistance of Artificial Intelligence (AI) for architecture design, geometric calculations, 3D/2D rendering workflows, and comprehensive automated test suites.
