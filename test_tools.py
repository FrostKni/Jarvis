#!/usr/bin/env python3
"""Test MCP tools implementation directly"""

import asyncio
import json
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


async def test_tools():
    executor = ToolExecutor()

    print("=" * 80)
    print(f"TOTAL TOOLS REGISTERED: {len(TOOL_DEFINITIONS)}")
    print("=" * 80)

    # List all tools
    print("\n📋 ALL TOOLS:")
    for i, tool in enumerate(TOOL_DEFINITIONS, 1):
        print(f"{i:2}. {tool['name']:30} - {tool['description'][:60]}")

    print("\n" + "=" * 80)
    print("TESTING CRITICAL TOOLS")
    print("=" * 80)

    # Test 1: read_file
    print("\n1️⃣ Testing read_file...")
    result = await executor.execute(
        "read_file", {"path": "/home/kali/Music/Jarvis/README.md", "max_lines": 10}
    )
    print(f"   Result preview: {result[:200]}...")

    # Test 2: list_directory
    print("\n2️⃣ Testing list_directory...")
    result = await executor.execute(
        "list_directory", {"path": "/home/kali/Music/Jarvis"}
    )
    print(f"   Result preview: {result[:200]}...")

    # Test 3: execute_terminal
    print("\n3️⃣ Testing execute_terminal...")
    result = await executor.execute(
        "execute_terminal", {"command": "echo 'Hello from Jarvis'"}
    )
    print(f"   Result: {result}")

    # Test 4: get_datetime
    print("\n4️⃣ Testing get_datetime...")
    result = await executor.execute("get_datetime", {"format": "iso"})
    print(f"   Result: {result}")

    # Test 5: system_info
    print("\n5️⃣ Testing system_info...")
    result = await executor.execute("system_info", {})
    print(f"   Result preview: {result[:200]}...")

    # Test 6: search_files
    print("\n6️⃣ Testing search_files...")
    result = await executor.execute(
        "search_files",
        {
            "directory": "/home/kali/Music/Jarvis/backend",
            "pattern": "*.py",
            "recursive": False,
        },
    )
    print(f"   Result preview: {result[:200]}...")

    # Test tool schema validation
    print("\n" + "=" * 80)
    print("TOOL SCHEMA ANALYSIS")
    print("=" * 80)

    issues = []
    for tool in TOOL_DEFINITIONS:
        schema = tool.get("input_schema", {})

        # Check for required properties
        if "type" not in schema:
            issues.append(f"{tool['name']}: Missing 'type' in input_schema")
        if schema.get("type") != "object":
            issues.append(f"{tool['name']}: input_schema type is not 'object'")
        if "properties" not in schema:
            issues.append(f"{tool['name']}: Missing 'properties' in input_schema")

        # Check if required fields are in properties
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        for req in required:
            if req not in properties:
                issues.append(
                    f"{tool['name']}: Required field '{req}' not in properties"
                )

    if issues:
        print(f"\n❌ Found {len(issues)} schema issues:")
        for issue in issues[:10]:
            print(f"   - {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more")
    else:
        print("\n✅ All tool schemas are valid")

    # Check tool handler coverage
    print("\n" + "=" * 80)
    print("HANDLER COVERAGE")
    print("=" * 80)

    defined_tools = {t["name"] for t in TOOL_DEFINITIONS}
    handler_tools = set(executor._handlers.keys())

    missing_handlers = defined_tools - handler_tools
    extra_handlers = handler_tools - defined_tools

    if missing_handlers:
        print(f"\n⚠️  Tools without handlers ({len(missing_handlers)}):")
        for tool in missing_handlers:
            print(f"   - {tool}")

    if extra_handlers:
        print(f"\n⚠️  Handlers without definitions ({len(extra_handlers)}):")
        for tool in extra_handlers:
            print(f"   - {tool}")

    if not missing_handlers and not extra_handlers:
        print("\n✅ All tools have matching handlers")

    # Test OpenAI function calling format
    print("\n" + "=" * 80)
    print("OPENAI FUNCTION CALLING FORMAT TEST")
    print("=" * 80)

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_DEFINITIONS[:3]  # Test first 3
    ]

    print(f"\nSample OpenAI tool format (first tool):")
    print(json.dumps(openai_tools[0], indent=2))

    # Verify JSON serializable
    try:
        json.dumps(openai_tools)
        print("\n✅ All tools are JSON serializable")
    except Exception as e:
        print(f"\n❌ JSON serialization error: {e}")


if __name__ == "__main__":
    asyncio.run(test_tools())
