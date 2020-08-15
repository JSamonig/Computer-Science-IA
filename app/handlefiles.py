from app import app, db, handleExcel
from app.models import reclaim_forms, reclaim_forms_details, User
import imghdr, datetime
from werkzeug.utils import secure_filename


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS_IMAGES"]


#  --> Adapted from https://blog.miguelgrinberg.com/
def validate_image(stream):
    header = stream.read(512)
    stream.seek(0)
    format = imghdr.what(None, header)
    if not format:
        return None
    return format


# <--

def validate_excel(filename):
    filename = secure_filename(filename)
    print(filename)
    return filename.rsplit('.', 1)[0].lower() + ".xlsx"


def createExcel(file_id,current_user):
    handleExcel.deleteAllSheets()
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first_or_404()
    rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(form_id=file_id).all()
    user = User.query.get(current_user.id)
    date = datetime.datetime.now().strftime("%d/%m/%Y")
    handleExcel.requirements([str(user.first_name), str(user.last_name)], str(date), str(file.filename))
    for row in rows:
        info = [row.date_receipt, row.description, row.miles, row.account_id,
                row.Total]
        handleExcel.editRow(info, file.filename, row.row_id)
        if row.image_name:
            handleExcel.addImages(file.filename, row.row_id, row.image_name)
    return file.filename