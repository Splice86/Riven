"""Exit module for riven - allows LLM to exit the program."""

import threading
from modules import Module, check_modules_changed, update_module_mtimes

# Global flag to signal exit (thread-safe)
# This must be at module level so all imports share the same instance
_exit_requested = threading.Event()


def is_exit_requested() -> bool:
    """Check if exit was requested."""
    return _exit_requested.is_set()


def clear_exit() -> None:
    """Clear the exit flag."""
    _exit_requested.clear()


def get_module():
    """Get the exit module."""
    
    def exit_session(message: str = "Goodbye!") -> str:
        """Exit the current session.
        
        Args:
            message: Optional goodbye message to display.
        
        Returns:
            Goodbye message.
        """
        _exit_requested.set()
        return message
    
    def check_reload_modules() -> str:
        """Check if any module files have changed and need reloading.
        
        Returns:
            Whether modules have changed and need reload.
        """
        if check_modules_changed():
            update_module_mtimes()
            return "Modules have changed. Call reload_modules to apply changes."
        return "No module changes detected."
    
    return Module(
        name="exit",
        enrollment=lambda: None,
        functions={
            "exit_session": exit_session,
            "check_reload_modules": check_reload_modules,
        },
        get_context=lambda: None,
        tag="system"
    )