from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from models import db, User, Doctor, Patient, Appointment, Treatment
from datetime import date
from cache_config import cache

doctor_bp = Blueprint('doctor', __name__, url_prefix='/api/doctor')


# get dr rec
def get_current_doctor():
    user_id = get_jwt_identity()
    doctor  = Doctor.query.filter_by(user_id=user_id).first()
    return doctor


def is_doctor():
    claims = get_jwt()
    return claims.get('role') == 'doctor'


# dr dashb
@doctor_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    # Get today's date
    today = date.today()

    # Get all appointments for this doctor today
    todays_appointments = Appointment.query.filter_by(
        doctor_id=doctor.id,
        date=today
    ).all()

    # Get total unique patients for this doctor
    total_patients = Appointment.query.filter_by(
        doctor_id=doctor.id
    ).distinct(Appointment.patient_id).count()

    appointments_data = []
    for appt in todays_appointments:
        patient_user = User.query.get(appt.patient.user_id)
        appointments_data.append({
            'appointment_id': appt.id,
            'patient_name'  : patient_user.username,
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason,
            'has_treatment' : appt.treatment is not None
        })

    return jsonify({
        'todays_appointments': appointments_data,
        'total_patients'     : total_patients
    }), 200


# get app 
@doctor_bp.route('/appointments', methods=['GET'])
@jwt_required()
def get_appointments():
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()

    result = []
    for appt in appointments:
        patient_user = User.query.get(appt.patient.user_id)
        result.append({
            'appointment_id': appt.id,
            'patient_name'  : patient_user.username,
            'patient_id'    : appt.patient_id,
            'date'          : str(appt.date),
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason,
            'has_treatment' : appt.treatment is not None,
            # Include full treatment details so frontend can show inline
            'treatment'     : {
                'diagnosis'   : appt.treatment.diagnosis,
                'prescription': appt.treatment.prescription,
                'notes'       : appt.treatment.notes,
                'next_visit'  : appt.treatment.next_visit
            } if appt.treatment else None
        })

    return jsonify(result), 200

# update app
@doctor_bp.route('/appointments/<int:appointment_id>/status', methods=['PUT'])
@jwt_required()
def update_appointment_status(appointment_id):
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    appointment = Appointment.query.filter_by(
        id        = appointment_id,
        doctor_id = doctor.id
    ).first()

    if not appointment:
        return jsonify({'message': 'Appointment not found'}), 404

    # Cannot cancel a completed appointment
    if appointment.status == 'Completed':
        return jsonify({'message': 'Completed appointments cannot be cancelled'}), 400

    data   = request.get_json()
    status = data.get('status')

    if status not in ['Completed', 'Cancelled']:
        return jsonify({'message': 'Status must be Completed or Cancelled'}), 400

    appointment.status = status
    db.session.commit()

    return jsonify({'message': f'Appointment marked as {status}'}), 200


# add treatment
@doctor_bp.route('/appointments/<int:appointment_id>/treatment', methods=['POST'])
@jwt_required()
def add_treatment(appointment_id):
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    appointment = Appointment.query.filter_by(
        id=appointment_id,
        doctor_id=doctor.id
    ).first()

    if not appointment:
        return jsonify({'message': 'Appointment not found'}), 404

    # Can only add treatment to completed appointments
    if appointment.status != 'Completed':
        return jsonify({'message': 'Treatment can only be added to completed appointments'}), 400

    # Check if treatment already exists for this appointment
    existing = Treatment.query.filter_by(appointment_id=appointment_id).first()
    if existing:
        return jsonify({'message': 'Treatment already added for this appointment'}), 400

    data = request.get_json()

    treatment = Treatment(
        appointment_id = appointment_id,
        diagnosis      = data.get('diagnosis'),
        prescription   = data.get('prescription'),
        notes          = data.get('notes'),
        next_visit     = data.get('next_visit')
    )
    db.session.add(treatment)
    db.session.commit()

    return jsonify({'message': 'Treatment added successfully'}), 201


# set avail
@doctor_bp.route('/availability', methods=['POST'])
@jwt_required()
def set_availability():
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    data  = request.get_json()
    # dates is a list ["2024-01-01", "2024-01-02"]
    dates = data.get('dates', [])

    # Store as comma separated string in DB
    doctor.availability = ','.join(dates)
    db.session.commit()

    return jsonify({'message': 'Availability updated successfully'}), 200


# get patient history
@doctor_bp.route('/patients/<int:patient_id>/history', methods=['GET'])
@jwt_required()
def get_patient_history(patient_id):
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    # Get all appointments for this patient with this doctor
    appointments = Appointment.query.filter_by(
        doctor_id=doctor.id,
        patient_id=patient_id
    ).all()

    history = []
    for appt in appointments:
        treatment_data = None
        if appt.treatment:
            treatment_data = {
                'diagnosis'   : appt.treatment.diagnosis,
                'prescription': appt.treatment.prescription,
                'notes'       : appt.treatment.notes,
                'next_visit'  : appt.treatment.next_visit
            }

        history.append({
            'appointment_id': appt.id,
            'date'          : str(appt.date),
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason,
            'treatment'     : treatment_data
        })

    return jsonify(history), 200


# View All Assigned Patients
@doctor_bp.route('/patients', methods=['GET'])
@jwt_required()
def get_assigned_patients():
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    # Get all appointments for this doctor
    appointments = Appointment.query.filter_by(
        doctor_id=doctor.id
    ).all()

    # Use a dict to get unique patients only
    
    unique_patients = {}
    for appt in appointments:
        pid = appt.patient_id
        if pid not in unique_patients:
            patient_user = User.query.get(appt.patient.user_id)
            unique_patients[pid] = {
                'patient_id' : appt.patient.id,
                'name'       : patient_user.username,
                'email'      : patient_user.email,
                'age'        : appt.patient.age,
                'blood_group': appt.patient.blood_group,
                'phone'      : appt.patient.phone,
                'gender'     : appt.patient.gender
            }

    return jsonify(list(unique_patients.values())), 200


# Doctor View Patient Treatment Records

@doctor_bp.route('/patients/<int:patient_id>/treatments', methods=['GET'])
@jwt_required()
def get_patient_treatment_records(patient_id):
    if not is_doctor():
        return jsonify({'message': 'Access denied'}), 403

    doctor = get_current_doctor()
    if not doctor:
        return jsonify({'message': 'Doctor profile not found'}), 404

    # Doctor view patients who app with them
    appointments = Appointment.query.filter_by(
        doctor_id  = doctor.id,
        patient_id = patient_id
    ).order_by(Appointment.date.desc()).all()

    if not appointments:
        return jsonify({'message': 'No records found for this patient'}), 404

    patient_user = User.query.get(appointments[0].patient.user_id)

    records = []
    for appt in appointments:
        treatment_data = None
        if appt.treatment:
            treatment_data = {
                'diagnosis'   : appt.treatment.diagnosis,
                'prescription': appt.treatment.prescription,
                'notes'       : appt.treatment.notes,
                'next_visit'  : appt.treatment.next_visit
            }

        records.append({
            'appointment_id': appt.id,
            'date'          : str(appt.date),
            'time_slot'     : appt.time_slot,
            'status'        : appt.status,
            'reason'        : appt.reason,
            'treatment'     : treatment_data
        })

    return jsonify({
        'patient_name': patient_user.username,
        'records'     : records
    }), 200