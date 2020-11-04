from app import app, db
from app.models import Account_codes, reclaim_forms, reclaim_forms_details, User


@app.shell_context_processor  # shell which is accessed when "flask shell" is executed
def make_shell_context():
    return {'db': db, 'User': User,
            'Account_codes': Account_codes, 'reclaim_forms': reclaim_forms,
            "reclaim_forms_details": reclaim_forms_details}


"""
This file is set as the python app: "set FLASK_APP=run.py"
The app is then executed using flask run
"""
