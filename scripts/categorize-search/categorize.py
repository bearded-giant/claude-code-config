#!/usr/bin/env python3
"""regex-based categorizer for gl search code CSV results.

deterministic classification for ~80% of rows. rows below confidence
threshold get flagged for llm review.
"""
import csv
import json
import re
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path


# path patterns that indicate test files
TEST_PATH_PATTERNS = re.compile(
    r"(^tests?/|/tests?/|_test\.py$|test_\w+\.py$|_unittest\.py$|"
    r"unittest\.py$|conftest\.py$|/fixture|/spec/|_spec\.py$)",
    re.IGNORECASE,
)

# snippet patterns for classification
IMPORT_PATTERNS = re.compile(
    r"(^from\s+\S+\s+import\s|^import\s+\S|from\s+\S+\s+import\s)"
)
DEFINITION_PATTERNS = re.compile(
    r"(^class\s+\w|^\s*class\s+\w|^def\s+\w|^\s*def\s+\w|"
    r"^\w+\s*=\s*(CacheBustMode|os\.getenv))"
)
CONFIG_ENV_PATTERN = re.compile(
    r'os\.getenv\s*\(\s*["\'].*[Rr][Ee][Dd][Ii][Ss]|'
    r'os\.environ\.get\s*\(\s*["\'].*[Rr][Ee][Dd][Ii][Ss]|'
    r'env_prefix\s*=\s*["\']REDIS'
)
COMMENT_PATTERNS = re.compile(
    r"(^\s*#\s|^\s*//\s|^\s*/\*|^\s*\*\s|"
    r"^This\s+(module|class|utility)|^The\s+(tests?|utility)|"
    r"^Usage:|^Args:|^Attributes:|^Retrieves\s|^Parameterized\s)"
)
LOG_PATTERNS = re.compile(
    r"(logger\.(warning|error|info|debug|exception)\s*\(|"
    r"logging\.(warning|error|info|debug)\s*\(|"
    r'print\s*\(.*[Rr]edis)'
)
SIMPLE_KEY_PATTERNS = re.compile(
    r'(f"[^"]*\{[^}]+\}[^"]*:|'
    r"f'[^']*\{[^}]+\}[^']*:|"
    r'\.format\s*\(.*store_id|'
    r'f"(dropped_event|translate_emails|recharge_segment|segment_sync|klaviyo)'
    r")",
)


def extract_method(snippet: str) -> str:
    """extract the most specific method/function/class name from snippet."""
    # from X import Y
    m = re.search(r"from\s+\S+\s+import\s+(\w+)", snippet)
    if m:
        return m.group(1)

    # import X
    m = re.search(r"^import\s+(\w+)", snippet)
    if m:
        return m.group(1)

    # class Foo
    m = re.search(r"class\s+(\w+)", snippet)
    if m:
        return m.group(1)

    # def foo
    m = re.search(r"def\s+(\w+)", snippet)
    if m:
        return m.group(1)

    # obj.method(
    m = re.search(r"(\w+\.\w+)\s*\(", snippet)
    if m:
        return m.group(1)

    # Foo(
    m = re.search(r"(\w+)\s*\(", snippet)
    if m:
        return m.group(1)

    # CONSTANT = value
    m = re.search(r"^(\w+)\s*=", snippet)
    if m:
        return m.group(1)

    # fallback: first redis-related word
    m = re.search(r"(redis\w*|\w*[Rr]edis\w*)", snippet)
    if m:
        return m.group(1)

    return ""


def classify_row(project: str, filepath: str, snippet: str) -> dict:
    """classify a single row. returns {type, method, confidence}."""
    method = extract_method(snippet)
    stripped = snippet.strip()

    # test files first (highest priority)
    if TEST_PATH_PATTERNS.search(filepath):
        return {"type": "TEST", "method": method, "confidence": 0.95}

    # config files
    is_config_file = filepath.endswith("config.py") or "/config" in filepath
    if is_config_file and CONFIG_ENV_PATTERN.search(snippet):
        return {"type": "CONFIG", "method": method, "confidence": 0.95}
    if is_config_file and "os.getenv" in snippet:
        return {"type": "CONFIG", "method": method, "confidence": 0.90}
    if "/deploy/" in filepath and ("REDIS" in snippet or "redis" in snippet):
        return {"type": "CONFIG", "method": method, "confidence": 0.90}

    # comments and docstrings
    if COMMENT_PATTERNS.search(stripped):
        return {"type": "COMMENT", "method": method, "confidence": 0.90}

    # imports
    if IMPORT_PATTERNS.search(stripped):
        return {"type": "IMPORT", "method": method, "confidence": 0.95}

    # definitions
    if re.search(r"^\s*(class|def)\s+\w+", stripped):
        return {"type": "DEFINITION", "method": method, "confidence": 0.95}

    # constant definitions (REDIS_FOO = CacheBustMode(...))
    if re.search(r"^REDIS_\w+\s*=\s*\w+\(", stripped):
        return {"type": "DEFINITION", "method": method, "confidence": 0.90}

    # log statements
    if LOG_PATTERNS.search(snippet):
        return {"type": "LOG", "method": method, "confidence": 0.85}

    # simple key patterns
    if SIMPLE_KEY_PATTERNS.search(snippet):
        return {"type": "SIMPLE_KEY", "method": method, "confidence": 0.80}

    # config references (not in config files)
    if re.search(r"config\.REDIS_\w+", snippet):
        return {"type": "CONFIG", "method": method, "confidence": 0.85}

    # redis connection/instantiation
    if re.search(r"redis\.Redis\s*\(|Redis\.from_url|redis\.StrictRedis", snippet):
        return {"type": "USAGE", "method": method, "confidence": 0.90}

    # method calls on redis objects
    if re.search(
        r"(self\.redis|redis_client|cache_client|self\._cache)\.\w+\s*\(",
        snippet,
    ):
        return {"type": "USAGE", "method": method, "confidence": 0.85}

    # RedisCache() instantiation
    if re.search(r"RedisCache\(\)", snippet):
        return {"type": "USAGE", "method": method, "confidence": 0.90}

    # skip_redis parameter usage
    if re.search(r"skip_redis\s*=", snippet):
        return {"type": "USAGE", "method": method, "confidence": 0.80}

    # string literals with "redis" (likely config or enum values)
    if re.search(r'["\'].*redis.*["\']', snippet, re.IGNORECASE):
        if is_config_file:
            return {"type": "CONFIG", "method": method, "confidence": 0.80}
        if "Enum" in snippet or "= " in stripped and "redis" in stripped.lower():
            return {"type": "DEFINITION", "method": method, "confidence": 0.75}

    # generic usage patterns
    if re.search(r"self\.\w*redis\w*", snippet):
        return {"type": "USAGE", "method": method, "confidence": 0.75}

    # error handling
    if re.search(r"except\s+.*[Rr]edis|RedisError", snippet):
        return {"type": "USAGE", "method": method, "confidence": 0.80}

    # fallback: low confidence
    return {"type": "USAGE", "method": method, "confidence": 0.50}


def main():
    parser = argparse.ArgumentParser(description="regex-based search result categorizer")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--ambiguous-csv", help="write rows below threshold here")
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--summary", action="store_true", help="print json summary")
    args = parser.parse_args()

    rows = []
    with open(args.input_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    results = []
    ambiguous = []
    for i, row in enumerate(rows):
        cat = classify_row(row["project"], row["file"], row["snippet"])
        result = {
            "row": i + 1,
            "project": row["project"],
            "file": row["file"],
            "line": row["line"],
            "ref": row["ref"],
            "type": cat["type"],
            "method": cat["method"],
            "confidence": cat["confidence"],
            "snippet": row["snippet"],
        }
        results.append(result)
        if cat["confidence"] < args.threshold:
            ambiguous.append(result)

    # write categorized csv
    with open(args.output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["project", "file", "line", "ref", "type", "method", "confidence", "snippet"])
        for r in results:
            writer.writerow([
                r["project"], r["file"], r["line"], r["ref"],
                r["type"], r["method"], r["confidence"], r["snippet"],
            ])

    # write ambiguous rows
    if args.ambiguous_csv and ambiguous:
        with open(args.ambiguous_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["row", "project", "file", "line", "ref", "type", "method", "confidence", "snippet"])
            for r in ambiguous:
                writer.writerow([
                    r["row"], r["project"], r["file"], r["line"], r["ref"],
                    r["type"], r["method"], r["confidence"], r["snippet"],
                ])

    if args.summary:
        type_counts = Counter(r["type"] for r in results)
        conf_buckets = {"high": 0, "medium": 0, "low": 0}
        for r in results:
            if r["confidence"] >= 0.9:
                conf_buckets["high"] += 1
            elif r["confidence"] >= 0.7:
                conf_buckets["medium"] += 1
            else:
                conf_buckets["low"] += 1

        method_counts = defaultdict(lambda: Counter())
        for r in results:
            if r["method"]:
                method_counts[r["method"]][r["type"]] += 1

        top_methods = sorted(method_counts.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]
        top_methods_out = []
        for method, tcounts in top_methods:
            total = sum(tcounts.values())
            breakdown = ", ".join(f"{cnt} {tp}" for tp, cnt in tcounts.most_common())
            top_methods_out.append({"method": method, "total": total, "breakdown": breakdown})

        summary = {
            "total_rows": len(results),
            "types": [{"type": t, "count": c, "pct": round(c / len(results) * 100, 1)}
                      for t, c in type_counts.most_common()],
            "confidence": conf_buckets,
            "ambiguous_count": len(ambiguous),
            "ambiguous_pct": round(len(ambiguous) / len(results) * 100, 1) if results else 0,
            "unique_methods": len(method_counts),
            "top_methods": top_methods_out,
            "output_csv": args.output_csv,
            "ambiguous_csv": args.ambiguous_csv,
        }
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
