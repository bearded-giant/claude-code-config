Quick lookup of feature facts (beta flags, config, endpoints, test commands).

## Arguments

- name: Feature name (or partial match)

## Steps

1. Search .giantmem/features/ for matching feature folder
2. If exact match found, read .giantmem/features/{name}/facts.md
3. If partial match, list matching features and ask for clarification
4. Display the facts.md content
5. If meta.json exists, also show last_session date
