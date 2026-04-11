# Core Switcher Module
import os
import yaml
import glob


def _load_cores() -> dict:
    """Load cores from the cores/ folder."""
    cores = {}
    cores_dir = "cores"
    
    if not os.path.exists(cores_dir):
        return cores
    
    for filepath in glob.glob(os.path.join(cores_dir, "*.yaml")):
        with open(filepath) as f:
            core_config = yaml.safe_load(f)
            if core_config and 'name' in core_config:
                core_name = core_config.pop('name')
                cores[core_name] = core_config
    
    return cores


def list_cores() -> list[dict]:
    """List available cores with names and descriptions.
    
    Returns:
        List of dicts with 'name', 'display_name', and 'description'
    """
    cores = _load_cores()
    result = []
    
    for name, config in cores.items():
        result.append({
            'name': name,
            'display_name': config.get('display_name', name),
            'description': config.get('description', 'No description'),
        })
    
    return result


def get_core_description(core_name: str) -> str:
    """Get description for a specific core.
    
    Args:
        core_name: Name of the core
        
    Returns:
        Description string
    """
    cores = _load_cores()
    if core_name in cores:
        return cores[core_name].get('description', 'No description')
    return f"Core '{core_name}' not found"


def core_exists(core_name: str) -> bool:
    """Check if a core exists.
    
    Args:
        core_name: Name of the core
        
    Returns:
        True if core exists
    """
    return core_name in _load_cores()


async def switch_core(core_name: str) -> str:
    """Switch to a different core.
    
    Args:
        core_name: Name of the core to switch to
        
    Returns:
        Confirmation message
    """
    cores = _load_cores()
    
    if core_name not in cores:
        available = ", ".join(cores.keys())
        return f"Core '{core_name}' not found. Available: {available}"
    
    display = cores[core_name].get('display_name', core_name)
    desc = cores[core_name].get('description', '')
    
    return f"Switched to {display}: {desc}"


def get_module():
    """Return module definition."""
    from modules import Module, Tool
    
    return Module(
        name="core_switcher",
        description="Switch between different AI cores",
        tools=[
            Tool(
                name="list_cores",
                description="List available cores with descriptions",
                func=list_cores,
            ),
            Tool(
                name="switch_core",
                description="Switch to a different core by name",
                func=switch_core,
            ),
        ],
    )