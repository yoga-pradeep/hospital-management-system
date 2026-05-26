from app import celery
from models import db, User, Doctor, Patient, Appointment, Treatment
from mail_config import mail
from flask_mail import Message
from datetime import date, datetime
import csv
import io


# Daily app remainder
@celery.task(name='tasks.send_daily_reminders')
def send_daily_reminders():
    today = date.today()

    # Find all booked appointments for today and future dates
    todays_appointments = Appointment.query.filter(
        Appointment.date >= today,
        Appointment.status == 'Booked'
    ).all()

    for appt in todays_appointments:
        # Get patient email
        patient_user = User.query.get(appt.patient.user_id)
        doctor_user  = User.query.get(appt.doctor.user_id)

        if patient_user and patient_user.email:
            msg = Message(
                subject    = 'Hospital Appointment Reminder',
                recipients = [patient_user.email]
            )

            
            msg.body = (
                f"Dear {patient_user.username},\n\n"
                f"This is a reminder that you have an appointment today.\n\n"
                f"Doctor    : {doctor_user.username}\n"
                f"Date      : {str(appt.date)}\n"
                f"Time Slot : {appt.time_slot}\n"
                f"Reason    : {appt.reason or 'General Consultation'}\n\n"
                f"Please arrive 10 minutes before your scheduled time.\n\n"
                f"Regards,\nHospital Management - 23F3000598"
            )

            mail.send(msg)

    return f'Reminders sent for {len(todays_appointments)} appointments'


#  Monthly Activity Report - Dr

@celery.task(name='tasks.send_monthly_reports')
def send_monthly_reports():
    # Get last month's number and year
    today      = date.today()
    month      = today.month - 1 if today.month > 1 else 12
    year       = today.year if today.month > 1 else today.year - 1

    # Get all doctors
    doctors = Doctor.query.all()

    for doctor in doctors:
        doctor_user = User.query.get(doctor.user_id)

        # Get all completed appointments for this doctor last month
        appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status    == 'Completed',
            db.extract('month', Appointment.date) == month,
            db.extract('year',  Appointment.date) == year
        ).all()

        total_appointments = len(appointments)
        total_treatments   = sum(1 for a in appointments if a.treatment)

        # Build HTML report
        rows = ''
        for appt in appointments:
            patient_user   = User.query.get(appt.patient.user_id)
            treatment_info = 'No treatment recorded'
            if appt.treatment:
                treatment_info = appt.treatment.diagnosis or 'Recorded'

            rows += f"""
                <tr>
                    <td>{patient_user.username}</td>
                    <td>{str(appt.date)}</td>
                    <td>{appt.time_slot}</td>
                    <td>{treatment_info}</td>
                </tr>
            """

        html_report = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">

                <h2>Monthly Activity Report</h2>
                <p>Doctor  : <strong>{doctor_user.username}</strong></p>
                <p>Month   : <strong>{month}/{year}</strong></p>

                <table border="1" cellpadding="8" cellspacing="0"
                       style="border-collapse: collapse; width: 100%;">
                    <thead style="background-color: #f2f2f2;">
                        <tr>
                            <th>Patient</th>
                            <th>Date</th>
                            <th>Time Slot</th>
                            <th>Diagnosis</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>

                <br>
                <p>Total Appointments : <strong>{total_appointments}</strong></p>
                <p>Total Treatments   : <strong>{total_treatments}</strong></p>

                <br>
                <p>Regards,<br>Hospital Management System</p>

            </body>
            </html>
        """

        if doctor_user and doctor_user.email:
            msg = Message(
                subject    = f'Monthly Activity Report - {month}/{year}',
                recipients = [doctor_user.email]
            )
            msg.html = html_report
            mail.send(msg)

    return f'Monthly reports sent to {len(doctors)} doctors'


# CSV User exp
@celery.task(name='tasks.export_patient_csv')
def export_patient_csv(patient_id):
    # Get patient details
    patient      = Patient.query.get(patient_id)
    patient_user = User.query.get(patient.user_id)

    # Get all appointments with treatments
    appointments = Appointment.query.filter_by(
        patient_id=patient_id
    ).order_by(Appointment.date.desc()).all()

    # Built in memyor & snd - no disk
    output = io.StringIO()
    writer = csv.writer(output)

    # CSV Header row
    writer.writerow([
        'Appointment ID',
        'Doctor Name',
        'Date',
        'Time Slot',
        'Status',
        'Reason',
        'Diagnosis',
        'Prescription',
        'Notes',
        'Next Visit'
    ])

    # CSV Data rows
    for appt in appointments:
        doctor_user = User.query.get(appt.doctor.user_id)

        diagnosis    = ''
        prescription = ''
        notes        = ''
        next_visit   = ''

        if appt.treatment:
            diagnosis    = appt.treatment.diagnosis    or ''
            prescription = appt.treatment.prescription or ''
            notes        = appt.treatment.notes        or ''
            next_visit   = appt.treatment.next_visit   or ''

        writer.writerow([
            appt.id,
            doctor_user.username,
            str(appt.date),
            appt.time_slot,
            appt.status,
            appt.reason or '',
            diagnosis,
            prescription,
            notes,
            next_visit
        ])

    # Get CSV content as string
    csv_content = output.getvalue()
    output.close()

    # Send email with CSV 
    if patient_user and patient_user.email:
        msg = Message(
            subject    = 'Your Treatment History Export',
            recipients = [patient_user.email]
        )

        msg.body = (
            f"Dear {patient_user.username},\n\n"
            f"Your treatment history export is ready.\n"
            f"PFA CSV.\n\n"
            f"Regards,\nHospital Management - 23F3000598"
        )

        # Attach CSV file to email
        msg.attach(
            filename     = f'treatment_history_{patient_id}.csv',
            content_type = 'text/csv',
            data         = csv_content
        )

        mail.send(msg)

    return f'CSV export completed for patient {patient_id}'