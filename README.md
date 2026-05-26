Hospital Management System (HMS) web application that allows Admins, Doctors, and Patients to interact with the system based on their roles.
# Hospital Management System - V2

## Project Overview

This is a Hospital Management System developed as part of the MAD-II project.
The system allows Admin, Doctor, and Patient to interact with the application for managing hospital operations.

---

## Technologies Used

* Python (Flask)
* SQLite (Database)
* HTML, CSS (Frontend)
* Redis & Celery (for background jobs)

---

## User Roles

Admin, Doctor, Patients


## How to Run the Project

### Install dependencies

```bash
pip install -r backend/requirements.txt
```

---

### Create database

```bash
python backend/create_db.py
```

---

###  Run Flask application

```bash
cd backend
python app.py
```

---

###  Run Celery Worker (for background jobs)

```bash
cd backend
celery -A app.celery worker --loglevel=info
```

---

###  Run Celery Beat (for scheduled tasks)

```bash
cd backend
celery -A app.celery beat --loglevel=info
```


---

## 🗄️ Database

* Database is created programmatically using `create_db.py`


---

## 📁 Project Structure

```
backend/
  app.py
  models.py
  routes/
frontend/
  *.html
```

---

## 🎯 Features Implemented

* User authentication (Admin, Doctor, Patient)
* Appointment management
* Role-based dashboards
* Treatment history tracking

---
