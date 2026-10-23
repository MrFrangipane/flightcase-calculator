"""Flightcase Domain Layer."""

from .exceptions import (
    FlightCaseDomainError,
    InvalidDimensionError,
    WallOutOfBoundsError,
    InvalidLidConfigurationError,
)
from .value_objects import (
    Dimensions3D,
    WallOrientation,
    InsideWall,
    CutPieceCategory,
    CutPiece,
    Point3D,
    Segment3D,
    PolygonFace3D,
    DimensionCallout3D,
    ComponentLayer,
)
from .entities import (
    FlightCase,
    CaseCompartment,
)
from .materials import (
    WoodMaterial,
    load_wood_materials,
    save_wood_materials,
    find_wood_material,
)
from .services import (
    FlightCaseCalculationReport,
    WireframeMesh3D,
    FlightCaseDomainService,
    Schema3DGeometryBuilder,
    WoodPanelsSvgGenerator,
    ParallelProjector,
)

__all__ = [
    "FlightCaseDomainError",
    "InvalidDimensionError",
    "WallOutOfBoundsError",
    "InvalidLidConfigurationError",
    "Dimensions3D",
    "WallOrientation",
    "InsideWall",
    "CutPieceCategory",
    "CutPiece",
    "Point3D",
    "Segment3D",
    "PolygonFace3D",
    "DimensionCallout3D",
    "ComponentLayer",
    "FlightCase",
    "CaseCompartment",
    "WoodMaterial",
    "load_wood_materials",
    "save_wood_materials",
    "find_wood_material",
    "FlightCaseCalculationReport",
    "WireframeMesh3D",
    "FlightCaseDomainService",
    "Schema3DGeometryBuilder",
    "WoodPanelsSvgGenerator",
    "ParallelProjector",
]
