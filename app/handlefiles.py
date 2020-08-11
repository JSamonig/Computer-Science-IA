from app import app
import imghdr
from werkzeug.utils import secure_filename
import requests

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

def addFile(file_name,file):
    username = 'samonij'
    token = '3dad86ced0980df37f588eb91741e77b6474d3c8'
    host = 'https://eu.pythonanywhere.com/'

    response = requests.post(
        'https://{host}/api/v0/user/{username}/files/path{path}'.format(
            host=host, username=username, path=app.config['IMAGE_UPLOADS'] + file_name
        ),
        headers={'Authorization': 'Token {token}'.format(token=token), "content":file}
    )
    if response.status_code == 200:
        print('CPU quota info:')
        print(response.content)
    else:
        print('Got unexpected status code {}: {!r}'.format(response.status_code, response.content))