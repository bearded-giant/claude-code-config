---
description: Quick lookup of feature facts (beta flags, config keys, endpoints, test commands) from .giantmem/features/{name}/facts.md. Auto-fires before answering "what beta flag is X", "how do I test feature Y", "what's the config key for Z", "where's the endpoint for the W feature", "how do I run the tests for X" — match against features.json before guessing.
---

Quick lookup of feature facts (beta flags, config, endpoints, test commands).

## Arguments

- name: Feature name (or partial match)

## Steps

1. Search .giantmem/features/ for matching feature folder
2. If exact match found, read .giantmem/features/{name}/facts.md
3. If partial match, list matching features and ask for clarification
4. Display the facts.md content
5. If meta.json exists, also show last_session date
