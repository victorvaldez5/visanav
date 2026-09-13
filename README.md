# Project Raul Overview

Immigration RAG AI Chatbot

A chatbot that helps immigrants find the right immigration status and services. Helping people apply for immigration,
find immigration status, and find immigration services. Connecting with the right attorneys and lawyers.
Allowing for secure communication and document sharing with your attorneys.

## Features

- Scheduled or on-demand scraping of USCIS data
- Lightweight, containerized services
- Extendable Python codebase
- Pinecone integration for vector database
- vue frontend chat interface
- django backend api server
- docker-compose for local development
- AWS glue job for data ingestion
- Pydnatic-ai for AI Agent based chatbot

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Running with Docker Compose](#running-with-docker-compose)
5. [Cleaning Up](#cleaning-up)

---

## Prerequisites

- Git (to clone the repo)
- Python 3.13.5
- [pip](https://pip.pypa.io/)
- Docker & Docker Compose

---

## Getting Started

1. Clone the repository
   ```bash
   git clone https://github.com/victorvaldez5/visanav.git
   cd visanav
   ```

2. Create & activate a Python virtual environment
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate      # on macOS/Linux
   .\.venv\Scripts\Activate.ps1   # on Windows PowerShell
   ```

3. Install Python dependencies
   Each subdirectory is a service. Each service has its own requirements.
   to install specific project requirements, go into that service directory and run:
   ```bash
   pip install --upgrade pip
   pip install poetry
   poetry install
   ```

4. Install Frontend dependencies
   Inside the frontend directory run the following commands

```bash
npm install -D
```

---

## Development Workflow

Use docker compose to work with the containers.

To bring up the web services (frontend, api, database) run

```bash
  docker compose up
```

to bring up the scraper run

```bash
  docker compose up uscis_scraper
```

to bring up the glue5 container run

```bash
  docker compose glue5_pyspark
```

---

## Cleaning Up

When you’re done:

- Stop & remove containers
  ```bash
  docker compose down
  ```

- Deactivate your virtual environment
  ```bash
  deactivate
  ```

- (Optional) Remove local images/volumes
  ```bash
  docker system prune
  ```

---

## Production Checklist
