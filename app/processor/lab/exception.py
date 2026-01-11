class UserFacingError(Exception):
    """Exception that should be displayed to the user with a popup dialog.

    Attributes:
        title: The title of the error dialog.
        message: The detailed message to show to the user.
        severity: Either "error" or "info" (default: "error").
    """

    def __init__(self, title: str, message: str, severity: str = "error") -> None:
        super().__init__(message)
        self.title = title
        self.message = message
        self.severity = severity
