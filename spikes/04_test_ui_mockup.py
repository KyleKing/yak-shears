#!/usr/bin/env python3
"""Spike 4 Validation: Test Metadata UI Mockup.

This script validates that the HTML mockup:
1. Is valid HTML
2. Contains required UI sections
3. Has performance monitoring
4. Has responsive design CSS
"""

import sys
from pathlib import Path


def validate_html_mockup() -> bool:
    """Validate the metadata UI mockup HTML file.

    Returns:
        True if all validation tests pass, False otherwise.
    """
    print("=" * 60)
    print("SPIKE 4: Metadata UI Mockup Validation")
    print("=" * 60)

    mockup_path = Path(__file__).parent / "04_metadata_ui_mockup.html"

    if not mockup_path.exists():
        print("❌ HTML mockup file not found")
        return False

    content = mockup_path.read_text()

    # Test 1: Valid HTML structure
    print("\nTest 1: Valid HTML structure")
    required_tags = ["<!DOCTYPE html>", "<html", "<head>", "<body>", "</html>"]
    for tag in required_tags:
        assert tag in content, f"Missing required tag: {tag}"
    print("  ✅ Contains all required HTML tags")

    # Test 2: Metadata sections
    print("\nTest 2: Metadata panel sections")
    required_sections = [
        "📋 Properties",  # Properties section
        "🔗 Backlinks",   # Backlinks section
        "📊 Statistics",  # Statistics section
    ]
    for section in required_sections:
        assert section in content, f"Missing section: {section}"
    print("  ✅ All metadata sections present")

    # Test 3: Form fields
    print("\nTest 3: Form fields for ticket data model")
    required_fields = [
        'id="type"',      # Type selector
        'id="status"',    # Status selector
        'id="priority"',  # Priority selector
        'id="due"',       # Due date
        'type="date"',    # Date input
    ]
    for field in required_fields:
        assert field in content, f"Missing form field: {field}"
    print("  ✅ All required form fields present")

    # Test 4: Interactive features
    print("\nTest 4: Interactive JavaScript features")
    required_js = [
        "handleFieldChange",  # Field change handler
        "removeTag",          # Tag removal
        "handleTagKeypress",  # Tag addition
        "performance.now()",  # Performance measurement
    ]
    for js_func in required_js:
        assert js_func in content, f"Missing JS feature: {js_func}"
    print("  ✅ All interactive features implemented")

    # Test 5: Responsive design
    print("\nTest 5: Responsive design CSS")
    assert "@media (max-width: 768px)" in content
    assert "grid-template-columns" in content
    assert "grid-template-rows" in content
    print("  ✅ Responsive CSS media queries present")

    # Test 6: Performance monitoring
    print("\nTest 6: Performance monitoring")
    assert "renderTime" in content
    assert "performance-info" in content
    print("  ✅ Performance monitoring implemented")

    # Test 7: Scandinavian design colors
    print("\nTest 7: Scandinavian design system")
    assert "#f5f3ef" in content  # Beige background
    assert "#f7cf46" in content  # Yellow accent
    assert "#d9d4cc" in content  # Border color
    print("  ✅ Design system colors applied")

    # Test 8: Backlinks list
    print("\nTest 8: Backlinks display")
    assert "backlinks-list" in content
    assert "architecture-design.dj" in content
    print("  ✅ Backlinks list implemented")

    print("\n" + "=" * 60)
    print("✅ ALL VALIDATION TESTS PASSED")
    print("=" * 60)

    print("\nTo view the mockup:")
    print(f"  1. Open in browser: file://{mockup_path.absolute()}")
    print("  2. Open browser DevTools (F12) to see console logs")
    print("  3. Resize window to test responsive layout")
    print("  4. Interact with form fields and tags")
    print("\nSuccess Criteria:")
    print("  ✅ Renders in <100ms (check bottom-right corner)")
    print("  ✅ Smooth animations on focus/hover (test with mouse)")
    print("  ✅ Responsive layout (resize browser to <768px)")
    print("  ✅ Interactive updates (check browser console)")
    print("\nNext Steps:")
    print("  • Integrate with HTMX for live updates")
    print("  • Connect to Starlette backend routes")
    print("  • Generate forms dynamically from JSON Schema")
    print("  • Add wikilink autocomplete widget")

    return True


if __name__ == "__main__":
    try:
        success = validate_html_mockup()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)
