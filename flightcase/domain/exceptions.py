"""Domain exceptions for Flightcase Calculator."""


class FlightCaseDomainError(Exception):
    """Base exception for all domain-level errors."""
    pass


class InvalidDimensionError(FlightCaseDomainError):
    """Raised when dimension values violate domain invariants."""
    pass


class WallOutOfBoundsError(FlightCaseDomainError):
    """Raised when an inside wall is placed outside the internal boundary of the case."""
    pass


class InvalidLidConfigurationError(FlightCaseDomainError):
    """Raised when lid height or profile offset is incompatible with total height."""
    pass
