"""Tests for the time module."""
import re
from modules.time import _time_context, get_module


def test_time_context_returns_current_time_string():
    """_time_context() returns a properly formatted time string."""
    result = _time_context()
    assert result.startswith("Current time: ")
    # Check format: YYYY-MM-DD HH:MM:SS
    time_part = result.replace("Current time: ", "")
    pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    assert re.match(pattern, time_part), f"Unexpected time format: {time_part}"


def test_get_module_returns_module_with_time_name():
    """get_module() returns a Module with name='time'."""
    module = get_module()
    assert module.name == "time"


def test_get_module_includes_time_context_function():
    """get_module() includes _time_context in context_fns."""
    module = get_module()
    context_fn_tags = [fn.tag for fn in module.context_fns]
    assert "time" in context_fn_tags


def test_get_module_context_fn_returns_time_string():
    """The context function from get_module() returns the current time."""
    module = get_module()
    time_fn = next(fn for fn in module.context_fns if fn.tag == "time")
    result = time_fn.fn()
    assert result.startswith("Current time: ")
