"""
Script : créer le compte test_IV
Usage  : python create_test_user.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from Code.app import create_app
from Code.extensions import db
from Code.models.models import User, Entity

app = create_app()
with app.app_context():
    if User.query.filter_by(email='test_iv@devoptiq.test').first():
        print('Le compte test_IV existe déjà.')
        sys.exit(0)

    entity = Entity.query.filter_by(is_active=True).first() or Entity.query.first()
    u = User(
        first_name='Test',
        last_name='IV',
        email='test_iv@devoptiq.test',
        password='safe',
        status='user',
        entity_id=entity.id if entity else None
    )
    db.session.add(u)
    db.session.commit()
    print(f'Compte test_IV créé (id={u.id}, email=test_iv@devoptiq.test, password=safe)')
