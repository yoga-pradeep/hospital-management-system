from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, User, Patient

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
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
        role      = 'patient',
        is_active = True
    )
    db.session.add(new_user)
    db.session.flush()  

    new_patient = Patient(
        user_id     = new_user.id,
        age         = data.get('age'),
        blood_group = data.get('blood_group'),
        phone       = data.get('phone'),
        address     = data.get('address'),
        gender      = data.get('gender')
    )
    db.session.add(new_patient)
    db.session.commit()

    return jsonify({'message': 'Registration successful'}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid username or password'}), 401

    if not user.is_active:
        return jsonify({'message': 'Your account has been deactivated'}), 403

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'role'    : user.role,
            'username': user.username,
            'email'   : user.email
        }
    )

    return jsonify({
        'access_token': access_token,
        'role'        : user.role,
        'username'    : user.username,
        'user_id'     : user.id
    }), 200