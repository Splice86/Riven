#!/usr/bin/env python3
"""Tests for MemoryDB search functionality (non-vector)."""

import os
import sys
from datetime import datetime, timedelta, timezone

TEST_DB = "test_memory.db"


def setup():
    """Create fresh test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from database import init_db
    init_db(TEST_DB)
    print("✓ Database setup complete")


def add_test_data():
    """Add LOTS of test memories using MemoryDB API."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    now = datetime.now(timezone.utc)
    
    # Recent (0-6 hours)
    db.add_memory(
        "Learning Python programming with numpy and pandas",
        keywords=["python", "coding", "programming", "numpy", "pandas"],
        properties={"role": "tutorial", "importance": "high", "status": "active"},
        created_at=(now - timedelta(hours=0)).isoformat()
    )
    db.add_memory(
        "Building React web applications with JavaScript",
        keywords=["javascript", "react", "web", "frontend"],
        properties={"role": "user", "project": "webapp", "status": "active"},
        created_at=(now - timedelta(hours=1)).isoformat()
    )
    db.add_memory(
        "PostgreSQL database optimization and indexing",
        keywords=["postgresql", "database", "sql", "optimization", "indexing"],
        properties={"role": "admin", "priority": "high", "status": "active"},
        created_at=(now - timedelta(hours=2)).isoformat()
    )
    db.add_memory(
        "Building REST APIs with FastAPI in Python",
        keywords=["python", "fastapi", "api", "rest", "backend"],
        properties={"role": "developer", "project": "backend", "status": "active"},
        created_at=(now - timedelta(hours=3)).isoformat()
    )
    db.add_memory(
        "Debugging memory leaks in Node.js applications",
        keywords=["javascript", "nodejs", "debugging", "memory", "performance"],
        properties={"role": "support", "priority": "critical", "status": "active"},
        created_at=(now - timedelta(hours=4)).isoformat()
    )
    db.add_memory(
        "Writing unit tests with pytest and mock",
        keywords=["python", "testing", "pytest", "mock", "unittest"],
        properties={"role": "developer", "status": "active"},
        created_at=(now - timedelta(hours=5)).isoformat()
    )
    
    # Medium age (12-48 hours)
    db.add_memory(
        "Deep learning with PyTorch and neural networks",
        keywords=["machine-learning", "pytorch", "deep-learning", "neural-networks", "ai"],
        properties={"role": "research", "importance": "high", "status": "active"},
        created_at=(now - timedelta(hours=24)).isoformat()
    )
    db.add_memory(
        "Docker containerization and Kubernetes deployment",
        keywords=["docker", "kubernetes", "containers", "devops", "orchestration"],
        properties={"role": "devops", "status": "active"},
        created_at=(now - timedelta(hours=36)).isoformat()
    )
    db.add_memory(
        "Setting up CI/CD pipelines with GitHub Actions",
        keywords=["cicd", "github", "automation", "devops"],
        properties={"role": "devops", "project": "infrastructure", "status": "active"},
        created_at=(now - timedelta(hours=30)).isoformat()
    )
    db.add_memory(
        "GraphQL API design and implementation",
        keywords=["graphql", "api", "backend", "schema"],
        properties={"role": "developer", "project": "api", "status": "active"},
        created_at=(now - timedelta(hours=28)).isoformat()
    )
    
    # Older (72+ hours)
    db.add_memory(
        "Old deprecated Python 2 code that needs updating",
        keywords=["python", "python2", "deprecated", "legacy", "migration"],
        properties={"role": "maintenance", "status": "archived", "priority": "low"},
        created_at=(now - timedelta(hours=168)).isoformat()
    )
    db.add_memory(
        "Redis caching strategies for high traffic",
        keywords=["redis", "cache", "performance", "optimization"],
        properties={"role": "architect", "status": "active"},
        created_at=(now - timedelta(hours=72)).isoformat()
    )
    db.add_memory(
        "WebSocket real-time communication implementation",
        keywords=["websocket", "realtime", "javascript", "api"],
        properties={"role": "developer", "status": "active"},
        created_at=(now - timedelta(hours=60)).isoformat()
    )
    db.add_memory(
        "OAuth 2.0 authentication flow implementation",
        keywords=["oauth", "authentication", "security", "jwt"],
        properties={"role": "security", "status": "active"},
        created_at=(now - timedelta(hours=84)).isoformat()
    )
    
    # Even older (1+ week)
    db.add_memory(
        "Legacy PHP application from 2019",
        keywords=["php", "legacy", "old", "migration", "web"],
        properties={"role": "maintenance", "status": "archived", "priority": "low"},
        created_at=(now - timedelta(hours=200)).isoformat()
    )
    db.add_memory(
        "MongoDB schema design for analytics",
        keywords=["mongodb", "database", "nosql", "analytics", "schema"],
        properties={"role": "architect", "status": "active"},
        created_at=(now - timedelta(hours=120)).isoformat()
    )
    db.add_memory(
        "AWS Lambda serverless function optimization",
        keywords=["aws", "lambda", "serverless", "cloud", "optimization"],
        properties={"role": "devops", "status": "active"},
        created_at=(now - timedelta(hours=96)).isoformat()
    )
    
    print(f"  Added 19 memories")


def run_tests():
    """Run non-vector search tests."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    
    print("\n" + "=" * 60)
    print("RUNNING NON-VECTOR SEARCH TESTS")
    print("=" * 60)
    
    tests = [
        # BASIC KEYWORD TESTS
        ("Keyword - python", "k:python", 4),
        ("Keyword - javascript", "k:javascript", 3),
        ("Keyword - database", "k:database", 2),  # postgresql, mongodb
        ("Keyword - docker", "k:docker", 1),
        
        # KEYWORD SIMILARITY (LIKE fallback)
        ("Similarity - py", "s:py", 5),  # includes python, python2, pytorch, etc
        ("Similarity - jav", "s:jav", 3),
        
        # BOOLEAN OPERATORS
        ("AND - python AND coding", "k:python AND k:coding", 1),
        ("AND - python AND api", "k:python AND k:api", 1),  # FastAPI memory only
        ("OR - python OR javascript", "k:python OR k:javascript", 7),
        ("OR - docker OR kubernetes", "k:docker OR k:kubernetes", 1),
        ("NOT - NOT deprecated", "NOT k:deprecated", 16),
        
        # PROPERTY FILTERS
        ("Property - role=user", "p:role=user", 1),
        ("Property - role=developer", "p:role=developer", 4),
        ("Property - importance=high", "p:importance=high", 2),
        ("Property - status=active", "p:status=active", 15),
        ("Property - status=archived", "p:status=archived", 2),
        ("Property - priority=critical", "p:priority=critical", 1),
        
        # Multiple properties
        ("Multi prop - role=developer AND status=active", "p:role=developer AND p:status=active", 4),
        ("Multi prop - role=devops AND status=active", "p:role=devops AND p:status=active", 3),
        
        # CONTENT SEARCH (LIKE)
        ("Content - FastAPI", "q:FastAPI", 1),
        ("Content - Kubernetes", "q:Kubernetes", 1),
        ("Content - neural", "q:neural", 1),
        ("Content - pytest", "q:pytest", 1),
        ("Content - OAuth", "q:OAuth", 1),
        
        # DATE FILTERS
        ("Date - last 6 hours", "d:last 6 hours", 6),
        ("Date - last 12 hours", "d:last 12 hours", 6),
        ("Date - last 24 hours", "d:last 24 hours", 6),
        ("Date - last 48 hours", "d:last 48 hours", 10),
        ("Date - last 72 hours", "d:last 72 hours", 11),
        ("Date - today", "d:today", 6),
        
        # CRAZY COMPLEX QUERIES
        
        # Triple combinations
        ("Triple - python AND coding AND active", "k:python AND k:coding AND p:status=active", 1),
        ("Triple - javascript AND web AND role=user", "k:javascript AND k:web AND p:role=user", 1),
        
        # Multiple OR with AND
        ("Complex - (python OR javascript) AND devops", "(k:python OR k:javascript) AND p:role=devops", 0),
        ("Complex - (api OR graphql) AND backend", "(k:api OR k:graphql) AND p:backend=backend", 0),  # p:backend not stored
        
        # NOT with multiple conditions
        ("NOT - NOT deprecated AND active", "NOT k:deprecated AND p:status=active", 15),
        ("NOT - NOT role=user AND importance", "NOT p:role=user AND p:importance=high", 2),
        
        # Property + Date
        ("Prop+Date - role=developer AND last 24", "p:role=developer AND d:last 24 hours", 2),
        ("Prop+Date - status=archived AND last 30 days", "p:status=archived AND d:last 30 days", 2),
        
        # Keyword + Date
        ("Kw+Date - python AND last 48 hours", "k:python AND d:last 48 hours", 3),
        ("Kw+Date - javascript AND last 24 hours", "k:javascript AND d:last 24 hours", 2),
        
        # Keyword + Property + Date
        ("All three - python AND status=active AND last 48", "k:python AND p:status=active AND d:last 48 hours", 3),
        
        # Nested NOT
        ("Nested NOT - NOT (python OR javascript)", "NOT (k:python OR k:javascript)", 10),
        ("Nested NOT - NOT (deprecated OR legacy)", "NOT (k:deprecated OR k:legacy)", 15),
        
        # Double negation
        ("Double NOT - NOT NOT python", "NOT NOT k:python", 4),
        
        # Empty/edge case queries
        ("Empty - nonexistent keyword", "k:nonexistent", 0),
        ("Empty - nonexistent property", "p:nonexistent=value", 0),
        
        # Case insensitivity
        ("Case - PYTHON", "k:PYTHON", 4),
        ("Case - JAVASCRIPT", "k:JAVASCRIPT", 3),
        ("Case - role=user", "p:role=user", 1),  # key is lowercased
        
        # OR with NOT
        ("OR NOT - python OR NOT javascript", "k:python OR NOT k:javascript", 14),
        
        # Priority queries
        ("Priority - critical", "p:priority=critical", 1),
        ("Priority - low", "p:priority=low", 2),
        
        # Project queries
        ("Project - webapp", "p:project=webapp", 1),
        ("Project - backend", "p:project=backend", 1),
        ("Project - infrastructure", "p:project=infrastructure", 1),
        
        # Very recent only
        ("Very recent - last 2 hours", "d:last 2 hours", 2),
        
        # Long range
        ("Long range - last 14 days", "d:last 14 days", 17),
        
        # Content + keyword combo
        ("Content+Keyword - q:pytest AND k:testing", "q:pytest AND k:testing", 1),
        
        # Deeply nested
        ("Deep nesting", "(k:python OR k:javascript) AND (k:api OR k:web) AND p:status=active", 3),
        
        # Mixed operators
        ("Mixed - python OR javascript AND testing", "k:python OR k:javascript AND k:testing", 1),
        
        # Zero result edge cases
        ("Zero - old keyword AND recent date", "k:python2 AND d:last 1 hours", 0),
        
        # All properties
        ("All - NOT deprecated AND active AND recent", "NOT k:deprecated AND p:status=active AND d:last 24 hours", 6),
    ]
    
    passed = 0
    failed = 0
    
    for name, query, expected in tests:
        results = db.search(query)
        actual = len(results)
        
        if actual == expected:
            print(f"✓ {name}")
            passed += 1
        else:
            print(f"✗ {name}: got {actual}, expected {expected}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def cleanup():
    """Remove test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("✓ Cleanup complete")


def main():
    print("=" * 60)
    print("MEMORYDB SEARCH TESTS (NON-VECTOR) - EXPANDED")
    print("=" * 60)
    
    setup()
    add_test_data()
    
    success = run_tests()
    cleanup()
    
    if success:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
