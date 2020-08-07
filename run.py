from app import app, db
from app.models import Account_codes, reclaim_forms, reclaim_forms_details, User


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User,
            'Account_codes': Account_codes, 'reclaim_forms': reclaim_forms,
            "reclaim_forms_details": reclaim_forms_details}

# set FLASK_ENV=development
