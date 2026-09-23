Hospital Management System (HMS) web application that allows Admins, Doctors, and Patients to interact with the system based on their roles.
# Hospital Management System - V2

## Project Overview

This is a Hospital Management System developed as part of the MAD-II project.
The system allows Admin, Doctor, and Patient to interact with the application for managing hospital operations.

**V2 adds an MCP-integrated AI Assistant** (see below) on top of the original
system. Every original feature — JWT auth, RBAC, REST APIs, Celery/Redis,
Celery Beat — is unchanged.

---

## Technologies Used

* Python (Flask)
* SQLite (Database)
* HTML, CSS (Frontend)
* Redis & Celery (for background jobs)
* **MCP (Model Context Protocol)** + a local, open-source LLM via **Ollama** (AI Assistant)

---

## User Roles

Admin, Doctor, Patients


## How to Run the Project

### 0. Install Redis (needed by Celery, unchanged from V1)

Make sure a local Redis server is running on `localhost:6379` (e.g. `redis-server`).

### 1. Install dependencies

```bash
pip install -r backend/requirements.txt
```

---

### 2. Create database

```bash
python backend/create_db.py
```

---

### 3.  Run Flask application

```bash
cd backend
python app.py
```

---

### 4.  Run Celery Worker (for background jobs)

```bash
cd backend
celery -A app.celery worker --loglevel=info
```

---

### 5.  Run Celery Beat (for scheduled tasks)

```bash
cd backend
celery -A app.celery beat --loglevel=info
```

---

### 6. Set up the AI Assistant (local, open-source LLM — no API key needed)

The AI Assistant uses [Ollama](https://ollama.com) to run a small open-source
model on your own machine, so nothing leaves your computer and there is no
paid API key involved.

```bash
# 1. Install Ollama: https://ollama.com/download

# 2. Pull a small, tool-calling-capable open model (~2GB)
ollama pull llama3.2

# 3. Make sure Ollama is running (it usually auto-starts on install)
ollama serve
```

That's it — as soon as Flask, Redis, Celery and `ollama serve` are running,
the chat bubble in the bottom-right of every dashboard (Admin/Doctor/Patient)
is live. You can point it at a different model with:

```bash
export OLLAMA_MODEL=qwen2.5:3b   # any tool-calling capable Ollama model
export OLLAMA_HOST=http://localhost:11434
```

---

## 🗄️ Database

* Database is created programmatically using `create_db.py`


---

## 📁 Project Structure

```
backend/
  app.py
  models.py
  config.py
  cache_config.py
  celery_config.py
  mail_config.py
  create_db.py
  tasks.py
  mcp_server.py        <- NEW: MCP server exposing hospital data as tools
  ai_assistant.py       <- NEW: Flask blueprint, MCP client + Ollama tool-calling loop
  requirements.txt
  routes/
    __init__.py
    auth.py
    admin.py
    doctor.py
    patient.py
frontend/
  index.html
  register.html
  admin_dashboard.html
  doctor_dashboard.html
  patient_dashboard.html
  assistant_widget.js   <- NEW: floating chat widget included on all 3 dashboards
```

---

## 🎯 Features Implemented

* User authentication (Admin, Doctor, Patient) with JWT + role-based access control
* Appointment management
* Role-based dashboards
* Treatment history tracking
* Async background jobs and scheduled reminders/reports (Celery + Redis + Celery Beat)
* **NEW: MCP-integrated AI Assistant**
  * Natural-language chat widget on every dashboard
  * Backed by a local, open-source LLM (via Ollama) — no external/paid API
  * The LLM decides *when* and *which* MCP tool to call (real tool calling,
    not a hardcoded script)
  * MCP tools query the **same** Flask/SQLAlchemy models and SQLite database
    used by the REST APIs — no duplicate data source
  * Every tool call is executed with the caller's **real, JWT-verified**
    `role`/`user_id`, so a patient's assistant can only ever see that
    patient's data, a doctor's assistant only that doctor's data, etc. —
    the existing RBAC rules are fully respected, never bypassed

---

## 🤖 How the AI Assistant + MCP works

```
Browser (chat widget)
   |  POST /api/assistant/chat   (Authorization: Bearer <JWT>)
   v
Flask (ai_assistant.py)
   |  1. Verifies JWT -> gets REAL role/user_id/username (flask_jwt_extended)
   |  2. Connects to mcp_server.py over MCP (stdio transport)
   |  3. Sends the user's message + the MCP tool list to a local LLM (Ollama)
   |  4. Model replies with either a final answer, or a tool_call request
   |  5. If it's a tool_call: Flask OVERRIDES role/user_id with the
   |     authenticated caller's real values (ignores whatever the model sent)
   |     and calls the tool through the MCP session
   v
mcp_server.py (MCP server)
   |  Tools: get_my_appointments, get_doctor_today_schedule,
   |         search_doctors, get_hospital_overview, list_departments
   |  Queries models.py / db (the SAME database the REST API uses)
   v
Flask returns tool result -> fed back to the LLM -> LLM writes the final
natural-language reply -> returned to the chat widget
```

This demonstrates the full stack requested:
**Flask Backend + JWT/RBAC + REST APIs + MCP + AI Assistant + Tool Calling +
Real-Time Appointment Data + Celery + Redis + Celery Beat.**

---
