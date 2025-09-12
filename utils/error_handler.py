import logging
from enum import Enum

class ErrorCategory(Enum):
    NETWORK = "Netzwerkfehler"
    API = "API-Fehler"
    PERMISSION = "Berechtigungsfehler"
    VALIDATION = "Validierungsfehler"
    UNKNOWN = "Unbekannter Fehler"

class ErrorHandler:
    def __init__(self, logger):
        self.logger = logger

    def handle_error(self, error, category=ErrorCategory.UNKNOWN):
        error_message = f"{category.value}: {str(error)}"
        self.logger.error(error_message)
        return error_message

    def log_and_notify(self, ctx, error_message):
        self.logger.error(error_message)
        return ctx.send(f"Ein Fehler ist aufgetreten: {error_message}")

