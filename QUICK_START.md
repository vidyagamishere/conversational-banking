# Quick Start Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Ollama with gemma2:2b model

## 1. Clone and Setup

```bash
cd /path/to/ConversationalBanking
```

## 2. Database Setup

```bash
# Create PostgreSQL database
createdb conversational_banking

# Run schema from DATABASE_SCHEMA.md
psql conversational_banking
# Then copy and paste the SQL commands from DATABASE_SCHEMA.md
```

## 3. Backend Setup

```bash
cd backend

# Create virtual environment with Python 3.11
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed database (after PostgreSQL is configured)
python seed.py

# Start backend server
uvicorn main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000
API docs at: http://localhost:8000/docs

## 4. Frontend Setup

```bash
cd frontend-react

# Install dependencies
npm install --legacy-peer-deps

# Start development server
npm start
```

Frontend will be available at: http://localhost:3000

## 5. Ollama Setup (Optional for Conversational Mode)

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# In another terminal, pull gemma2:2b model
ollama pull gemma2:2b
```

## Test the Application

1. Open http://localhost:3000
2. Use demo credentials:
   - Card: `4111111111111111`, PIN: `1234`
   - Card: `4222222222222222`, PIN: `5678`
3. Choose Conversational or Traditional ATM mode
4. Try transactions!

## Troubleshooting

### Backend won't start
- Ensure PostgreSQL is running: `pg_isready`
- Check database connection in `.env` file
- Verify Python version: `python --version` (should be 3.11+)

### Frontend errors
- Try `rm -rf node_modules package-lock.json && npm install --legacy-peer-deps`
- Ensure backend is running on port 8000

### Conversational mode not working
- Check Ollama is running: `ollama list`
- Verify gemma2:2b model is installed
- If Ollama unavailable, app will auto-switch to Traditional mode
