#!/usr/bin/env python3
"""
APK UUID Finder Tool.

Searches decompiled APK source code for GATT UUIDs, command bytes,
and other protocol-related information.

Usage:
    # First decompile with JADX:
    jadx -d labelnize_decompiled labelnize.apk

    # Then run this tool:
    python tools/apk_uuid_finder.py labelnize_decompiled
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# Patterns to search for
UUID_PATTERN = re.compile(
    r'["\']?([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})["\']?'
)
UUID_FROM_STRING = re.compile(r'UUID\.fromString\s*\(\s*["\']([^"\']+)["\']')
HEX_BYTE_PATTERN = re.compile(r'\b0x([0-9a-fA-F]{2})\b')
BYTE_ARRAY_PATTERN = re.compile(r'new\s+byte\s*\[\s*\]\s*\{([^}]+)\}')
COMMAND_PATTERN = re.compile(r'(command|cmd|packet|write|send).*?=.*?(0x[0-9a-fA-F]+|\d+)', re.I)


def find_java_files(directory: Path):
    """Find all Java files in directory."""
    return list(directory.rglob("*.java"))


def search_file(filepath: Path, patterns: dict) -> dict:
    """Search a file for various patterns."""
    results = defaultdict(list)

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return results

    # Find UUIDs
    for match in UUID_PATTERN.finditer(content):
        uuid = match.group(1).lower()
        results["uuids"].append({
            "uuid": uuid,
            "file": str(filepath),
            "context": get_context(content, match.start(), 100)
        })

    # Find UUID.fromString calls
    for match in UUID_FROM_STRING.finditer(content):
        uuid = match.group(1).lower()
        results["uuid_from_string"].append({
            "uuid": uuid,
            "file": str(filepath),
            "context": get_context(content, match.start(), 100)
        })

    # Find command-related assignments
    for match in COMMAND_PATTERN.finditer(content):
        results["commands"].append({
            "match": match.group(0),
            "file": str(filepath),
            "context": get_context(content, match.start(), 150)
        })

    # Find byte arrays
    for match in BYTE_ARRAY_PATTERN.finditer(content):
        bytes_content = match.group(1)
        if HEX_BYTE_PATTERN.search(bytes_content):
            results["byte_arrays"].append({
                "bytes": bytes_content.strip(),
                "file": str(filepath),
                "context": get_context(content, match.start(), 200)
            })

    # Check for printer/BLE-related classes
    if any(term in content.lower() for term in ["bluetoothgatt", "blemanager", "printer", "label", "thermal"]):
        results["relevant_files"].append(str(filepath))

    return results


def get_context(content: str, pos: int, length: int) -> str:
    """Get surrounding context for a match."""
    start = max(0, pos - length // 2)
    end = min(len(content), pos + length // 2)
    context = content[start:end].replace("\n", " ").strip()
    return context


def analyze_results(all_results: dict):
    """Analyze and print results."""
    print("\n" + "=" * 70)
    print("APK ANALYSIS RESULTS")
    print("=" * 70)

    # UUIDs
    uuids = set()
    for r in all_results.get("uuids", []) + all_results.get("uuid_from_string", []):
        uuids.add(r["uuid"])

    print(f"\n{'=' * 70}")
    print(f"FOUND {len(uuids)} UNIQUE UUIDs")
    print("=" * 70)

    # Categorize UUIDs
    standard_uuids = []
    custom_uuids = []

    for uuid in sorted(uuids):
        if uuid.startswith("0000") and uuid.endswith("-0000-1000-8000-00805f9b34fb"):
            standard_uuids.append(uuid)
        else:
            custom_uuids.append(uuid)

    if standard_uuids:
        print("\nStandard Bluetooth UUIDs:")
        for uuid in standard_uuids:
            print(f"  {uuid}")
            print(f"    -> Short form: 0x{uuid[4:8].upper()}")

    if custom_uuids:
        print("\nCustom/Vendor UUIDs (likely printer-specific):")
        for uuid in custom_uuids:
            print(f"  {uuid}")

    # Relevant files
    relevant = set(all_results.get("relevant_files", []))
    if relevant:
        print(f"\n{'=' * 70}")
        print("RELEVANT SOURCE FILES")
        print("=" * 70)
        for f in sorted(relevant):
            print(f"  {f}")

    # Byte arrays (potential protocol data)
    byte_arrays = all_results.get("byte_arrays", [])
    if byte_arrays:
        print(f"\n{'=' * 70}")
        print("BYTE ARRAYS (potential protocol data)")
        print("=" * 70)
        seen = set()
        for ba in byte_arrays[:20]:  # Limit output
            key = ba["bytes"]
            if key not in seen:
                seen.add(key)
                print(f"\n  {ba['bytes']}")
                print(f"  File: {ba['file']}")

    # Commands
    commands = all_results.get("commands", [])
    if commands:
        print(f"\n{'=' * 70}")
        print("COMMAND-RELATED CODE")
        print("=" * 70)
        seen = set()
        for cmd in commands[:30]:  # Limit output
            if cmd["match"] not in seen:
                seen.add(cmd["match"])
                print(f"\n  {cmd['match']}")
                print(f"  File: {cmd['file']}")


def main():
    parser = argparse.ArgumentParser(description="APK UUID Finder")
    parser.add_argument("directory", help="Decompiled APK directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    source_dir = Path(args.directory)
    if not source_dir.exists():
        print(f"Error: Directory not found: {source_dir}")
        sys.exit(1)

    java_files = find_java_files(source_dir)
    print(f"Found {len(java_files)} Java files")

    all_results = defaultdict(list)

    for i, filepath in enumerate(java_files):
        if args.verbose and i % 100 == 0:
            print(f"Processing {i}/{len(java_files)}...")

        results = search_file(filepath, {})
        for key, values in results.items():
            all_results[key].extend(values)

    analyze_results(all_results)

    # Write detailed results to file
    output_file = source_dir / "protocol_findings.txt"
    with open(output_file, "w") as f:
        f.write("APK Protocol Analysis Results\n")
        f.write("=" * 70 + "\n\n")

        f.write("UUIDs Found:\n")
        for r in all_results.get("uuids", []) + all_results.get("uuid_from_string", []):
            f.write(f"  {r['uuid']}\n")
            f.write(f"    File: {r['file']}\n")
            f.write(f"    Context: {r['context']}\n\n")

        f.write("\nByte Arrays:\n")
        for ba in all_results.get("byte_arrays", []):
            f.write(f"  {ba['bytes']}\n")
            f.write(f"    File: {ba['file']}\n\n")

    print(f"\nDetailed results written to: {output_file}")


if __name__ == "__main__":
    main()
