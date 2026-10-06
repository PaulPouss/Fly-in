
"""Custom exceptions shared across the Fly-in project.
 
Kept in their own module (no dependency on classes.py, parser.py, or
map_builder.py) to avoid circular imports between those.
"""
 
 
class ParserError(Exception):
    """Accumulates one or more validation errors found while parsing an
    input file, keyed by line number, so the caller can report every
    problem found in a single pass instead of stopping at the first
    one."""
 
    def __init__(self) -> None:
        """Start with no errors recorded."""
        super().__init__()
        self.errors: dict[int, list[str]] = {}
 
    def add_error(self, line: int, error: str) -> None:
        """Record an error message for the given line number.
 
        Args:
            line: 1-indexed line number where the error occurred.
            error: human-readable description of the problem.
        """
        self.errors.setdefault(line, []).append(error)
 
 
class ValidationError(Exception):
    """Raised when a single line or value fails validation (bad
    syntax, invalid zone type, non-positive capacity, etc.)."""
 
    def __init__(self, message: str) -> None:
        """Store the reason validation failed.
 
        Args:
            message: human-readable description of the problem.
        """
        super().__init__(message)
 
 
class SimulationError(Exception):
    """Raised when the simulation itself cannot proceed (no path
    found, deadlock detected, inconsistent internal state)."""
 
    def __init__(self, message: str) -> None:
        """Store the reason the simulation failed.
 
        Args:
            message: human-readable description of the problem.
        """
        super().__init__(message)