# How to Connect to Your PostgreSQL Database

## Database Connection Details

**From your `.env` file:**
```
Host: localhost
Port: 5433
Database: ai_orchestrator
Username: orchestrator
Password: orchestrator_dev
```

**Connection URL:**
```
postgresql://orchestrator:orchestrator_dev@localhost:5433/ai_orchestrator
```

---

## Option 1: pgAdmin 4 (Best GUI Tool) ⭐

### Download & Install:
1. Download from: https://www.pgadmin.org/download/pgadmin-4-windows/
2. Install pgAdmin 4
3. Open pgAdmin 4

### Connect to Database:
1. **Right-click "Servers"** → **Create** → **Server**
2. **General Tab:**
   - Name: `AI Orchestrator Local`
3. **Connection Tab:**
   - Host name/address: `localhost`
   - Port: `5433`
   - Maintenance database: `postgres`
   - Username: `orchestrator`
   - Password: `orchestrator_dev`
   - ☑️ Save password
4. Click **Save**

### View Your Data:
Navigate to:
```
Servers → AI Orchestrator Local → Databases → ai_orchestrator → Schemas → public → Tables
```

Right-click any table → **View/Edit Data** → **All Rows**

---

## Option 2: DBeaver (Free Universal Database Tool)

### Download & Install:
1. Download from: https://dbeaver.io/download/
2. Install DBeaver Community Edition
3. Open DBeaver

### Connect to Database:
1. Click **New Database Connection** (plug icon)
2. Select **PostgreSQL**
3. Enter connection details:
   - Host: `localhost`
   - Port: `5433`
   - Database: `ai_orchestrator`
   - Username: `orchestrator`
   - Password: `orchestrator_dev`
4. Click **Test Connection**
5. Click **Finish**

### View Your Data:
Expand the connection tree → **Schemas** → **public** → **Tables**
Double-click any table to view data

---

## Option 3: VS Code Extension

### Install PostgreSQL Extension:
1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for: **"PostgreSQL" by Chris Kolkman**
4. Install it

### Connect:
1. Click the PostgreSQL icon in the sidebar
2. Click **+** to add connection
3. Enter details:
   - Host: `localhost`
   - Port: `5433`
   - Database: `ai_orchestrator`
   - Username: `orchestrator`
   - Password: `orchestrator_dev`
4. Browse tables and run queries

---

## Option 4: Command Line (psql)

### Direct Docker Connection:
```powershell
docker exec -it ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator
```

### Common SQL Commands:
```sql
-- List all tables
\dt

-- View table structure
\d workflows

-- Select all workflows
SELECT * FROM workflows LIMIT 10;

-- Select all stages
SELECT * FROM stages;

-- Count records
SELECT COUNT(*) FROM execution_records;

-- Exit
\q
```

---

## Option 5: DataGrip (JetBrains - Paid/Trial)

### If you have JetBrains DataGrip:
1. Open DataGrip
2. Click **+** → **Data Source** → **PostgreSQL**
3. Enter connection details (same as above)
4. Test connection and save

---

## Option 6: Azure Data Studio (Microsoft - Free)

### Download & Install:
1. Download from: https://docs.microsoft.com/en-us/sql/azure-data-studio/download
2. Install Azure Data Studio
3. Install **PostgreSQL extension** from Extensions

### Connect:
1. Click **New Connection**
2. Connection type: **PostgreSQL**
3. Enter details (same as above)

---

## Option 7: TablePlus (Modern GUI - Free/Paid)

### Download & Install:
1. Download from: https://tableplus.com/
2. Install TablePlus
3. Open TablePlus

### Connect:
1. Click **Create a new connection**
2. Select **PostgreSQL**
3. Enter details:
   - Host: `localhost:5433`
   - User: `orchestrator`
   - Password: `orchestrator_dev`
   - Database: `ai_orchestrator`
4. Click **Test** → **Connect**

---

## Quick Python Viewer (Already Created)

Run this to see all your data in the terminal:
```powershell
python view_database.py
```

---

## 🎯 Recommended for Beginners:
1. **pgAdmin 4** - Most popular PostgreSQL tool
2. **DBeaver** - Easier to use, supports many databases
3. **VS Code Extension** - If you prefer staying in VS Code

## 🎯 Recommended for Professionals:
1. **DataGrip** - Best IDE for databases
2. **TablePlus** - Fast and modern
3. **DBeaver** - Feature-rich and free

---

## Troubleshooting

### Cannot connect?
Make sure Docker container is running:
```powershell
docker ps | Select-String "postgres"
```

Start if not running:
```powershell
docker compose up -d postgres
```

### Wrong port?
Check your `.env` file for `POSTGRES_PORT`

### Firewall blocking?
Allow connections on port 5433 in Windows Firewall
