from app import app, db, handleExcel
from app.models import reclaim_forms, reclaim_forms_details, User
import imghdr, datetime
from werkzeug.utils import secure_filename
import colorsys
from PIL import Image, ImageFont, ImageDraw
import config as c
import uuid
import base64
import os


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
    file = filename.rsplit('.', 1)[0].lower() + ".xlsx"
    if file == ".xlsx":
        file = "reclaim_form.xlsx"
    return file


def createExcel(file_id, current_user, signature=None):
    handleExcel.deleteAllSheets()
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first_or_404()
    rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(form_id=file_id).all()
    user = User.query.get(current_user.id)
    date = datetime.datetime.now().strftime("%d/%m/%Y")
    handleExcel.requirements([str(user.first_name), str(user.last_name)], str(date), str(file.filename))
    if signature:
        handleExcel.addSignature(signature,file.filename, date)
    for row in rows:
        info = [row.date_receipt, row.description, row.miles, row.account_id,
                row.Total]
        handleExcel.editRow(info, file.filename, row.row_id)
        if row.image_name:
            handleExcel.addImages(file.filename, row.row_id, row.image_name)
    return file


def createDistinctColours(n):
    HSV_tuples = [(x * 1.0 / n, 0.5, 0.5) for x in range(n)]
    RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
    colors = []
    for i in RGB_tuples:
        txt = ""
        for j in i:
            txt = txt + str(hex(int(j * 255)).replace("0x", ""))
        colors.append("#" + txt)
    return colors


# https://stackoverflow.com/questions/52250812/how-to-set-watermark-text-on-images-in-python
def createSignatureBack(first, last):
    base = Image.open(c.Config.SIGNATURE_ROUTE + 'wellington_crest.png').convert('RGBA')
    width, height = base.size
    fnt = ImageFont.truetype('arial.ttf', 20)
    txt = Image.new('RGBA', base.size, (256, 256, 256, 0))
    for i in range(1, width, int(width / 4)):
        txt = txt.rotate(-45)
        d = ImageDraw.Draw(txt)
        d.text((i - (width / 3), i), datetime.datetime.now().date().strftime("%d/%m/%Y") + " {} {}".format(first, last), font=fnt,
               fill=(128, 128, 128, 64))
        txt = txt.rotate(45)
    out = Image.alpha_composite(base, txt)
    name = c.Config.SIGNATURE_ROUTE + str(uuid.uuid4()) + ".png"
    out.save(name)
    with open(name, "rb") as image:
        f = image.read()
        image.close()
    encoded = base64.b64encode(f).decode()
    data='data:image/png;base64,{}'.format(encoded)
    os.remove(name)
    return data