#!/usr/bin/env python3
"""Tests for MemoryDB link traversal and IF-THEN-ELSE features.

Run on server with:
    cd memory && python3 test_links_if.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

TEST_DB = "test_links_if.db"


def setup():
    """Create fresh test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from database import init_db
    init_db(TEST_DB)
    print("✓ Database setup complete")


def add_link(source_id: int, target_id: int, link_type: str):
    """Add a memory link."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute(
            "INSERT INTO memory_links (source_id, target_id, link_type) VALUES (?, ?, ?)",
            (source_id, target_id, link_type)
        )
        conn.commit()


def add_test_data():
    """Add test memories with links and properties."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    now = datetime.now(timezone.utc)
    
    # Create base memories (the "original" memories to be summarized/linked)
    
    # Memory 1: Python deep dive (old, needs summary)
    mem1 = db.add_memory(
        "Deep dive into Python asyncio for concurrent programming with async/await patterns",
        keywords=["python", "asyncio", "concurrency", "async"],
        properties={"status": "active", "type": "original"},
        created_at=(now - timedelta(days=30)).isoformat()
    )
    print(f"  Added memory 1: {mem1} - Python asyncio (30 days old)")
    
    # Memory 2: JavaScript tutorial (recent, no summary needed)
    mem2 = db.add_memory(
        "Learning JavaScript fundamentals including ES6 features like arrow functions",
        keywords=["javascript", "es6", "fundamentals"],
        properties={"status": "active", "type": "original"},
        created_at=(now - timedelta(days=2)).isoformat()
    )
    print(f"  Added memory 2: {mem2} - JavaScript (2 days old)")
    
    # Memory 3: Machine learning (very old, archived)
    mem3 = db.add_memory(
        "Exploring machine learning with scikit-learn including classification and regression",
        keywords=["machine-learning", "sklearn", "ai"],
        properties={"status": "archived", "type": "original"},
        created_at=(now - timedelta(days=60)).isoformat()
    )
    print(f"  Added memory 3: {mem3} - ML (60 days old)")
    
    # Memory 4: Docker tutorial (recent)
    mem4 = db.add_memory(
        "Docker containerization tutorial covering images, containers, and volumes",
        keywords=["docker", "containers", "devops"],
        properties={"status": "active", "type": "original"},
        created_at=(now - timedelta(days=1)).isoformat()
    )
    print(f"  Added memory 4: {mem4} - Docker (1 day old)")
    
    # Create summaries (linked to original memories)
    
    # Summary 1: Summary of memory 1 (Python asyncio)
    summary1 = db.add_memory(
        "Quick summary: Python asyncio provides async/await for concurrent programming.",
        keywords=["python", "asyncio", "summary"],
        properties={"status": "active", "type": "summary", "is_summary": "true"},
        created_at=(now - timedelta(days=25)).isoformat()
    )
    print(f"  Added summary 1: {summary1} - Summary of Python asyncio")
    add_link(mem1, summary1, "summary_of")
    
    # Summary 2: Summary of memory 3 (Machine learning)
    summary2 = db.add_memory(
        "Quick summary: scikit-learn for ML basics with classification and regression.",
        keywords=["machine-learning", "sklearn", "summary"],
        properties={"status": "archived", "type": "summary", "is_summary": "true"},
        created_at=(now - timedelta(days=50)).isoformat()
    )
    print(f"  Added summary 2: {summary2} - Summary of ML")
    add_link(mem3, summary2, "summary_of")
    
    # Create related links
    add_link(mem2, mem1, "related_to")  # JavaScript related to Python
    add_link(mem4, mem1, "related_to")      # Docker related to Python
    add_link(mem3, mem1, "derived_from")   # ML derived from Python
    
    print(f"  Added links: 2 summaries, 3 related, 1 derived")
    
    return {
        "mem1": mem1, "mem2": mem2, "mem3": mem3, "mem4": mem4,
        "summary1": summary1, "summary2": summary2,
    }


def test_link_traversal():
    """Test link traversal queries."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    ids = add_test_data()
    
    print("\n" + "=" * 60)
    print("TESTING LINK TRAVERSAL (l: prefix)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Direct link by ID
    print("\n--- Direct link by ID ---")
    results = db.search("l:summary_of:" + str(ids["mem1"]))
    print(f"  l:summary_of:{ids['mem1']} → {len(results)} results")
    if len(results) >= 1 and any(r['id'] == ids['summary1'] for r in results):
        print("  ✓ Found summary1")
        passed += 1
    else:
        print("  ✗ Expected summary1")
        failed += 1
    
    results = db.search("l:summary_of:" + str(ids["mem3"]))
    print(f"  l:summary_of:{ids['mem3']} → {len(results)} results")
    if len(results) >= 1 and any(r['id'] == ids['summary2'] for r in results):
        print("  ✓ Found summary2")
        passed += 1
    else:
        print("  ✗ Expected summary2")
        failed += 1
    
    results = db.search("l:summary_of:" + str(ids["mem2"]))
    print(f"  l:summary_of:{ids['mem2']} → {len(results)} (should be 0)")
    if len(results) == 0:
        print("  ✓ Correctly returns 0")
        passed += 1
    else:
        print("  ✗ Expected 0")
        failed += 1
    
    # Test 2: Related links
    print("\n--- Related links ---")
    results = db.search("l:related_to:" + str(ids["mem1"]))
    print(f"  l:related_to:{ids['mem1']} → {len(results)} results")
    if len(results) >= 2:
        print("  ✓ Found related memories")
        passed += 1
    else:
        print("  ✗ Expected at least 2")
        failed += 1
    
    # Test 3: Derived links
    print("\n--- Derived links ---")
    results = db.search("l:derived_from:" + str(ids["mem1"]))
    print(f"  l:derived_from:{ids['mem1']} → {len(results)} results")
    if len(results) >= 1 and any(r['id'] == ids["mem3"] for r in results):
        print("  ✓ Found mem3 (ML)")
        passed += 1
    else:
        print("  ✗ Expected mem3")
        failed += 1
    
    # Test 4: Link with inner query
    print("\n--- Link with inner query ---")
    results = db.search("l:summary_of:(k:python)")
    print(f"  l:summary_of:(k:python) → {len(results)} results")
    if len(results) >= 1:
        print("  ✓ Found summaries of python memories")
        passed += 1
    else:
        print("  ✗ Expected at least 1")
        failed += 1
    
    # Test 5: Any link type
    print("\n--- Any link type ---")
    results = db.search("l:summary_of")
    print(f"  l:summary_of → {len(results)} results")
    if len(results) >= 2:
        print("  ✓ Found all summaries")
        passed += 1
    else:
        print("  ✗ Expected at least 2")
        failed += 1
    
    return passed, failed


def test_if_then_else():
    """Test IF-THEN-ELSE conditional queries."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    
    print("\n" + "=" * 60)
    print("TESTING IF-THEN-ELSE CONDITIONALS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Date-based conditional
    print("\n--- Date-based conditional ---")
    query = "IF d:last 3 days THEN k:python ELSE k:python AND p:is_summary=true"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 2:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 2, got {len(results)}")
        failed += 1
    
    # Test 2: Property-based conditional
    print("\n--- Property-based conditional ---")
    query = "IF p:is_summary=true THEN k:python ELSE p:status=active"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 2:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 2, got {len(results)}")
        failed += 1
    
    # Test 3: Keyword-based conditional
    print("\n--- Keyword-based conditional ---")
    query = "IF k:python THEN k:asyncio ELSE k:javascript"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 1:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 1, got {len(results)}")
        failed += 1
    
    # Test 4: Complex conditional with AND/OR
    print("\n--- Complex conditional ---")
    query = "IF d:last 3 days THEN k:python OR k:javascript ELSE k:python AND p:is_summary=true"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 1:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 1, got {len(results)}")
        failed += 1
    
    # Test 5: Conditional with NOT
    print("\n--- Conditional with NOT ---")
    query = "IF NOT p:status=archived THEN k:python ELSE k:python AND p:is_summary=true"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 1:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 1, got {len(results)}")
        failed += 1
    
    return passed, failed


def test_combined():
    """Test combined link and IF-THEN-ELSE."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    
    print("\n" + "=" * 60)
    print("TESTING COMBINED (LINKS + IF-THEN-ELSE)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    print("\n--- Link with conditional ---")
    query = "IF d:last 3 days THEN l:related_to:(k:python) ELSE l:summary_of:(k:python)"
    results = db.search(query)
    print(f"  {query}")
    print(f"  → {len(results)} results")
    if len(results) >= 1:
        print("  ✓ Found matching memories")
        passed += 1
    else:
        print(f"  ✗ Expected at least 1, got {len(results)}")
        failed += 1
    
    return passed, failed


def test_edge_cases():
    """Test edge cases."""
    from database import MemoryDB
    
    db = MemoryDB(TEST_DB)
    
    print("\n" + "=" * 60)
    print("TESTING EDGE CASES")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    print("\n--- Invalid link type ---")
    results = db.search("l:nonexistent_link:123")
    print(f"  l:nonexistent_link:123 → {len(results)} results")
    if len(results) == 0:
        print("  ✓ Returns 0 for invalid link")
        passed += 1
    else:
        print("  ✗ Should return 0")
        failed += 1
    
    print("\n--- IF without ELSE ---")
    try:
        results = db.search("IF d:last 3 days THEN k:python")
        print(f"  IF without ELSE → {len(results)} results")
        print("  ✓ Parsed without error")
        passed += 1
    except Exception as e:
        print(f"  ✗ Error: {e}")
        failed += 1
    
    return passed, failed


def cleanup():
    """Remove test database."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("\n✓ Cleanup complete")


def main():
    print("=" * 60)
    print("MEMORYDB LINK TRAVERSAL & IF-THEN-ELSE TESTS")
    print("=" * 60)
    print()
    
    setup()
    
    link_passed, link_failed = test_link_traversal()
    if_passed, if_failed = test_if_then_else()
    combined_passed, combined_failed = test_combined()
    edge_passed, edge_failed = test_edge_cases()
    
    total_passed = link_passed + if_passed + combined_passed + edge_passed
    total_failed = link_failed + if_failed + combined_failed + edge_failed
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    print(f"  Link tests: {link_passed} passed, {link_failed} failed")
    print(f"  IF-THEN-ELSE tests: {if_passed} passed, {if_failed} failed")
    print(f"  Combined tests: {combined_passed} passed, {combined_failed} failed")
    print(f"  Edge case tests: {edge_passed} passed, {edge_failed} failed")
    
    cleanup()
    
    if total_failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
