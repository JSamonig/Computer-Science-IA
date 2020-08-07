from app import app
import imghdr
from werkzeug.utils import secure_filename


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS_IMAGES"]


def validate_image(stream):
    header = stream.read(512)
    stream.seek(0)
    format = imghdr.what(None, header)
    if not format:
        return None
    return format


def validate_excel(filename):
    filename = secure_filename(filename)
    print(filename)
    return filename.rsplit('.', 1)[0].lower() + ".xlsx"
