"""Bio module - loads character bio for system prompt."""

import os
from pathlib import Path

from modules import Module


DEFAULT_BIO_DIR = Path(__file__).parent.parent / "bios"


def get_module(bio_name: str = "riven") -> Module:
    """Load a character bio and return as a module.
    
    Args:
        bio_name: Name of the bio file (without extension)
        
    Returns:
        Module with get_context that returns bio content
    """
    bio_path = DEFAULT_BIO_DIR / f"{bio_name}.md"
    
    if not bio_path.exists():
        bio_content = f"# {bio_name}\n\n(No bio found for this character)"
    else:
        with open(bio_path, "r") as f:
            bio_content = f.read()
    
    def get_bio_context() -> str:
        """Return the bio content for the system prompt."""
        return bio_content
    
    return Module(
        name=f"bio_{bio_name}",
        get_context=get_bio_context,
        tag="bio"
    )
