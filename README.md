# EventSphere -- Agent-Based Event Management System

EventSphere is a web-based event management application developed with
**Python** and **FastAPI**. It supports event discovery and management,
ticket bookings, simulated payments, digital tickets, waitlists,
notifications, and event check-in.

The application uses six specialized agents to organize key
event-management responsibilities.

> **Project status:** The recorded automated test run completed with
> **38 passed tests** (13 agent tests and 25 API tests). The run also
> reported five deprecation warnings; these did not cause test failures.

------------------------------------------------------------------------

## Table of Contents

-   [Features](#features)
-   [Agent Responsibilities](#agent-responsibilities)
-   [Technology Stack](#technology-stack)
-   [User Roles](#user-roles)
-   [Getting Started](#getting-started)
-   [Running the Application](#running-the-application)
-   [API Documentation](#api-documentation)
-   [Running Tests](#running-tests)
-   [Project Structure](#project-structure)
-   [Configuration and Notes](#configuration-and-notes)

## Features

-   User registration and login
-   Role-based access for attendees, administrators, and staff
-   Venue and event management
-   Venue-capacity and event-overlap validation
-   Ticket booking with inventory validation and a six-ticket booking
    limit
-   Simulated payment processing
-   Unique digital ticket generation
-   Waitlist management with oldest-entry-first offers
-   Notification creation and persistence
-   Ticket validation and event check-in
-   Private-hire requests and related workflows
-   Agent-message persistence and logging
-   SQLite support for local development and PostgreSQL configuration
    support

## Agent Responsibilities

  -----------------------------------------------------------------------
  Agent                               Responsibility
  ----------------------------------- -----------------------------------
  **VenueAgent**                      Applies venue and event
                                      constraints, including venue
                                      capacity and overlapping published
                                      events.

  **BookingAgent**                    Validates booking requests, ticket
                                      limits, and remaining ticket
                                      inventory.

  **TicketAgent**                     Generates unique digital ticket
                                      codes and prevents duplicate ticket
                                      generation.

  **WaitlistAgent**                   Manages waiting entries, offers
                                      tickets to the oldest eligible
                                      entry, and handles expired offers.

  **NotificationAgent**               Creates notifications and persists
                                      notification state.

  **CheckinAgent**                    Validates tickets for an event and
                                      prevents invalid or repeated
                                      check-ins.
  -----------------------------------------------------------------------

The agents are coordinated by the application workflows. Their
responsibilities are separated so that individual business rules can be
maintained and tested independently.

## Technology Stack

  Technology              Purpose
  ----------------------- -----------------------------------------
  Python                  Backend and agent implementation
  FastAPI                 Backend API framework
  SQLAlchemy              Database ORM and data access
  SQLite                  Local development database
  PostgreSQL              Supported production database option
  Pydantic                Data validation
  HTML, CSS, JavaScript   Frontend
  Uvicorn                 ASGI application server
  Pytest                  Automated testing
  Git and GitHub          Version control and source-code hosting

## User Roles

-   **Attendee:** Registers, logs in, browses events, books tickets, and
    views their own relevant records.
-   **Administrator:** Uses authorized administrative functions for
    venue, event, and related management.
-   **Staff:** Uses authorized check-in functionality to validate event
    tickets.

Access to protected operations is controlled by authentication and role
checks.

## Getting Started

### Prerequisites

Install the following before running the project:

-   Python 3.10 or a compatible version supported by the project's
    dependencies
-   Git
-   pip

### 1. Clone the repository

``` bash
git clone https://github.com/nishageedayarathna/EventSphere.git
cd EventSphere
```

### 2. Create and activate a virtual environment

**Windows (Command Prompt):**

``` bash
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

``` bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

If the project includes a `.env.example` file, copy it to `.env` and
fill in the required values:

``` bash
copy .env.example .env
```

For PowerShell, the same `copy` command is supported. On macOS/Linux
use:

``` bash
cp .env.example .env
```

Do not commit secrets, passwords, API keys, or production database
credentials to GitHub. Check the actual application configuration and
`.env.example` file for the environment variables required by your
checkout.

## Running the Application

From the project root, with the virtual environment activated, run:

``` bash
python -m uvicorn app.main:app --reload --port 8010
```

Open the local application:

-   Homepage: http://127.0.0.1:8010
-   API documentation (Swagger UI): http://127.0.0.1:8010/docs
-   Alternative API documentation (ReDoc), if enabled:
    http://127.0.0.1:8010/redoc

Stop the development server with `Ctrl + C`.

## API Documentation

FastAPI provides interactive API documentation at:

``` text
http://127.0.0.1:8010/docs
```

Use the documentation to inspect available endpoints and try requests.
The endpoints shown there reflect the API routes registered by the
running version of the application.

## Running Tests

Run the complete automated test suite from the project root:

``` bash
pytest -v
```

The recorded test run for this project reported:

-   **13 agent tests passed**
-   **25 API tests passed**
-   **38 tests passed in total**

The tests cover selected behaviours including venue-capacity validation,
overlapping events, booking limits, ticket inventory, unique ticket
generation, waitlist ordering and expiry, notification persistence,
ticket check-in, authentication, role access, CSRF protection, event
operations, booking, refunds, private hire, and agent-message
persistence.

The recorded run also showed five deprecation warnings related to
framework/test-client APIs. These warnings did not cause the tests to
fail.

To run individual test files:

``` bash
pytest -v tests/test_agents.py
pytest -v tests/test_api.py
```

## Project Structure

The following is a high-level guide to important project paths. Refer to
the repository itself for the complete and exact file structure.

``` text
EventSphere/
├── app/
│   ├── main.py
│   ├── agents/
│   ├── database/
│   └── ...
├── static/
│   ├── css/
│   └── js/
├── templates/
├── tests/
│   ├── test_agents.py
│   └── test_api.py
├── requirements.txt
└── README.md
```

## Configuration and Notes

-   Local development uses the database configuration selected by the
    application. SQLite is the local-development option described for
    this project.
-   PostgreSQL support is included; configure the appropriate database
    connection settings before using a PostgreSQL deployment.
-   Payment processing in the described project is simulated. Do not
    treat it as a live payment integration.
-   Use test accounts and non-production data when demonstrating the
    application.
-   Never publish real user passwords, secret keys, session secrets, or
    database credentials.
-   The test results in this README refer to the recorded run. Re-run
    `pytest -v` after making code changes to verify the current
    checkout.

## Repository

GitHub: https://github.com/nishageedayarathna/EventSphere
