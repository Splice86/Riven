#!/usr/bin/env python3
"""Tests for MemoryDB vector search functionality.

These tests require a running embedding model (torch, sentence-transformers).
Run on server after deploying the embedding model.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

TEST_DB = "test_vector.db"


def setup():
    """Create fresh test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from database import init_db
    init_db(TEST_DB)
    print("✓ Database setup complete")


def add_test_data():
    """Add test memories with real embeddings using MemoryDB API."""
    from database import MemoryDB
    from embedding import EmbeddingModel
    
    # Use real embedding model
    emb_model = EmbeddingModel()
    db = MemoryDB(TEST_DB, embedding_model=emb_model)
    now = datetime.now(timezone.utc)
    
    # Memory 1: Python programming
    mem1 = db.add_memory(
        "Learning Python programming with numpy and pandas",
        keywords=["python", "coding", "programming", "numpy", "pandas"],
        properties={"role": "tutorial", "importance": "high"},
        created_at=(now - timedelta(hours=0)).isoformat()
    )
    print(f"  Added memory 1: Python (id={mem1})")
    
    # Memory 2: JavaScript
    mem2 = db.add_memory(
        "Building React web applications with JavaScript",
        keywords=["javascript", "react", "web", "frontend"],
        properties={"role": "user", "project": "webapp"},
        created_at=(now - timedelta(hours=2)).isoformat()
    )
    print(f"  Added memory 2: JavaScript (id={mem2})")
    
    # Memory 3: Machine learning
    mem3 = db.add_memory(
        "Deep learning with PyTorch and neural networks",
        keywords=["machine-learning", "pytorch", "deep-learning", "neural-networks"],
        properties={"role": "research", "importance": "high"},
        created_at=(now - timedelta(hours=48)).isoformat()
    )
    print(f"  Added memory 3: Machine learning (id={mem3})")
    
    # Memory 4: Deprecated old code
    mem4 = db.add_memory(
        "Old deprecated Python 2 code that needs updating",
        keywords=["python", "deprecated", "old", "python2"],
        properties={"status": "archived"},
        created_at=(now - timedelta(hours=168)).isoformat()
    )
    print(f"  Added memory 4: Deprecated (id={mem4})")
    
    # Memory 5: Database
    mem5 = db.add_memory(
        "PostgreSQL database optimization and indexing",
        keywords=["postgresql", "database", "sql", "optimization"],
        properties={"role": "admin"},
        created_at=(now - timedelta(hours=6)).isoformat()
    )
    print(f"  Added memory 5: Database (id={mem5})")
    
    # Memory 6: Docker
    mem6 = db.add_memory(
        "Docker containerization and Kubernetes deployment",
        keywords=["docker", "kubernetes", "containers", "devops"],
        properties={"role": "devops"},
        created_at=(now - timedelta(hours=72)).isoformat()
    )
    print(f"  Added memory 6: Docker (id={mem6})")
    
    # Memory 7: API development
    mem7 = db.add_memory(
        "Building REST APIs with FastAPI in Python",
        keywords=["python", "fastapi", "api", "rest"],
        properties={"role": "developer", "project": "backend"},
        created_at=(now - timedelta(hours=4)).isoformat()
    )
    print(f"  Added memory 7: API (id={mem7})")
    
    return [mem1, mem2, mem3, mem4, mem5, mem6, mem7]


def run_tests():
    """Run vector search tests."""
    from database import MemoryDB
    from embedding import EmbeddingModel
    
    emb_model = EmbeddingModel()
    db = MemoryDB(TEST_DB, embedding_model=emb_model)
    
    print("\n" + "=" * 50)
    print("RUNNING VECTOR SEARCH TESTS")
    print("=" * 50)
    
    # Test keyword similarity with vector search (s: operator)
    tests = [
        # Keyword vector similarity - s: operator
        ("Vector Similarity - programming", "s:programming", 3),
        ("Vector Similarity - webdev", "s:webdev", 2),
        ("Vector Similarity - data", "s:data", 2),
        
        # Content vector similarity - q: operator
        ("Vector Content - machine learning", "q:machine learning", 1),
        ("Vector Content - containers", "q:containers", 1),
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
    print("MEMORYDB VECTOR SEARCH TESTS")
    print("=" * 50)
    print("NOTE: These tests require embedding model (torch)")
    print()
    
    # Check if embedding is available
    try:
        from embedding import EmbeddingModel
        emb = EmbeddingModel()
        test_vec = emb.get("test")
        if test_vec is None or (hasattr(test_vec, 'size') and test_vec.size == 0):
            print("✗ Embedding model not available (returns empty vectors)")
            return 1
    except ImportError as e:
        print(f"✗ Cannot import embedding: {e}")
        return 1
    except Exception as e:
        print(f"✗ Embedding error: {e}")
        return 1
    
    setup()
    add_test_data()
    
    success = run_tests()
    cleanup()
    
    if success:
        print("\n✓ ALL VECTOR TESTS PASSED!")
        return 0
    else:
        print("\n✗ SOME VECTOR TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
