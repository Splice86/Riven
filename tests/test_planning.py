"""Tests for the planning module."""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPlanningImports:
    """Test that planning module has correct imports at module level."""

    def test_os_imported_at_module_level(self):
        """Verify os is imported at module level, not inside functions."""
        import modules.planning as planning_mod
        import inspect
        source = inspect.getsource(planning_mod)
        
        lines = source.split('\n')
        in_function = False
        function_indent = 0
        
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            # Detect function definition
            if stripped.startswith('def ') or stripped.startswith('async def '):
                in_function = True
                function_indent = indent
            elif in_function and indent <= function_indent and stripped and not stripped.startswith('#'):
                in_function = False
            
            # import os inside functions is bad
            if in_function and 'import os' in stripped:
                pytest.fail(f"Found 'import os' inside function: {line}")


class TestGetGoalFiles:
    """Test _get_goal_files utility function."""

    def test_parses_valid_json_files_list(self):
        """Test parsing of valid JSON files list."""
        from modules.planning import _get_goal_files
        
        goal = {
            "properties": {
                "files": '["/path/to/file1.py", "/path/to/file2.py"]'
            }
        }
        files = _get_goal_files(goal)
        assert files == ["/path/to/file1.py", "/path/to/file2.py"]

    def test_parses_empty_files_list(self):
        """Test parsing of empty JSON files list."""
        from modules.planning import _get_goal_files
        
        goal = {"properties": {"files": "[]"}}
        files = _get_goal_files(goal)
        assert files == []

    def test_handles_missing_files_property(self):
        """Test handling when files property is missing."""
        from modules.planning import _get_goal_files
        
        goal = {"properties": {}}
        files = _get_goal_files(goal)
        assert files == []

    def test_handles_invalid_json(self):
        """Test handling of invalid JSON in files property."""
        from modules.planning import _get_goal_files
        
        goal = {"properties": {"files": "not valid json ["}}
        files = _get_goal_files(goal)
        assert files == []


class TestCreateGoal:
    """Test create_goal function."""

    @pytest.mark.asyncio
    async def test_create_goal_with_minimal_args(self, mock_memory_api, mock_config_singleton):
        """Test creating a goal with just a title."""
        from modules import _session_id
        from modules.planning import create_goal
        
        _session_id.set("test-session-123")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 42, "content": "Goal: Test Goal"}
        mock_memory_api.post.return_value = mock_resp
        
        result = await create_goal(title="Test Goal")
        
        assert "42" in result
        assert "Test Goal" in result
        mock_memory_api.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_goal_with_priority(self, mock_memory_api, mock_config_singleton):
        """Test creating a goal with priority."""
        from modules import _session_id
        from modules.planning import create_goal
        
        _session_id.set("test-session-123")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "content": "Goal: High Priority Task"}
        mock_memory_api.post.return_value = mock_resp
        
        result = await create_goal(title="High Priority Task", priority="high")
        
        # Check that the request included priority in properties
        call_args = mock_memory_api.post.call_args
        json_data = call_args[1]['json']
        assert json_data['properties']['priority'] == 'high'

    @pytest.mark.asyncio
    async def test_create_goal_invalid_priority_defaults_to_medium(self, mock_memory_api, mock_config_singleton):
        """Test that invalid priority defaults to medium."""
        from modules import _session_id
        from modules.planning import create_goal
        
        _session_id.set("test-session-123")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "content": "Goal: Test"}
        mock_memory_api.post.return_value = mock_resp
        
        result = await create_goal(title="Test", priority="invalid")
        
        call_args = mock_memory_api.post.call_args
        json_data = call_args[1]['json']
        assert json_data['properties']['priority'] == 'medium'


class TestAddFileToGoal:
    """Test add_file_to_goal function."""

    @pytest.mark.asyncio
    async def test_add_file_to_existing_goal(self, mock_memory_api, mock_config_singleton):
        """Test adding a file to an existing goal."""
        from modules import _session_id
        from modules.planning import add_file_to_goal
        
        _session_id.set("test-session-123")
        
        # Mock GET returning existing goal
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": 1,
            "content": "Goal: Test",
            "properties": {"files": "[]", "status": "active", "priority": "medium"}
        }
        
        # Mock PUT for update
        put_resp = MagicMock()
        put_resp.status_code = 200
        put_resp.json.return_value = {"id": 1}
        
        mock_memory_api.get.return_value = get_resp
        mock_memory_api.put.return_value = put_resp
        
        result = await add_file_to_goal(1, "/tmp/test_file.py")
        
        assert "test_file.py" in result
        mock_memory_api.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_file_already_linked(self, mock_memory_api, mock_config_singleton):
        """Test adding a file that's already linked."""
        from modules import _session_id
        from modules.planning import add_file_to_goal
        
        _session_id.set("test-session-123")
        
        # Mock GET returning goal with file already linked
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": 1,
            "content": "Goal: Test",
            "properties": {
                "files": json.dumps(["/tmp/test_file.py"]),
                "status": "active",
                "priority": "medium"
            }
        }
        mock_memory_api.get.return_value = get_resp
        
        result = await add_file_to_goal(1, "/tmp/test_file.py")
        
        assert "already linked" in result.lower()
        mock_memory_api.put.assert_not_called()


class TestUpdateGoalStatus:
    """Test update_goal_status function."""

    @pytest.mark.asyncio
    async def test_valid_status_update(self, mock_memory_api, mock_config_singleton):
        """Test updating goal status with valid status."""
        from modules import _session_id
        from modules.planning import update_goal_status
        
        _session_id.set("test-session-123")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_memory_api.put.return_value = mock_resp
        
        result = await update_goal_status(1, "complete")
        
        assert "complete" in result
        call_args = mock_memory_api.put.call_args
        assert call_args[1]['json']['properties']['status'] == 'complete'

    @pytest.mark.asyncio
    async def test_invalid_status_returns_error(self, mock_memory_api, mock_config_singleton):
        """Test that invalid status returns error."""
        from modules import _session_id
        from modules.planning import update_goal_status
        
        _session_id.set("test-session-123")
        
        result = await update_goal_status(1, "invalid_status")
        
        assert "[ERROR]" in result
        mock_memory_api.put.assert_not_called()


class TestCloseGoal:
    """Test close_goal function."""

    @pytest.mark.asyncio
    async def test_close_goal_calls_update_status(self, mock_memory_api, mock_config_singleton):
        """Test that close_goal delegates to update_goal_status."""
        from modules import _session_id
        from modules.planning import close_goal
        
        _session_id.set("test-session-123")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_memory_api.put.return_value = mock_resp
        
        result = await close_goal(1)
        
        assert "complete" in result
        mock_memory_api.put.assert_called_once()
