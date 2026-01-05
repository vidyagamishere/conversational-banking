# Conversational ATM Banking Demo

A full-stack conversational banking application with React frontend, FastAPI backend, and Ollama LLM integration.

## Features

- **Conversational ATM**: Natural language banking powered by Ollama gemma2:2b
- **Traditional ATM**: Menu-driven interface for standard banking operations
- **JWT Authentication**: Secure 30-minute session tokens
- **Multi-language Support**: English-first with i18n framework
- **Remote Screen Flow**: Visual transaction flow with auto-progression
- **Detailed Error Handling**: Specific error codes for better UX

## Tech Stack

### Frontend
- React 18 with TypeScript
- Material-UI v5
- react-i18next for internationalization
- Axios for API calls

### Backend
- FastAPI 0.109+
- SQLModel (SQLAlchemy 2.0)
- PostgreSQL
- JWT authentication
- Ollama integration with retry logic

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+
- Ollama with gemma2:2b model

## Setup Instructions

### 1. Database Setup

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for complete PostgreSQL setup instructions.

Quick setup:
```bash
# Create database and user
createdb conversational_banking
psql conversational_banking < DATABASE_SCHEMA.md  # Run the SQL commands

# Or use the provided seed script after setting up tables
cd backend
source venv/bin/activate
python seed.py
```

### 2. Ollama Setup

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull gemma2:2b model (in a new terminal)
ollama pull gemma2:2b
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.example ../.env
# Edit .env with your configuration

# Run migrations
alembic upgrade head

# Seed database
python seed.py

# Start backend server
uvicorn main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd frontend-react

# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest
```

### Frontend Tests
```bash
cd frontend-react
npm test
```

## Demo Credentials

### Customer 1 (English)
- Card Number: 4111111111111111
- PIN: 1234
- Accounts: Checking ($2,500), Savings ($4,200)

### Customer 2 (Spanish preference)
- Card Number: 4222222222222222
- PIN: 5678
- Accounts: Checking ($1,800), Savings ($3,600)

## API Documentation

Full API documentation is available at http://localhost:8000/docs when the backend is running.

## Project Structure

```
ConversationalBanking/
├── backend/
│   ├── models/          # SQLModel database models
│   ├── routes/          # FastAPI route handlers
│   ├── services/        # Business logic layer
│   ├── orchestrator/    # Ollama LLM integration
│   ├── migrations/      # Alembic migrations
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration management
│   ├── seed.py          # Database seeding
│   └── requirements.txt
├── frontend-react/
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── contexts/    # React contexts
│   │   ├── services/    # API service layer
│   │   ├── i18n/        # Internationalization
│   │   └── App.tsx
│   └── package.json
├── .env.example
└── README.md
```

## Error Codes

- `INSUFFICIENT_FUNDS`: Account balance too low
- `INVALID_ACCOUNT`: Account not found or invalid
- `INVALID_PIN`: Incorrect PIN entered
- `ACCOUNT_LOCKED`: Too many failed PIN attempts
- `LLM_UNAVAILABLE`: Conversational mode unavailable

## License

MIT License - For demonstration purposes only
