"""Tests for shard loading and management."""

import pytest
import sys
import os
import yaml
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestShardFiles:
    """Test that shard files are valid and non-duplicate."""

    def test_codehammer_shard_exists(self):
        """Verify codehammer shard exists."""
        shard_path = Path(__file__).parent.parent / "shards" / "codehammer.yaml"
        assert shard_path.exists(), "codehammer.yaml should exist"

    def test_default_shard_is_codehammer_alias(self):
        """Verify default.yaml is identical to codehammer.yaml (not a separate shard)."""
        shards_dir = Path(__file__).parent.parent / "shards"
        codehammer_path = shards_dir / "codehammer.yaml"
        default_path = shards_dir / "default.yaml"
        
        if default_path.exists():
            with open(codehammer_path) as f:
                codehammer_content = yaml.safe_load(f)
            with open(default_path) as f:
                default_content = yaml.safe_load(f)
            
            # They should be the same or default should be minimal
            # Check if default has the same system content
            if 'system' in default_content and 'system' in codehammer_content:
                assert default_content['system'] == codehammer_content['system'], \
                    "default.yaml and codehammer.yaml have identical system content - default is redundant"

    def test_shard_has_required_fields(self):
        """Verify shards have required fields."""
        shards_dir = Path(__file__).parent.parent / "shards"
        
        for shard_file in shards_dir.glob("*.yaml"):
            with open(shard_file) as f:
                data = yaml.safe_load(f)
            
            assert "name" in data, f"{shard_file.name} missing 'name' field"
            assert "system" in data, f"{shard_file.name} missing 'system' field"
            assert "modules" in data, f"{shard_file.name} missing 'modules' field"

    def test_shard_no_hardcoded_absolute_paths(self):
        """Verify shards don't have hardcoded absolute paths in debug_dir."""
        shards_dir = Path(__file__).parent.parent / "shards"
        
        for shard_file in shards_dir.glob("*.yaml"):
            with open(shard_file) as f:
                content = f.read()
            
            assert "/home/david/" not in content, \
                f"{shard_file.name} contains hardcoded home directory path"

    def test_shard_magic_numbers_defined(self):
        """Verify magic numbers in shards could be config-driven (informational)."""
        shards_dir = Path(__file__).parent.parent / "shards"
        
        for shard_file in shards_dir.glob("*.yaml"):
            with open(shard_file) as f:
                data = yaml.safe_load(f)
            
            # These are fine to have in shards, but they should ideally be
            # overridable via config.yaml or environment variables
            if "tool_timeout" in data:
                assert isinstance(data["tool_timeout"], int), \
                    f"{shard_file.name}: tool_timeout should be an integer"
            if "max_function_calls" in data:
                assert isinstance(data["max_function_calls"], int), \
                    f"{shard_file.name}: max_function_calls should be an integer"
