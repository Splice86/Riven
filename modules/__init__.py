"""Module system for riven."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Module:
    """A riven module with optional enrollment and context functionality.
    
    Rules:
    - If functions present → enrollment MUST be present
    - If get_context present → tag MUST be present
    - Must have at least one set (functions+enrollment OR get_context+tag)
    - Can have both sets
    """
    name: str
    enrollment: Callable | None = None  # Required if functions present
    functions: dict[str, Callable] = field(default_factory=dict)  # Required if enrollment present
    get_context: Callable[[], Any] | None = None  # Required if tag present
    tag: str | None = None  # Required if get_context present
    _session_id: str = ""  # Required - set at registration
    
    def __post_init__(self):
        has_functions = bool(self.functions)
        has_enrollment = self.enrollment is not None
        has_context = self.get_context is not None
        has_tag = self.tag is not None
        
        # Validate rules
        if has_functions and not has_enrollment:
            raise ValueError(f"Module {self.name}: functions requires enrollment")
        if has_enrollment and not has_functions:
            raise ValueError(f"Module {self.name}: enrollment requires functions")
        if has_context and not has_tag:
            raise ValueError(f"Module {self.name}: get_context requires tag")
        if has_tag and not has_context:
            raise ValueError(f"Module {self.name}: tag requires get_context")
        
        # Must have at least one set
        if not (has_functions or has_context):
            raise ValueError(f"Module {self.name}: must have either functions or get_context")


class ModuleRegistry:
    """Registry for riven modules."""
    
    def __init__(self):
        self._modules: dict[str, Module] = {}
        self._enrolled: bool = False
    
    def register(self, module: Module, session_id: str) -> None:
        """Register a module with session_id.
        
        If module has enrollment, it will be called.
        """
        self._modules[module.name] = module
        module._session_id = session_id
        
        # Run enrollment if present
        if module.enrollment:
            module.enrollment()
    
    def get(self, name: str) -> Module | None:
        """Get a module by name."""
        return self._modules.get(name)
    
    def all(self) -> dict[str, Module]:
        """Get all modules."""
        return self._modules.copy()
    
    def get_functions(self) -> list[tuple[str, Callable, str]]:
        """Get all functions from enrolled modules.
        
        Returns:
            List of (name, function, description) tuples
        """
        functions = []
        for module in self._modules.values():
            if module.functions:
                # Get functions with their descriptions
                for name, func in module.functions.items():
                    desc = getattr(func, '__doc__', '') or ''
                    functions.append((name, func, desc.strip().split('\n')[0]))
        return functions
    
    def build_context(self) -> dict[str, Any]:
        """Build context from all modules with get_context.
        
        Returns:
            Dict of tag -> context value
        """
        context = {}
        for module in self._modules.values():
            if module.get_context and module.tag:
                try:
                    context[module.tag] = module.get_context()
                except Exception:
                    context[module.tag] = None
        return context


# Auto-discover modules from files
def discover_modules() -> list:
    """Discover all modules in the modules folder.
    
    Each module file should export a get_module() function.
    
    Returns:
        List of Module instances
    """
    import os
    
    modules = []
    modules_dir = os.path.dirname(os.path.abspath(__file__))
    
    for filename in os.listdir(modules_dir):
        if filename.startswith('_'):
            continue
        if not filename.endswith('.py'):
            continue
        
        module_name = filename[:-3]  # Remove .py
        
        # Import the module
        try:
            mod = __import__(f'modules.{module_name}', fromlist=['get_module'])
            if hasattr(mod, 'get_module'):
                module = mod.get_module()
                modules.append(module)
        except Exception as e:
            print(f"Warning: Failed to load module {module_name}: {e}")
    
    return modules


def get_all_modules() -> list:
    """Get all auto-discovered modules.
    
    Returns:
        List of Module instances
    """
    return discover_modules()


# Global registry
registry = ModuleRegistry()

# Track module file mtimes for auto-reload
_module_mtimes: dict[str, float] = {}


def get_module_mtimes() -> dict[str, float]:
    """Get modification times of all module files."""
    import os
    mtimes = {}
    modules_dir = os.path.dirname(os.path.abspath(__file__))
    
    for filename in os.listdir(modules_dir):
        if filename.startswith('_'):
            continue
        if not filename.endswith('.py'):
            continue
        
        path = os.path.join(modules_dir, filename)
        mtimes[filename] = os.path.getmtime(path)
    
    return mtimes


def check_modules_changed() -> bool:
    """Check if any module files have changed since last check."""
    global _module_mtimes
    
    current_mtimes = get_module_mtimes()
    
    # Check if any new or modified files
    for filename, mtime in current_mtimes.items():
        if filename not in _module_mtimes:
            return True
        if mtime > _module_mtimes[filename]:
            return True
    
    # Check if any files were deleted
    for filename in _module_mtimes:
        if filename not in current_mtimes:
            return True
    
    return False


def update_module_mtimes() -> None:
    """Update the stored modification times."""
    global _module_mtimes
    _module_mtimes = get_module_mtimes()


def reload_modules(registry: ModuleRegistry) -> str:
    """Reload all modules from disk.
    
    Args:
        registry: The registry to reload modules into
        
    Returns:
        Confirmation message
    """
    import importlib
    import os
    import sys
    
    modules_dir = os.path.dirname(os.path.abspath(__file__))
    reloaded = []
    errors = []
    
    for filename in os.listdir(modules_dir):
        if filename.startswith('_'):
            continue
        if not filename.endswith('.py'):
            continue
        
        module_name = filename[:-3]
        
        try:
            # Force reimport
            if module_name in sys.modules:
                importlib.reload(sys.modules[f'modules.{module_name}'])
            else:
                importlib.import_module(f'modules.{module_name}')
            
            mod = sys.modules[f'modules.{module_name}']
            if hasattr(mod, 'get_module'):
                module = mod.get_module()
                registry.register(module)
                reloaded.append(module_name)
        except Exception as e:
            errors.append(f"{module_name}: {e}")
    
    update_module_mtimes()
    
    if errors:
        return f"Reloaded: {reloaded}. Errors: {errors}"
    return f"Reloaded modules: {reloaded}"
