class DomainException(Exception):
    """Base class for domain exceptions"""
    message: str
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class EntityNotFoundError(DomainException):
    """Raised when an entity is not found"""
    pass

class BusinessRuleViolationError(DomainException):
    """Raised when a business rule is violated"""
    pass
