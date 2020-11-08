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


#  --> Adapted from https://blog.miguelgrinberg.com/
def validate_image(stream):
    """
    :param stream: byte stream of image
    :return: string of filetype
    """
    # find image type
    header = stream.read(512)
    stream.seek(0)
    file_format = imghdr.what(None, header)
    if not file_format:
        return None
    return file_format


# <--

def validate_excel(filename):
    """
    secure file name
    :param filename: filename of excel sheet
    :return: secured filename string
    """
    filename = secure_filename(filename)
    file = filename.rsplit('.', 1)[0].lower() + ".xlsx"
    if file == ".xlsx":
        file = "reclaim_form.xlsx"
    return file


def create_excel(file_id, current_user, signature=None):
    """
    create an excel sheet
    :param file_id: file id of reclaim form
    :param current_user: current user object
    :param signature: signature file name
    """
    handleExcel.delete_all_sheets()
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first_or_404()
    rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(form_id=file_id).all()
    user = User.query.get(current_user.id)
    date = datetime.datetime.now().strftime("%d/%m/%Y")
    handleExcel.requirements([str(user.first_name), str(user.last_name)], str(date), str(file.filename))
    if signature:
        handleExcel.add_signature(signature, file.filename, date)
    for row in rows:
        info = [row.date_receipt, row.description, row.miles, row.account_id, row.Total]
        handleExcel.edit_row(info, file.filename, row.row_id)
        if row.image_name:
            handleExcel.add_images(file.filename, row.row_id, row.image_name)
    return file


# https://stackoverflow.com/questions/876853/generating-color-ranges-in-python
def create_distinct_colours(n):
    """
    Create distinct colours
    :param n: number of colours
    :return: colour array (Hex)
    """
    HSV_tuples = [(x * 1.0 / n, 0.5, 0.5) for x in range(n)]
    RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
    colours = []
    for i in RGB_tuples:
        txt = ""
        for j in i:
            txt = txt + str(hex(int(j * 255)).replace("0x", ""))
        colours.append("#" + txt)
    return colours


# https://stackoverflow.com/questions/52250812/how-to-set-watermark-text-on-images-in-python
def create_signature_back(first, last):
    """
    Create a signature watermark
    :param first: first name of user
    :param last: surname of user
    :return: data url encoded watermark image
    """
    base = Image.open(c.Config.SIGNATURE_ROUTE + 'wellington_crest.png').convert('RGBA')
    width, height = base.size
    fnt = ImageFont.truetype('arial.ttf', 20)
    txt = Image.new('RGBA', base.size, (256, 256, 256, 0))
    for i in range(1, width, int(width / 4)):  # watermark image with date and name
        txt = txt.rotate(-45)
        d = ImageDraw.Draw(txt)
        d.text((i - (width / 3), i), datetime.datetime.now().date().strftime("%d/%m/%Y") + " {} {}".format(first, last),
               font=fnt,
               fill=(128, 128, 128, 64))
        txt = txt.rotate(45)
    out = Image.alpha_composite(base, txt)
    name = c.Config.SIGNATURE_ROUTE + str(uuid.uuid4()) + ".png"  # save image temporarily
    out.save(name)
    with open(name, "rb") as image:
        f = image.read()
        image.close()
    encoded = base64.b64encode(f).decode()
    data = 'data:image/png;base64,{}'.format(encoded)
    os.remove(name)  # delete image
    return data  # return as url encoded data


def revert_to_draft(file):
    if file.sent == "Authorized":  # if a file is already authorized make it into a draft
        file.sent = "Draft"
        if file.signature:
            try:  # remove signature
                os.remove(os.path.join(app.config["SIGNATURE_ROUTE"], file.signature))
                file.signature = None
            except FileNotFoundError:
                pass
            db.session.commit()
