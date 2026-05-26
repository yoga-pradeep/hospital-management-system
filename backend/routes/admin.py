from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.security import generate_password_hash
from models import db, User, Doctor, Patient, Appointment, Department
from cache_config import cache

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def is_admin():
    claims = get_jwt()
    return claims.get('role') == 'admin'

# adm dashboard

@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
# Cache dashboard stats for 2 minutes
@cache.cached(timeout=120)
def dashboard():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    total_doctors      = Doctor.query.count()
    total_patients     = Patient.query.count()
    total_appointments = Appointment.query.count()

    return jsonify({
        'total_doctors'     : total_doctors,
        'total_patients'    : total_patients,
        'total_appointments': total_appointments
    }), 200


# to add dr 
@admin_bp.route('/doctors', methods=['POST'])
@jwt_required()
def add_doctor():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    data = request.get_json()

    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Username, email and password are required'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400

    
    new_user = User(
        username  = data['username'],
        email     = data['email'],
        password  = generate_password_hash(data['password']),
        role      = 'doctor',
        is_active = True
    )
    db.session.add(new_user)
    db.session.flush()

    # Create doctor profile linked to user
    new_doctor = Doctor(
        user_id          = new_user.id,
        department_id    = data.get('department_id'),
        qualification    = data.get('qualification'),
        experience_years = data.get('experience_years', 0),
        phone            = data.get('phone')
    )
    db.session.add(new_doctor)
    db.session.commit()

    return jsonify({'message': 'Doctor added successfully'}), 201


# to get dr
@admin_bp.route('/doctors', methods=['GET'])
@jwt_required()
def get_doctors():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    # search query parameter - /api/admin/doctors?search=john
    search = request.args.get('search', '')

    # Join Doctor with User to get username and email
    query = db.session.query(Doctor, User).join(User, Doctor.user_id == User.id)

    if search:
        query = query.filter(
            User.username.ilike(f'%{search}%') |
            User.email.ilike(f'%{search}%')
        )

    results = query.all()

    doctors = []
    for doctor, user in results:
        dept_name = None
        if doctor.department_id:
            dept = Department.query.get(doctor.department_id)
            dept_name = dept.name if dept else None

        doctors.append({
            'doctor_id'       : doctor.id,
            'user_id'         : user.id,
            'username'        : user.username,
            'email'           : user.email,
            'is_active'       : user.is_active,
            'qualification'   : doctor.qualification,
            'experience_years': doctor.experience_years,
            'phone'           : doctor.phone,
            'department'      : dept_name
        })

    return jsonify(doctors), 200


# to get patient
@admin_bp.route('/patients', methods=['GET'])
@jwt_required()
def get_patients():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    search = request.args.get('search', '')

    query = db.session.query(Patient, User).join(User, Patient.user_id == User.id)

    if search:
        query = query.filter(
            User.username.ilike(f'%{search}%') |
            User.email.ilike(f'%{search}%') |
            Patient.phone.ilike(f'%{search}%')
        )

    results = query.all()

    patients = []
    for patient, user in results:
        patients.append({
            'patient_id': patient.id,
            'user_id'   : user.id,
            'username'  : user.username,
            'email'     : user.email,
            'is_active' : user.is_active,
            'age'       : patient.age,
            'blood_group': patient.blood_group,
            'phone'     : patient.phone,
            'address'   : patient.address,
            'gender'    : patient.gender
        })

    return jsonify(patients), 200


# blacklist/reactivate
@admin_bp.route('/users/<int:user_id>/toggle', methods=['PUT'])
@jwt_required()
def toggle_user(user_id):
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Flip the is_active value
    # True becomes False (blacklist)
    # False becomes True (reactivate)
    user.is_active = not user.is_active
    db.session.commit()

    status = 'activated' if user.is_active else 'deactivated'
    return jsonify({'message': f'User {status} successfully'}), 200


# get app
@admin_bp.route('/appointments', methods=['GET'])
@jwt_required()
def get_appointments():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    appointments = Appointment.query.all()

    result = []
    for appt in appointments:
        # Get patient username
        patient_user = User.query.get(appt.patient.user_id)
        # Get doctor username
        doctor_user  = User.query.get(appt.doctor.user_id)

        result.append({
            'appointment_id' : appt.id,
            'patient_name'   : patient_user.username,
            'doctor_name'    : doctor_user.username,
            'date'           : str(appt.date),
            'time_slot'      : appt.time_slot,
            'status'         : appt.status,
            'reason'         : appt.reason
        })

    return jsonify(result), 200


# get all dep
@admin_bp.route('/departments', methods=['GET'])
@jwt_required()
def get_departments():
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    departments = Department.query.all()
    result = []
    for dept in departments:
        result.append({
            'id'         : dept.id,
            'name'       : dept.name,
            'description': dept.description
        })

    return jsonify(result), 200

# Update Doctor Profile
@admin_bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
@jwt_required()
def update_doctor(doctor_id):
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    # Find doctor by doctor id
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404

    # Get the linked user record
    user = User.query.get(doctor.user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json()

    # Update user fields only if sent in request
    if data.get('email'):
        # Check email not taken by another user
        existing = User.query.filter_by(email=data['email']).first()
        if existing and existing.id != user.id:
            return jsonify({'message': 'Email already in use'}), 400
        user.email = data['email']

    if data.get('username'):
        existing = User.query.filter_by(username=data['username']).first()
        if existing and existing.id != user.id:
            return jsonify({'message': 'Username already in use'}), 400
        user.username = data['username']

    # Update doctor fields only if sent in request
    if data.get('qualification')   : doctor.qualification    = data['qualification']
    if data.get('experience_years'): doctor.experience_years = data['experience_years']
    if data.get('phone')           : doctor.phone            = data['phone']
    if data.get('department_id')   : doctor.department_id    = data['department_id']

    db.session.commit()

    return jsonify({'message': 'Doctor profile updated successfully'}), 200


# del Doctor

@admin_bp.route('/doctors/<int:doctor_id>', methods=['DELETE'])
@jwt_required()
def remove_doctor(doctor_id):
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404

    user = User.query.get(doctor.user_id)

    # Delete all appointments linked to this doctor first
    # to avoid foreign key errors
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    for appt in appointments:
        if appt.treatment:
            db.session.delete(appt.treatment)
        db.session.delete(appt)

    # Delete doctor profile
    db.session.delete(doctor)

    # Delete user account
    if user:
        db.session.delete(user)

    db.session.commit()

    return jsonify({'message': 'Doctor removed from system'}), 200


# del patient
@admin_bp.route('/patients/<int:patient_id>', methods=['DELETE'])
@jwt_required()
def remove_patient(patient_id):
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'message': 'Patient not found'}), 404

    user = User.query.get(patient.user_id)

    # Delete all appointments linked to this patient first
    appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    for appt in appointments:
        if appt.treatment:
            db.session.delete(appt.treatment)
        db.session.delete(appt)

    # Delete patient profile
    db.session.delete(patient)

    # Delete user account
    if user:
        db.session.delete(user)

    db.session.commit()

    return jsonify({'message': 'Patient removed from system'}), 200


# View Patient Treatment Records

@admin_bp.route('/patients/<int:patient_id>/treatments', methods=['GET'])
@jwt_required()
def get_patient_treatments(patient_id):
    if not is_admin():
        return jsonify({'message': 'Access denied'}), 403

    # Check patient exists
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'message': 'Patient not found'}), 404

    patient_user = User.query.get(patient.user_id)

    # Get all appointments for this patient
    appointments = Appointment.query.filter_by(
        patient_id=patient_id
    ).order_by(Appointment.date.desc()).all()

    records = []
    for appt in appointments:
        doctor_user    = User.query.get(appt.doctor.user_id)
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
            'doctor_name'   : doctor_user.username,
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