"""
mcp_server.py
--------------
Model Context Protocol (MCP) server for the Hospital Management System.

This does NOT create a second/duplicate data layer. Every tool below opens
the SAME Flask app context and queries the SAME SQLAlchemy models
(models.py) and the SAME SQLite database used by the REST API
(routes/admin.py, routes/doctor.py, rouclonetes/patient.py).

RBAC NOTE:
    MCP tools normally have no idea who is calling them. To keep the
    existing JWT/RBAC guarantees intact, every tool takes `role` and
    `user_id` arguments. These values are NEVER trusted from the LLM.
    The MCP *client* (ai_assistant.py) always overwrites them with the
    role/user_id taken from the caller's verified JWT before the tool is
    invoked, no matter what the model tried to pass. So even though the
    tool signature exposes these fields (MCP requires a JSON schema),
    the actual access control decision is made server-side from the
    authenticated Flask request, not from model output.

Run standalone for testing:
    python mcp_server.py
It is normally spawned as a subprocess (stdio transport) by ai_assistant.py.
"""

from datetime import date

from mcp.server.fastmcp import FastMCP

from app import app
from models import db, User, Doctor, Patient, Appointment, Department

mcp = FastMCP("hospital-mcp")


def _doctor_display(doctor: Doctor):
    user = User.query.get(doctor.user_id)
    dept = Department.query.get(doctor.department_id) if doctor.department_id else None
    return {
        "doctor_id": doctor.id,
        "name": user.username if user else None,
        "department": dept.name if dept else None,
        "qualification": doctor.qualification,
        "experience_years": doctor.experience_years,
    }


@mcp.tool()
def get_my_appointments(role: str, user_id: str, filter: str = "upcoming") -> dict:
    """Get appointments belonging to the currently authenticated caller.

    For a patient: returns that patient's own appointments.
    For a doctor: returns that doctor's own appointments.
    For an admin: returns a summary across every appointment in the system.

    Args:
        role: injected server-side from the caller's JWT ("patient"/"doctor"/"admin").
        user_id: injected server-side from the caller's JWT (the User.id).
        filter: "upcoming", "history", or "all".
    """
    with app.app_context():
        if role == "patient":
            patient = Patient.query.filter_by(user_id=user_id).first()
            if not patient:
                return {"error": "Patient profile not found"}
            query = Appointment.query.filter_by(patient_id=patient.id)
        elif role == "doctor":
            doctor = Doctor.query.filter_by(user_id=user_id).first()
            if not doctor:
                return {"error": "Doctor profile not found"}
            query = Appointment.query.filter_by(doctor_id=doctor.id)
        elif role == "admin":
            query = Appointment.query
        else:
            return {"error": "Unknown role"}

        today = date.today()
        if filter == "upcoming":
            query = query.filter(Appointment.date >= today, Appointment.status == "Booked")
        elif filter == "history":
            query = query.filter(Appointment.date < today)

        appointments = query.order_by(Appointment.date.desc()).limit(25).all()

        results = []
        for appt in appointments:
            patient_user = User.query.get(appt.patient.user_id)
            doctor_user = User.query.get(appt.doctor.user_id)
            results.append({
                "appointment_id": appt.id,
                "patient_name": patient_user.username if patient_user else None,
                "doctor_name": doctor_user.username if doctor_user else None,
                "date": str(appt.date),
                "time_slot": appt.time_slot,
                "status": appt.status,
                "reason": appt.reason,
            })

        return {"count": len(results), "appointments": results}


@mcp.tool()
def get_doctor_today_schedule(role: str, user_id: str) -> dict:
    """Get today's appointment schedule for the caller, if the caller is a doctor.

    Args:
        role: injected server-side from the caller's JWT.
        user_id: injected server-side from the caller's JWT.
    """
    with app.app_context():
        if role != "doctor":
            return {"error": "Only a doctor can view their own schedule with this tool"}

        doctor = Doctor.query.filter_by(user_id=user_id).first()
        if not doctor:
            return {"error": "Doctor profile not found"}

        today = date.today()
        appointments = Appointment.query.filter_by(doctor_id=doctor.id, date=today).all()

        results = []
        for appt in appointments:
            patient_user = User.query.get(appt.patient.user_id)
            results.append({
                "appointment_id": appt.id,
                "patient_name": patient_user.username if patient_user else None,
                "time_slot": appt.time_slot,
                "status": appt.status,
                "reason": appt.reason,
            })

        return {"date": str(today), "count": len(results), "appointments": results}


@mcp.tool()
def search_doctors(role: str, user_id: str, department: str = "", query: str = "") -> dict:
    """Search active doctors by department or name, with their availability.
    Available to any authenticated role (patients use this to find a doctor).

    Args:
        role: injected server-side from the caller's JWT.
        user_id: injected server-side from the caller's JWT.
        department: optional department name filter.
        query: optional doctor name filter.
    """
    with app.app_context():
        if role not in ("patient", "doctor", "admin"):
            return {"error": "Unknown role"}

        q = db.session.query(Doctor, User, Department).join(
            User, Doctor.user_id == User.id
        ).outerjoin(
            Department, Doctor.department_id == Department.id
        ).filter(User.is_active == True)  # noqa: E712

        if department:
            q = q.filter(Department.name.ilike(f"%{department}%"))
        if query:
            q = q.filter(User.username.ilike(f"%{query}%"))

        results = []
        for doctor, user, dept in q.limit(25).all():
            availability = doctor.availability.split(",") if doctor.availability else []
            results.append({
                "doctor_id": doctor.id,
                "name": user.username,
                "department": dept.name if dept else None,
                "qualification": doctor.qualification,
                "experience_years": doctor.experience_years,
                "availability": availability,
            })

        return {"count": len(results), "doctors": results}


@mcp.tool()
def get_hospital_overview(role: str, user_id: str) -> dict:
    """Get hospital-wide statistics (total doctors/patients/appointments).
    Admin only.

    Args:
        role: injected server-side from the caller's JWT.
        user_id: injected server-side from the caller's JWT.
    """
    with app.app_context():
        if role != "admin":
            return {"error": "Access denied. Only an admin can view hospital-wide stats."}

        return {
            "total_doctors": Doctor.query.count(),
            "total_patients": Patient.query.count(),
            "total_appointments": Appointment.query.count(),
            "booked": Appointment.query.filter_by(status="Booked").count(),
            "completed": Appointment.query.filter_by(status="Completed").count(),
            "cancelled": Appointment.query.filter_by(status="Cancelled").count(),
        }


@mcp.tool()
def list_departments() -> dict:
    """List all hospital departments. Available to any authenticated role."""
    with app.app_context():
        depts = Department.query.all()
        return {"departments": [{"name": d.name, "description": d.description} for d in depts]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
