# Starting the Emircom NOC Agent

## One-Command Start (Recommended)

Open PowerShell in the project folder and run:
```powershell
.\start_noc.ps1
```

This automatically:
1. Starts Docker Desktop (if not already running)
2. Starts GLPI containers (mariadb + glpi)
3. Starts the FastAPI backend on port 8001
4. Starts the GLPI Agent worker (polls every 15 seconds)
5. Starts the React frontend on port 5173

Each service opens in its own PowerShell window.

---

## URLs

| Service       | URL                          | Login      |
|---------------|------------------------------|------------|
| NOC Dashboard | http://localhost:5173        | —          |
| GLPI          | http://localhost             | glpi/glpi  |
| API Docs      | http://localhost:8001/docs   | —          |

---

## Push Fresh Mock Tickets

To load new tickets into GLPI for the agent to process:
```powershell
.\venv\Scripts\python.exe glpi\push_to_glpi.py
```

The agent will pick them up within 15 seconds, post AI analysis, set priority, and assign them to the right NOC team.

---

## Manual Start (if needed)

```powershell
# Terminal 1 — Backend
.\venv\Scripts\Activate.ps1
python -m uvicorn react.backend.main:app --port 8001 --reload

# Terminal 2 — GLPI Agent
.\venv\Scripts\Activate.ps1
python glpi\glpi_agent.py

# Terminal 3 — Frontend
cd frontend
npm run dev

# Docker
docker start mariadb
docker start glpi
```
