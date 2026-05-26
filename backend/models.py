from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password      = db.Column(db.String(200), nullable=False)  
    role          = db.Column(db.String(20), nullable=False)   
    is_active     = db.Column(db.Boolean, default=True)        
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

   
    doctor_profile  = db.relationship('Doctor', backref='user', uselist=False)
    patient_profile = db.relationship('Patient', backref='user', uselist=False)

    def __repr__(self):
        return f'<User {self.username} - {self.role}>'


class Department(db.Model):
    __tablename__ = 'department'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False) 
    description = db.Column(db.String(300))                               

    doctors = db.relationship('Doctor', backref='department', lazy=True)

    def __repr__(self):
        return f'<Department {self.name}>'

class Doctor(db.Model):
    __tablename__ = 'doctor'

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    department_id    = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    qualification    = db.Column(db.String(100))   
    experience_years = db.Column(db.Integer, default=0)
    phone            = db.Column(db.String(15))
    
    availability     = db.Column(db.Text, default='')

    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

    def __repr__(self):
        return f'<Doctor user_id={self.user_id}>'


class Patient(db.Model):
    __tablename__ = 'patient'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    age         = db.Column(db.Integer)
    blood_group = db.Column(db.String(5))   
    phone       = db.Column(db.String(15))
    address     = db.Column(db.String(300))
    gender      = db.Column(db.String(10))

    appointments = db.relationship('Appointment', backref='patient', lazy=True)

    def __repr__(self):
        return f'<Patient user_id={self.user_id}>'


class Appointment(db.Model):
    __tablename__ = 'appointment'

    id         = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id  = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    time_slot  = db.Column(db.String(20), nullable=False) 
    status     = db.Column(db.String(20), default='Booked') 
    reason     = db.Column(db.String(300))                 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    treatment = db.relationship('Treatment', backref='appointment', uselist=False)

    def __repr__(self):
        return f'<Appointment patient={self.patient_id} doctor={self.doctor_id} date={self.date}>'


class Treatment(db.Model):
    __tablename__ = 'treatment'

    id             = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False, unique=True)
    diagnosis      = db.Column(db.String(500))   
    prescription   = db.Column(db.String(500))   
    notes          = db.Column(db.String(500))    
    next_visit     = db.Column(db.String(100))     
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Treatment appointment_id={self.appointment_id}>'