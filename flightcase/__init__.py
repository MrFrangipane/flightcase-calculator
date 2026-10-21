"""Flightcase Calculator package following Domain-Driven Design (DDD) principles."""

from .domain import (
    FlightCase,
    Dimensions3D,
    InsideWall,
    WallOrientation,
    CutPiece,
    CutPieceCategory,
    FlightCaseDomainError,
    InvalidDimensionError,
    WallOutOfBoundsError,
    InvalidLidConfigurationError,
)
from .application import (
    CaseInputDTO,
    InsideWallDTO,
    UISettingsDTO,
    CalculationResultDTO,
    CutPieceDTO,
    CalculateFlightCaseUseCase,
    GenerateSchema3DUseCase,
)
from .ui import (
    FlightCaseMainWindow,
    run_app,
)

__all__ = [
    "FlightCase",
    "Dimensions3D",
    "InsideWall",
    "WallOrientation",
    "CutPiece",
    "CutPieceCategory",
    "FlightCaseDomainError",
    "InvalidDimensionError",
    "WallOutOfBoundsError",
    "InvalidLidConfigurationError",
    "CaseInputDTO",
    "InsideWallDTO",
    "UISettingsDTO",
    "CalculationResultDTO",
    "CutPieceDTO",
    "CalculateFlightCaseUseCase",
    "GenerateSchema3DUseCase",
    "FlightCaseMainWindow",
    "run_app",
]
