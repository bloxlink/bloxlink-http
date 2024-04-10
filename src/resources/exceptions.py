from bloxlink_lib.exceptions import *

class Message(BloxlinkException):
    """Generic exception to communicate some message to the user."""

class BloxlinkForbidden(BloxlinkException):
    """Raised when a user is forbidden from using a command or
    Bloxlink does not have the proper permissions.
    """

class PromptException(BloxlinkException):
    """Base exception for prompts."""

class CancelPrompt(PromptException):
    """Raised when a prompt is cancelled."""

class PageNotFound(PromptException):
    """Raised when a page is not found."""

class CancelCommand(BloxlinkException):
    """Raised when a command is cancelled. This silently cancels the command."""

class PremiumRequired(CancelCommand):
    """Raised when a command requires premium."""

class BadArgument(BloxlinkException):
    """Raised when a command argument is invalid."""

class CommandException(BloxlinkException):
    """Base exception for commands."""

class AlreadyResponded(CommandException):
    """Raised when a command has already responded."""

class BindException(BloxlinkException):
    """Base exception for binds."""

class BindConflictError(BindException):
    """Raised when a bind conflicts with another bind."""
