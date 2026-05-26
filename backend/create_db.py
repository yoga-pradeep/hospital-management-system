from app import app
from models import db, User, Department
from werkzeug.security import generate_password_hash


def create_database():
    with app.app_context():

        db.create_all()

        existing_admin = User.query.filter_by(role='admin').first()
        if not existing_admin:
            admin = User(
                username  = 'admin',
                email     = 'admin@hospital.com',
                password  = generate_password_hash('admin123'),
                role      = 'admin',
                is_active = True
            )
            db.session.add(admin)
            db.session.commit()

        departments = [
            {'name': 'Cardiology',      'description': 'Heart and cardiovascular system'},
            {'name': 'Neurology',       'description': 'Brain and nervous system'},
            {'name': 'Dermatology',     'description': 'Skin, hair and nails'},
           
        ]

        for dept_data in departments:
            existing = Department.query.filter_by(name=dept_data['name']).first()
            if not existing:
                dept = Department(
                    name        = dept_data['name'],
                    description = dept_data['description']
                )
                db.session.add(dept)

        db.session.commit()
        print("Database created and initialized successfully!")

if __name__ == '__main__':
    create_database()