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
)
from .entities import (
    FlightCase,
    CaseCompartment,
)
from .services import (
    FlightCaseCalculationReport,
    WireframeMesh3D,
    FlightCaseDomainService,
    Schema3DGeometryBuilder,
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
    "FlightCase",
    "CaseCompartment",
    "FlightCaseCalculationReport",
    "WireframeMesh3D",
    "FlightCaseDomainService",
    "Schema3DGeometryBuilder",
    "ParallelProjector",
]
