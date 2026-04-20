"""Tests for GOAL 2: dead code removal.

These tests verify behaviors that should NOT change when we remove dead code.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSanitizeMessagesLegacyParsing:
    """Verify legacy tool message parsing is NOT active.

    The legacy code handled "func_name: result" format in content field
    when name was None. This is dead code - new storage uses 'function' property.
    """

    def test_sanitize_does_not_extract_name_from_content_with_colon(self):
        """Tool messages with colon in content and name already set should not be modified."""
        from context import ContextManager

        # Simulate what comes back from memory: a tool message with name already set
        # and content that happens to have a colon (like a path "C:\Users\...")
        messages = [
            {
                "role": "tool",
                "content": "C:\\Users\\test\\file.py: line 42",
                "tool_call_id": "call_abc123",
                "name": "read_file",  # name is already set from 'function' property
            }
        ]

        ctx = ContextManager(memory_url="http://localhost:8030")
        result = ctx.sanitize_messages_for_llm(messages)

        assert result[0]["name"] == "read_file"
        # The content should NOT be split at the colon
        assert result[0]["content"] == "C:\\Users\\test\\file.py: line 42"

    def test_sanitize_does_not_split_content_with_colon_when_name_is_set(self):
        """Verify legacy 'func_name: result' parsing does not fire when name is set."""
        from context import ContextManager

        messages = [
            {
                "role": "tool",
                "content": "read_file: some result content",
                "tool_call_id": "call_abc",
                "name": "some_other_name",
            }
        ]

        ctx = ContextManager(memory_url="http://localhost:8030")
        result = ctx.sanitize_messages_for_llm(messages)

        # name should stay as-is, NOT be overwritten
        assert result[0]["name"] == "some_other_name"
        # content should stay intact, NOT be split
        assert result[0]["content"] == "read_file: some result content"


class TestPrepareMessagesNoOriginalLenLeak:
    """Verify prepare_messages_for_llm does not leave 'original_len' in messages."""

    def test_truncated_tool_message_has_no_original_len_field(self):
        """Truncated tool messages should not have original_len in output."""
        from context import MemoryClient, ContextManager

        # Create a long tool result that will be truncated
        long_content = "\n".join([f"line {i}: {'x' * 100}" for i in range(300)])

        history = [
            {
                "role": "tool",
                "content": long_content,
                "tool_call_id": "call_abc123",
                "function": "read_file",
            }
        ]

        ctx = ContextManager(
            memory_url="http://localhost:8030",
            tool_result_max_lines=200,
            tool_result_char_per_line=150,
        )

        with patch.object(ctx, 'build_system_prompt', return_value=''):
            messages, _ = ctx.prepare_messages_for_llm(history, '', MagicMock())

        tool_msg = messages[0]
        assert "original_len" not in tool_msg
        assert tool_msg["role"] == "tool"
        assert "[TRUNCATED" in tool_msg["content"]
