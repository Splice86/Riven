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
    """Add test memories using MemoryDB API."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    now = datetime.now(timezone.utc)
    
    # Memory 1: Python programming (recent)
    mem1 = db.add_memory(
        "Learning Python programming with numpy and pandas",
        keywords=["python", "coding", "programming", "numpy", "pandas"],
        properties={"role": "tutorial", "importance": "high"},
        created_at=(now - timedelta(hours=0)).isoformat()
    )
    print(f"  Added memory 1: Python (id={mem1})")
    
    # Memory 2: JavaScript (recent)
    mem2 = db.add_memory(
        "Building React web applications with JavaScript",
        keywords=["javascript", "react", "web", "frontend"],
        properties={"role": "user", "project": "webapp"},
        created_at=(now - timedelta(hours=2)).isoformat()
    )
    print(f"  Added memory 2: JavaScript (id={mem2})")
    
    # Memory 3: Machine learning (older)
    mem3 = db.add_memory(
        "Deep learning with PyTorch and neural networks",
        keywords=["machine-learning", "pytorch", "deep-learning", "neural-networks"],
        properties={"role": "research", "importance": "high"},
        created_at=(now - timedelta(hours=48)).isoformat()
    )
    print(f"  Added memory 3: Machine learning (id={mem3})")
    
    # Memory 4: Deprecated old code (old)
    mem4 = db.add_memory(
        "Old deprecated Python 2 code that needs updating",
        keywords=["python", "deprecated", "old", "python2"],
        properties={"status": "archived"},
        created_at=(now - timedelta(hours=168)).isoformat()  # 1 week ago
    )
    print(f"  Added memory 4: Deprecated (id={mem4})")
    
    # Memory 5: Database (recent)
    mem5 = db.add_memory(
        "PostgreSQL database optimization and indexing",
        keywords=["postgresql", "database", "sql", "optimization"],
        properties={"role": "admin"},
        created_at=(now - timedelta(hours=6)).isoformat()
    )
    print(f"  Added memory 5: Database (id={mem5})")
    
    # Memory 6: Docker (older)
    mem6 = db.add_memory(
        "Docker containerization and Kubernetes deployment",
        keywords=["docker", "kubernetes", "containers", "devops"],
        properties={"role": "devops"},
        created_at=(now - timedelta(hours=72)).isoformat()
    )
    print(f"  Added memory 6: Docker (id={mem6})")
    
    # Memory 7: API development (recent)
    mem7 = db.add_memory(
        "Building REST APIs with FastAPI in Python",
        keywords=["python", "fastapi", "api", "rest"],
        properties={"role": "developer", "project": "backend"},
        created_at=(now - timedelta(hours=4)).isoformat()
    )
    print(f"  Added memory 7: API (id={mem7})")
    
    return [mem1, mem2, mem3, mem4, mem5, mem6, mem7]


def run_tests():
    """Run non-vector search tests."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    
    print("\n" + "=" * 50)
    print("RUNNING NON-VECTOR SEARCH TESTS")
    print("=" * 50)
    
    tests = [
        # Keyword exact match
        ("Keyword - python", "k:python", 3),
        ("Keyword - javascript", "k:javascript", 1),
        
        # Keyword similarity (LIKE fallback)
        ("Similarity - pyth", "s:pyth", 3),
        
        # Boolean operators
        ("AND - python AND coding", "k:python AND k:coding", 1),
        ("OR - python OR javascript", "k:python OR k:javascript", 4),
        ("NOT - NOT deprecated", "NOT k:deprecated", 6),
        
        # Property filters
        ("Property - role=user", "p:role=user", 1),
        ("Property - importance=high", "p:importance=high", 2),
        ("Property - multiple", "p:role=developer AND p:project=backend", 1),
        
        # Content search (LIKE fallback)
        ("Content - Docker", "q:Docker", 1),
        ("Content - neural", "q:neural", 1),
        
        # Date filters
        ("Date - last 24 hours", "d:last 24 hours", 4),
        ("Date - last 7 days", "d:last 7 days", 6),
        
        # Complex queries
        ("Complex - python AND NOT deprecated", "k:python AND NOT k:deprecated", 2),
        ("Complex - (python OR javascript) AND role=user", "k:python OR k:javascript AND p:role=user", 1),
        
        # Date ranges
        ("Date - today", "d:today", 4),
        ("Date - last 3 days", "d:last 3 days", 5),
        
        # Combined
        ("Combined - python AND last 7 days", "k:python AND d:last 7 days", 2),
        ("Combined - docker AND last 3 days", "k:docker AND d:last 3 days", 0),
        
        # Negation with properties
        ("Negation - NOT role=user", "NOT p:role=user", 6),
        
        # Edge cases
        ("Case - k:PYTHON", "k:PYTHON", 3),
        ("Case - p:ROLE=user", "p:ROLE=user", 1),
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
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


def cleanup():
    """Remove test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("✓ Cleanup complete")


def main():
    print("=" * 50)
    print("MEMORYDB SEARCH TESTS (NON-VECTOR)")
    print("=" * 50)
    
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
