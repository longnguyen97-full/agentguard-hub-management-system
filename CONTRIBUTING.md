# Contributing to Agent Observability & Management System

Thank you for your interest in contributing to the project! We welcome contributions of all kinds: bug fixes, new guardrails, dashboard UI enhancements, SDK improvements, documentation updates, and test additions.

---

## 🛠️ Local Development Setup

We use [`uv`](https://github.com/astral-sh/uv) as the fast, reliable package and environment manager.

### 1. Prerequisites
- Python >= 3.11
- `uv` installed ([Install guide](https://docs.astral.sh/uv/getting-started/installation/))
- Docker & Docker Compose (optional, required if you want full Langfuse tracing)

### 2. Clone and Setup
```bash
git clone https://github.com/longnguyen97-full/agent-management-system.git
cd agent-management-system

# Sync dependencies and create virtual environment
uv sync --all-groups
```

### 3. Run the Backend and Dashboard
```bash
uv run run.py
```
Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard) in your browser.

---

## 🧪 Running Tests

Ensure all automated tests pass before submitting a Pull Request:

```bash
uv run pytest -v
```

All 6 test suites cover:
- Standard multi-step agent reasoning & tool execution
- Loop detector guardrail
- Token & USD budget limits
- Human-in-the-Loop approval workflows
- Emergency kill switch
- External agent SDK ingestion lifecycle

---

## 🌿 Contribution Guidelines

1. **Fork the repository** on GitHub.
2. **Create a feature branch**:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```
3. **Commit your changes**:
   Write clear, semantic commit messages (e.g. `feat: add slack webhook alert on kill switch`, `fix: handle edge case in loop detector`).
4. **Add tests**:
   If adding a new guardrail or route, provide unit/integration tests in `tests/`.
5. **Push and Open a Pull Request**:
   Describe what changed and why. Reference any related issues.

---

## 💬 Community & Questions

Feel free to open an issue or start a GitHub Discussion if you have design ideas or questions.
