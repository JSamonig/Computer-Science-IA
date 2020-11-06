# from app import app, preprocess
import re
import cv2
import pytesseract
import difflib
from collections import defaultdict
import config as c
import requests
import datetime
import concurrent.futures

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def getDate(text):
    n_text = len(text['text'])
    for i in range(n_text):
        if int(text['conf'][i]) > 0:
            if re.match(c.Config.DATE_PATTERN, text['text'][i]):
                return (text['text'][i])
    return None


def findTotal(text):
    totals = defaultdict(list)
    totalList = ["total", "subtotal", "amount", "due", "sum", "payable", "mastercard"]
    n_boxes = len(text['text'])
    for i in range(n_boxes):
        if int(text["conf"][i]) > 0:
            parsedText = difflib.get_close_matches(text["text"][i].lower(), totalList, 1)
            if parsedText and locatePrices(text, i) is not None:
                totals[parsedText[0]].append(locatePrices(text, i))
    if len(totals) > 1:
        if "subtotal" in totals:
            totals.pop("subtotal")
        return next(iter(totals.values()))[0]
    return None


def locatePrices(text, start):
    n_text = len(text['text'])
    for i in range(start, n_text):
        if int(text["conf"][i]) > 0:
            if re.match(c.Config.PRICE_PATTERN, text['text'][i]):
                return float(re.sub(r'\D+', '', text['text'][i]))
    return None


def recognise(fname, taggun=False):
    filename = c.Config.IMAGE_UPLOADS + fname
    img = cv2.imread(filename)
    if taggun is False:
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=custom_config)
        date = getDate(text)
        try:
            symbols = ''.join([i for i in date if not i.isdigit()])
            if len(date.split(symbols[1])[2]) != 4:
                date = date.split(symbols[1])
                date[2] = "20" + date[2]
                date = symbols[0].join(date)
        except TypeError:
            date = None
        total = findTotal(text)
    else:
        # <-- adapted from https://www.taggun.io/
        url = 'https://api.taggun.io/api/receipt/v1/simple/file'
        headers = {'apikey': '7c9356e0d8c111eaafc7c5a18819396c'}
        files = {'file': (
            fname,  # set a filename for the file
            open(filename, 'rb'),  # the actual file
            'image/' + str(fname.split(".")[1])),  # content-type for the file
            # other optional parameters for Taggun API (eg: incognito, refresh, ipAddress, language)
            'incognito': (
                None,  # set filename to none for optional parameters
                'false')  # value for the parameters
        }
        response = requests.post(url, files=files, headers=headers).json()
        # -->
        try:
            date = datetime.datetime.strptime(response["date"]["data"].split("T")[0].replace("-", ""), "%Y%m%d").date()
            date = str(date.strftime("%d/%m/%Y"))
        except KeyError:
            date = None
        try:
            total = response["totalAmount"]["data"]
        except KeyError:
            total = None
    return {"date_receipt": date, "Total": total}


def run(fname, taggun=False):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(recognise, fname, taggun)
        try:
            return_value = future.result(timeout=10)
        except concurrent.futures.TimeoutError:
            return_value = {"date_receipt": None, "Total": None}
        return return_value
