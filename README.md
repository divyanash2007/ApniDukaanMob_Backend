# ApniDukaan Mobile Backend

This directory contains the FastAPI backend for the ApniDukaan Mobile application.

## Tech Stack
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT, bcrypt

## Setup Instructions

1. **Virtual Environment**: Create and activate a Python virtual environment.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   # venv\Scripts\activate   # On Windows
   ```

2. **Dependencies**: Install the required packages.
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**: Define your local database credentials.
   ```bash
   cp .env.example .env
   ```
   Open `.env` and configure your `DATABASE_URL` (requires a running PostgreSQL database).

4. **Run Server**: Start the FastAPI development server.
   ```bash
   uvicorn main:app --reload
   ```
   *The server will typically start at `http://127.0.0.1:8000`.*

5. **API Documentation**: With the server running, visit `http://127.0.0.1:8000/docs` to view the interactive Swagger API documentation.
