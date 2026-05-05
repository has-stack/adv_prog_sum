# Python Environment Drift Manager

This repository will contain a DevOps support tool for validating
Python workflows in isolated Docker environments. The project is based on a
small DevOps team that has experienced repeated Python environment
issues after a server and infrastructure migration.

The intended application will allow a user to define a constrained Python
workflow, generate a Docker execution environment, run the workflow, capture
logs, classify common failures and present solution guidance in a dashboard.

# Planned stack

- Python for the frontend, backend and core services.
- FastAPI for backend API endpoints.
- Streamlit for the dashboard frontend.
- SQLite for workflow templates, run history and findings.
- Docker for isolated workflow execution.
- pytest for automated testing.

# Note

This project was initially developed in a separate repository associated with a work account
and later migrated here for submission.
