#---
name: code-editing
description: Enforces repository code editing rules for the Python FastAPI AI API.
applyTo: "app/**/*.py"

---

# Code Editing Skill Instructions

> **Note:** This file documents the Code Editing skill for the Python FastAPI AI API.
> It is formatted as a repository-level skill so the agent can discover and apply these
> instructions when asked or when `applyTo` patterns match.

## Best Practices

- Use `async def` for all FastAPI route handlers, service methods, and any function that
  performs I/O (HTTP calls, file reads, etc.).
- Define data contracts with **Pydantic v2** `BaseModel` and `Field(...)` — never pass raw
  dicts across module boundaries.
- Prefer **dependency injection** via FastAPI's `Depends()` for auth, shared services, and config.
- Follow PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_CASE` for module-level constants.
- Use Python type hints on all function signatures and return types.
- Sanitise all external input (HTML, text) before processing or forwarding to Ollama.
- Always review the full context of the code being edited before making any changes.

---

# Rules

### 1. Review Context Before Changing Anything

Before modifying or adding a function, class, or block:

- Read the surrounding code to understand the purpose of the target symbol.
- Check how and where it is called (callers, routers, dependency injections).
- Understand the data flow: what comes in, what goes out, what side effects exist.
- Do **not** proceed until the full context is clear.

### 2. Never Overwrite Existing Code — Comment Then Add

When **modifying** existing code:

- **Comment out** the original code block in place. Do not delete it.
- Use `#` for single-line Python comments.
- Immediately **after** the commented block, write the new code.
- The commented original acts as an in-file diff and historical record.

```python
# ORIGINAL — replaced by: added discount support
# def calculate_total(items: list[dict]) -> float:
#     return sum(item["price"] for item in items)

# UPDATED — now applies optional discount rate
def calculate_total(items: list[dict], discount_rate: float = 0.0) -> float:
    subtotal = sum(item["price"] for item in items)
    return subtotal * (1 - discount_rate)
```

### 3. Document Every Change

Immediately after the new code block, add a change comment that records:

| Field          | Content                                                       |
| -------------- | ------------------------------------------------------------- |
| **Changed by** | Author name or `Copilot`                                      |
| **Date**       | ISO-8601 date (`YYYY-MM-DD`)                                  |
| **Reason**     | One sentence explaining _why_ the change was made             |
| **Impact**     | Side effects, related files touched, or callers affected      |

```python
# CHANGE LOG
# Changed by : Copilot
# Date       : 2026-03-21
# Reason     : Added discount_rate parameter to support promotional pricing.
# Impact     : All callers must pass discount_rate or rely on the default of 0.0
#              (backward compatible). Tests in tests/test_calculate_total.py updated.
```

---

### 4. Add Logs

When modifying code that involves complex logic, external service calls, or side effects,
add logging using Python's `logging` module (not bare `print`):

```python
import logging

logger = logging.getLogger(__name__)

# UPDATED — added structured logging
def calculate_total(items: list[dict], discount_rate: float = 0.0) -> float:
    logger.debug("Calculating total for %d items, discount_rate=%.2f", len(items), discount_rate)
    subtotal = sum(item["price"] for item in items)
    total = subtotal * (1 - discount_rate)
    logger.debug("subtotal=%.2f  total=%.2f", subtotal, total)
    return total
```

During development, `print("DEBUG: ...")` is acceptable but must be replaced with
`logging` before merging to main. **Never log sensitive data** (tokens, emails, full bodies).

---

### 5. Async Code Conventions

All route handlers and service methods must be `async def`. Use `await` for every I/O call.
Never use synchronous blocking calls (`requests`, `time.sleep`) in async contexts.

```python
# ORIGINAL — synchronous, blocks event loop
# def check_ollama_health(base_url: str) -> bool:
#     import requests
#     response = requests.get(f"{base_url}/api/tags")
#     return response.status_code == 200

# UPDATED — fully async using httpx
async def check_ollama_health(base_url: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

# CHANGE LOG
# Changed by : Copilot
# Date       : 2026-03-21
# Reason     : Replace synchronous requests with async httpx to avoid blocking the event loop.
# Impact     : Callers must await this function. Unit tests must use pytest-asyncio.
```

---

### 6. Pydantic v2 Schema Conventions

Always define request/response models with explicit `Field(...)` and type annotations.
Use `field_validator` for input validation.

```python
from pydantic import BaseModel, Field, field_validator

class TranslationRequest(BaseModel):
    '''Request schema for the /api/translate endpoint.'''

    title: str = Field(..., min_length=1, description="Article title to translate")
    body: str = Field(..., min_length=1, description="Article body HTML to translate")
    section: str = Field(..., description="Section label to translate")
    target_language: str = Field(default="Spanish", description="Target language")
    model: str = Field(default="llama3.2", description="Ollama model name")

    @field_validator("title", "body")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank or whitespace only")
        return v
```

---

### 7. Follow Project Conventions

- PEP 8: `snake_case`, 4-space indentation, max line length 100.
- Keep route handlers thin — delegate all business logic to service classes.
- Avoid global mutable state; pass dependencies via `Depends()`.

### 8. Prioritise Security

- Sanitise HTML input before processing (`utils/sanitize_html.py`).
- Validate tokens server-side; never trust client-supplied claims.
- Avoid logging sensitive data (tokens, emails, full HTML bodies).
- Use `async with httpx.AsyncClient(timeout=...)` with explicit timeouts.

### 9. Write a Changelog Entry

Create a new Markdown file in `ChangeLogs/API/` for significant changes. Include:

- **Overview**: What changed and why.
- **Need for change**: The problem or requirement that triggered it.
- **Affected files / functions**: List every file and function touched.
- **Original code**: The commented-out block (copy from the in-file comment).
- **New code**: The replacement block.
- **Test report**: Which tests were added/updated and their results.

---

## Quick Reference Checklist

- [ ] I have read the function/class and its callers.
- [ ] The original code is **commented out**, not deleted.
- [ ] The new code appears **directly after** the commented block.
- [ ] A `# CHANGE LOG` comment is added **after** the new code.
- [ ] Logging uses `logging.getLogger(__name__)` for complex/side-effect logic.
- [ ] All async I/O uses `async def` + `await` with `httpx.AsyncClient`.
- [ ] Pydantic schemas have `Field(...)` with descriptions and validators.
- [ ] A `ChangeLogs/API/<change-name>.md` entry has been written.

---

_Last updated: 2026-03-21_
