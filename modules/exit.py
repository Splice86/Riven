"""Exit module for riven - allows LLM to exit the program."""

from modules import Module


def get_module():
    """Get the exit module."""
    
    def exit_session(message: str = "Goodbye!") -> str:
        """Exit the current session.
        
        Args:
            message: Optional goodbye message to display.
        
        Returns:
            Goodbye message.
        """
        # Set a flag that the CLI can check
        import sys
        sys.exit(0)
    
    return Module(
        name="exit",
        enrollment=lambda: None,
        functions={
            "exit_session": exit_session,
        },
        get_context=lambda: None,
        tag="system"
    )