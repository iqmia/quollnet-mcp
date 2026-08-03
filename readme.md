# Quollnet MCP

Minimal standalone MCP server using the official `mcp==2.0.0` SDK.

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

The MCP Streamable HTTP endpoint is `http://127.0.0.1:8000/mcp`.
The health check is `http://127.0.0.1:8000/health`.

Configuration is environment-based. Copy `.env.example` to `.env` and export
the values in your shell before starting Uvicorn.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
