# TUSOME School Management System

A comprehensive web‑based school management system built with Flask.
Manages students, grades, fees, attendance, assignments, and parent communication.

## Features

- **Admin Dashboard** – Student enrollment, grade entry, fee structure, announcements, reports.
- **Teacher Portal** – Grade entry (spreadsheet style with NCBE levels), attendance, assignments, class lists.
- **Parent Portal** – View children’s grades, fee balances, announcements, download reports.
- **Finance Dashboard** – Fee collections, outstanding balances, payment recording, expense tracking.
- **Reports** – Student report cards (KNEC format), class grade sheets, fee summaries, student lists.

## Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask‑Login
- **Frontend**: Bootstrap 5, Chart.js, DataTables, jQuery
- **Database**: SQLite (development) / PostgreSQL (production)
- **Deployment**: Render, Gunicorn

## Installation (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/douglaskiplagatc-hue/tusome-academy.git
cd tusome-academy
