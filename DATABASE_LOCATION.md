# 📍 Where Your PostgreSQL Database Actually Is

## 🗄️ Physical Database Files Location

Your PostgreSQL database files are stored in a **Docker Volume**:

### Docker Volume Information:
- **Volume Name**: `pblaiorchestrator_postgres_data`
- **Internal Path**: `/var/lib/docker/volumes/pblaiorchestrator_postgres_data/_data`
- **Windows Path**: This is inside Docker's WSL2 virtual disk

### Access the Physical Files:

#### Option A: Through Docker Desktop
1. Open **Docker Desktop**
2. Go to **Volumes** tab in the sidebar
3. Find: `pblaiorchestrator_postgres_data`
4. Click on it to see the actual database files

#### Option B: Through WSL2 (if using Docker with WSL2)
```powershell
# Access the Docker volume in WSL2
wsl -d docker-desktop
cd /var/lib/docker/volumes/pblaiorchestrator_postgres_data/_data
ls -la
```

#### Option C: Through Docker Command
```powershell
# Browse database files
docker exec -it ai_orchestrator_postgres ls -la /var/lib/postgresql/data

# Copy database files to your Windows directory (backup)
docker cp ai_orchestrator_postgres:/var/lib/postgresql/data E:\PBL_AI_Orchestrator\db_backup
```

---

## 🔌 How to Access the DATABASE (Not Files, But Actual Data)

### ✅ EASIEST METHOD: pgAdmin 4

**Download**: https://www.pgadmin.org/download/pgadmin-4-windows/

**Connection Details**:
```
Host:     localhost
Port:     5433
Database: ai_orchestrator
User:     orchestrator
Password: orchestrator_dev
```

**Steps**:
1. Install pgAdmin 4
2. Open it
3. Right-click "Servers" → Create → Server
4. Enter the connection details above
5. Browse your tables with a nice GUI!

---

### ✅ SECOND EASIEST: DBeaver (Free)

**Download**: https://dbeaver.io/download/

**Why DBeaver?**
- ✨ Beautiful, modern interface
- 🆓 Completely free
- 🚀 Easy to use
- 📊 Great data visualization

**Steps**:
1. Install DBeaver Community
2. Click "New Database Connection" (plug icon)
3. Select PostgreSQL
4. Enter connection details
5. Start browsing!

---

### ✅ INSIDE VS CODE: PostgreSQL Extension

**Extension Name**: "PostgreSQL" by Chris Kolkman

**Steps**:
1. In VS Code, press `Ctrl+Shift+X`
2. Search: "PostgreSQL"
3. Install it
4. Click PostgreSQL icon in sidebar
5. Add connection with your details
6. Browse database without leaving VS Code!

---

## 🎯 Quick Commands to View Data RIGHT NOW

### Via Python (Already Set Up):
```powershell
cd "E:\PBL AI Orchestrator"
python view_database.py
```
This shows ALL your data in the terminal!

### Via Docker Command Line:
```powershell
# Connect to PostgreSQL
docker exec -it ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator

# Once connected, run SQL commands:
SELECT * FROM workflows;
SELECT * FROM stages;
SELECT * FROM execution_records;

# Type \q to exit
```

---

## 📊 Your Database Structure

Based on the actual data in your database:

```
ai_orchestrator (Database)
│
├── workflows (25 records)
│   ├── Pipeline Implementation
│   ├── Binary Search Examples
│   ├── Data Processing Workflows
│   └── UI Development Tasks
│
├── stages (46 records)
│   ├── Analysis stages
│   ├── Generation stages
│   ├── Testing stages
│   └── Design stages
│
├── execution_records (46 records)
│   ├── Using Groq API (qwen, gpt-oss)
│   ├── Cost tracking
│   └── Token usage
│
├── cache_entries (39 records)
│   └── Semantic cache with embeddings
│
├── model_profiles (4 records)
│   └── AI model configurations
│
└── Other tables...
```

---

## 🚀 What I Recommend

### For Quick Viewing:
```powershell
python view_database.py
```

### For Serious Database Work:
1. **Install pgAdmin 4** (industry standard for PostgreSQL)
2. **Or install DBeaver** (easier, prettier)

### For Staying in VS Code:
Install the PostgreSQL extension

---

## 🔧 Your Database Container Info

**Container Name**: `ai_orchestrator_postgres`
**Image**: `pgvector/pgvector:pg15`
**Port Mapping**: `5433 (your PC) → 5432 (container)`

### Check if Database is Running:
```powershell
docker ps | Select-String "postgres"
```

### Start Database:
```powershell
cd "E:\PBL AI Orchestrator"
docker compose up -d postgres
```

### Stop Database:
```powershell
docker compose down postgres
```

### View Database Logs:
```powershell
docker logs ai_orchestrator_postgres
```

---

## 💾 Backup Your Database

### Create a Backup:
```powershell
docker exec -t ai_orchestrator_postgres pg_dump -U orchestrator ai_orchestrator > E:\PBL_AI_Orchestrator\backup_$(Get-Date -Format 'yyyy-MM-dd').sql
```

### Restore from Backup:
```powershell
Get-Content E:\PBL_AI_Orchestrator\backup_2024-11-12.sql | docker exec -i ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator
```

---

## 🎓 Bottom Line

**Physical database files?** Inside Docker volume (not easily readable)

**Actual data viewing?** Use:
1. ✅ **pgAdmin 4** (download it!)
2. ✅ **DBeaver** (easier to use)
3. ✅ **python view_database.py** (already works!)
4. ✅ **VS Code PostgreSQL extension**

**The database is real** and running right now on your machine at `localhost:5433`!
