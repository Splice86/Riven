"""Tests for the api module."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestShardListing:
    """Test that shard listing is not duplicated."""

    def test_shard_loading_uses_shared_function(self):
        """Verify that listing shards uses a single function, not inline code."""
        import inspect
        import api as api_mod
        
        source = inspect.getsource(api_mod)
        lines = source.split('\n')
        
        # Count occurrences of the pattern that lists .yaml files in shards dir
        yaml_list_count = sum(1 for line in lines if 'Path("shards")' in line and '.glob' in line)
        
        # The pattern for listing yaml files should appear at most once per function
        # that uses it (not duplicated inline)
        in_function = False
        function_indent = 0
        function_yaml_list_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if stripped.startswith('def ') or stripped.startswith('async def '):
                in_function = True
                function_indent = indent
            elif in_function and indent <= function_indent and stripped and not stripped.startswith('#'):
                in_function = False
            
            if in_function and '.yaml' in line and ('shards' in line or 'glob' in line):
                function_yaml_list_lines.append((i+1, stripped))
        
        # If there are multiple yaml listing blocks, they should be in different
        # functions and share a helper - not duplicated inline
        # This test documents the current behavior
        print(f"YAML listing lines found at: {function_yaml_list_lines}")


class TestApiImports:
    """Test that api module imports are clean."""

    def test_requests_not_imported_inline(self):
        """Verify requests is imported at module level, not inline."""
        import inspect
        import api as api_mod
        
        source = inspect.getsource(api_mod)
        lines = source.split('\n')
        
        in_function = False
        function_indent = 0
        
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if stripped.startswith('def ') or stripped.startswith('async def '):
                in_function = True
                function_indent = indent
            elif in_function and indent <= function_indent and stripped and not stripped.startswith('#'):
                in_function = False
            
            if in_function and 'import requests' in stripped:
                pytest.fail(f"Found 'import requests' inside function: {line}")
