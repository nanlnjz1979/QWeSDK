# ClickHouse Query Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize ClickHouse identifier and string-literal construction so user-provided values cannot alter query structure.

**Architecture:** Add a dependency-free `m.db.sql_safety` module with pure quoting helpers. Keep the existing HTTP and CSV layers unchanged, and replace only raw value interpolation in `InputV1`, `ExtractDataV1`, and `SelectorV1`.

**Tech Stack:** Python 3.10+, `unittest`, `requests`, ClickHouse HTTP SQL.

## Global Constraints

- Preserve existing empty-list behavior: `InputV1` may query all rows, while `ExtractDataV1` returns no rows.
- Do not add a database client dependency.
- Raise `ValueError` for invalid identifiers and non-string query values.
- Add concise comments where escaping rules or historical behavior are non-obvious.

### Task 1: Add SQL safety primitives

**Files:**
- Create: `m/db/sql_safety.py`
- Test: `tests/test_sql_safety.py`

**Interfaces:**
- `quote_identifier(value: str, allow_qualified: bool = False) -> str`
- `quote_string(value: str) -> str`
- `quote_string_list(values) -> str`

- [ ] **Step 1: Write the failing tests** for valid identifiers, qualified table names, rejected SQL fragments, escaped literals, and list output.
- [ ] **Step 2: Run `python -m unittest tests.test_sql_safety -v` and confirm failure because the module does not exist.**
- [ ] **Step 3: Implement the three pure helpers with explicit type and grammar checks.**
- [ ] **Step 4: Run the focused test and the existing test suite.**
- [ ] **Step 5: Commit with `git commit -m "feat: add ClickHouse SQL safety helpers"`.**

### Task 2: Replace raw value interpolation

**Files:**
- Modify: `m/input/input_v1.py:223-233`
- Modify: `m/extract_data/extract_data_v1.py:171-182`
- Modify: `m/selector/selector.py:215-230,338-364,427-446`
- Test: `tests/test_sql_safety.py`

**Interfaces:**
- The three modules import the helpers from `m.db.sql_safety` and retain their current private query methods and return types.

- [ ] **Step 1: Add failing query-construction assertions for a value containing a quote and SQL keywords.**
- [ ] **Step 2: Run the focused tests and confirm the assertions fail against the current raw interpolation.**
- [ ] **Step 3: Replace joins and f-strings for stock codes, dates, industries, markets, indexes, and table names with the helper calls.**
- [ ] **Step 4: Add comments explaining why values are quoted separately from fixed SQL syntax.**
- [ ] **Step 5: Run focused tests, all unit tests, `git diff --check`, and Python syntax checks.**
- [ ] **Step 6: Commit with `git commit -m "fix: harden ClickHouse query construction"`.**
