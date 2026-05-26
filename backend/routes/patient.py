from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from models import db, User, Doctor, Patient, Appointment, Treatment, Department
from datetime import date
from cache_config import cache

patient_bp = Blueprint('patient', __name__, url_prefix='/api/patient')

def get_current_patient():
    # get_jwt_identity() returns user_id stored in token
    user_id = get_jwt_identity()
    patient = Patient.query.filter_by(user_id=user_id).first()
    return patient


def is_patient():
    claims = get_jwt()
    return claims.get('role') == 'patient'


# Patient Dashboard

@patient_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    today = date.today()

    # Get upcoming appointments - date is today or future
    upcoming = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.date       >= today,
        Appointment.status     == 'Booked'
    ).all()

    upcoming_data = []
    for appt in upcoming:
        doctor_user = User.query.get(appt.doctor.user_id)
        dept        = Department.query.get(appt.doctor.department_id)
        upcoming_data.append({
            'appointment_id': appt.id,
            'doctor_name'   : doctor_user.username,
            'department'    : dept.name if dept else None,
            'date'          : str(appt.date),
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason
        })

    return jsonify({
        'upcoming_appointments': upcoming_data,
        'total_upcoming'       : len(upcoming_data)
    }), 200


# view dr
@patient_bp.route('/doctors', methods=['GET'])
@jwt_required()

@cache.cached(timeout=300, query_string=True)
def get_doctors():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    search = request.args.get('search', '')

    query = db.session.query(Doctor, User, Department).join(
        User, Doctor.user_id == User.id
    ).outerjoin(
        Department, Doctor.department_id == Department.id
    ).filter(User.is_active == True)

    if search:
        query = query.filter(
            User.username.ilike(f'%{search}%') |
            Department.name.ilike(f'%{search}%')
        )

    results = query.all()

    doctors = []
    for doctor, user, dept in results:
        availability = doctor.availability.split(',') if doctor.availability else []
        doctors.append({
            'doctor_id'       : doctor.id,
            'name'            : user.username,
            'department'      : dept.name if dept else None,
            'qualification'   : doctor.qualification,
            'experience_years': doctor.experience_years,
            'availability'    : availability
        })

    return jsonify(doctors), 200

    
# book app
@patient_bp.route('/appointments', methods=['POST'])
@jwt_required()
def book_appointment():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    data = request.get_json()

    if not data.get('doctor_id') or not data.get('date') or not data.get('time_slot'):
        return jsonify({'message': 'Doctor, date and time slot are required'}), 400

    # prevent multibooking
    existing = Appointment.query.filter_by(
        doctor_id = data['doctor_id'],
        date      = date.fromisoformat(data['date']),
        time_slot = data['time_slot'],
        status    = 'Booked'
    ).first()

    if existing:
        return jsonify({'message': 'This time slot is already booked'}), 400

    # prevent same pt booking same dr same day same slot
    patient_existing = Appointment.query.filter_by(
        patient_id = patient.id,
        doctor_id  = data['doctor_id'],
        date       = date.fromisoformat(data['date']),
        time_slot  = data['time_slot']
    ).first()

    if patient_existing:
        return jsonify({'message': 'You already have an appointment at this time'}), 400

    new_appointment = Appointment(
        patient_id = patient.id,
        doctor_id  = data['doctor_id'],
        date       = date.fromisoformat(data['date']),
        time_slot  = data['time_slot'],
        reason     = data.get('reason'),
        status     = 'Booked'
    )
    db.session.add(new_appointment)
    db.session.commit()

    return jsonify({'message': 'Appointment booked successfully'}), 201


# cancel app
@patient_bp.route('/appointments/<int:appointment_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_appointment(appointment_id):
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    # Find appointment belonging to this patient only
    appointment = Appointment.query.filter_by(
        id         = appointment_id,
        patient_id = patient.id
    ).first()

    if not appointment:
        return jsonify({'message': 'Appointment not found'}), 404

    if appointment.status != 'Booked':
        return jsonify({'message': 'Only booked appointments can be cancelled'}), 400

    appointment.status = 'Cancelled'
    db.session.commit()

    return jsonify({'message': 'Appointment cancelled successfully'}), 200


# view app history
@patient_bp.route('/appointments/history', methods=['GET'])
@jwt_required()
def appointment_history():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    # Get all appointments for this patient
    appointments = Appointment.query.filter_by(
        patient_id=patient.id
    ).order_by(Appointment.date.desc()).all()

    history = []
    for appt in appointments:
        doctor_user    = User.query.get(appt.doctor.user_id)
        dept           = Department.query.get(appt.doctor.department_id)
        treatment_data = None

        # Include treatment details if available
        if appt.treatment:
            treatment_data = {
                'diagnosis'   : appt.treatment.diagnosis,
                'prescription': appt.treatment.prescription,
                'notes'       : appt.treatment.notes,
                'next_visit'  : appt.treatment.next_visit
            }

        history.append({
            'appointment_id': appt.id,
            'doctor_name'   : doctor_user.username,
            'department'    : dept.name if dept else None,
            'date'          : str(appt.date),
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason,
            'treatment'     : treatment_data
        })

    return jsonify(history), 200


# edit patient prof

@patient_bp.route('/profile', methods=['PUT'])
@jwt_required()
def edit_profile():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    data = request.get_json()

    # Update only fields that are sent
    if data.get('age')        : patient.age         = data['age']
    if data.get('blood_group'): patient.blood_group  = data['blood_group']
    if data.get('phone')      : patient.phone        = data['phone']
    if data.get('address')    : patient.address      = data['address']
    if data.get('gender')     : patient.gender       = data['gender']

    db.session.commit()

    return jsonify({'message': 'Profile updated successfully'}), 200


# get patient profile
@patient_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    user = User.query.get(patient.user_id)

    return jsonify({
        'username'   : user.username,
        'email'      : user.email,
        'age'        : patient.age,
        'blood_group': patient.blood_group,
        'phone'      : patient.phone,
        'address'    : patient.address,
        'gender'     : patient.gender
    }), 200

# Reschedule Appointment

@patient_bp.route('/appointments/<int:appointment_id>/reschedule', methods=['PUT'])
@jwt_required()
def reschedule_appointment(appointment_id):
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    # Find appointment belonging to this patient only
    appointment = Appointment.query.filter_by(
        id         = appointment_id,
        patient_id = patient.id
    ).first()

    if not appointment:
        return jsonify({'message': 'Appointment not found'}), 404

    # Only booked appointments can be rescheduled
    if appointment.status != 'Booked':
        return jsonify({'message': 'Only booked appointments can be rescheduled'}), 400

    data     = request.get_json()
    new_date = data.get('date')
    new_slot = data.get('time_slot')

    if not new_date or not new_slot:
        return jsonify({'message': 'New date and time slot are required'}), 400

    # conflict prevention 
    existing = Appointment.query.filter_by(
        doctor_id = appointment.doctor_id,
        date      = date.fromisoformat(new_date),
        time_slot = new_slot,
        status    = 'Booked'
    ).first()

    # Conflict
    if existing and existing.id != appointment.id:
        return jsonify({'message': 'This time slot is already booked'}), 400

    # Update to new date and time
    appointment.date      = date.fromisoformat(new_date)
    appointment.time_slot = new_slot
    db.session.commit()

    return jsonify({'message': 'Appointment rescheduled successfully'}), 200

# CSV Export

@patient_bp.route('/export-csv', methods=['POST'])
@jwt_required()
def export_csv():
    if not is_patient():
        return jsonify({'message': 'Access denied'}), 403

    patient = get_current_patient()
    if not patient:
        return jsonify({'message': 'Patient profile not found'}), 404

    # Import here to avoid circular import
    from tasks import export_patient_csv


    export_patient_csv.delay(patient.id)

    return jsonify({
        'message': 'Export started. Check your Mail.'
    }), 200