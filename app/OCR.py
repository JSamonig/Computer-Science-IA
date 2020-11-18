import re
import cv2
import pytesseract
import difflib
from collections import defaultdict
import config as c
import requests
import datetime
import concurrent.futures
from currency_converter import CurrencyConverter

CurrencyConverter = CurrencyConverter(
    fallback_on_missing_rate=True, fallback_on_wrong_date=True
)

# change this depending on location
pytesseract.pytesseract.tesseract_cmd = c.Config.TESSERACT_LOCATION


def get_date(text):
    n_text = len(text["text"])
    for i in range(n_text):
        if int(text["conf"][i]) > 0:  # if confidence level is positive
            if re.match(
                c.Config.DATE_PATTERN, text["text"][i]
            ):  # iterate until a date is found
                return text["text"][i]
    return None  # return None if no date is found


def find_total(text):
    totals = defaultdict(list)  # prevents KeyError
    total_list = ["total", "subtotal", "amount", "due", "sum", "payable", "mastercard"]
    n_boxes = len(text["text"])
    for i in range(n_boxes):
        if int(text["conf"][i]) > 0:
            parsed_text = difflib.get_close_matches(
                text["text"][i].lower(), total_list, 1
            )
            # fuzzy match total in text
            if parsed_text and locate_prices(text, i) is not None:
                totals[parsed_text[0]].append(locate_prices(text, i))
                # append total to totals
    if len(totals) > 1:
        if "subtotal" in totals:
            totals.pop("subtotal")
        return next(iter(totals.values()))[0]  # return first item of list
    return None


def locate_prices(text, start):
    n_text = len(text["text"])
    for i in range(start, n_text):
        if int(text["conf"][i]) > 0:
            if re.match(c.Config.PRICE_PATTERN, text["text"][i]):
                # match prices
                return float(re.sub(r"\D+", "", text["text"][i]))
                # remove characters and return a float
    return None


def recognise(filename, taggun=False):
    file_path = c.Config.IMAGE_UPLOADS + filename
    img = cv2.imread(file_path)
    if taggun is False:
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_data(
            img, output_type=pytesseract.Output.DICT, config=custom_config
        )
        date = get_date(text)
        try:  # put date into correct format dd/mm/yyyy, regardless of date e.g. 1/10/19 -> 01/10/2019
            symbols = "".join([i for i in date if not i.isdigit()])
            if len(date.split(symbols[1])[2]) != 4:
                date = date.split(symbols[1])
                date[2] = "20" + date[2]
                date = symbols[0].join(date)
        except TypeError:
            date = None
        total = find_total(text)
    else:
        # <-- adapted from https://www.taggun.io/
        url = "https://api.taggun.io/api/receipt/v1/verbose/file"
        headers = {"apikey": c.Config.TAGGUN_KEY}
        files = {
            "file": (
                filename,  # set a filename for the file
                open(file_path, "rb"),  # the actual file
                "image/" + str(filename.split(".")[1]),
            ),  # content-type for the file
            # other optional parameters for Taggun API (eg: incognito, refresh, ipAddress, language)
            "incognito": (
                None,
                "false",
            ),  # set filename to none for optional parameters  # value for the parameters
        }
        response = requests.post(url, files=files, headers=headers).json()
        # -->
        try:
            date_obj = datetime.datetime.strptime(
                response["date"]["data"].split("T")[0].replace("-", ""), "%Y%m%d"
            ).date()
            date = str(date_obj.strftime("%d/%m/%Y"))
        except KeyError:
            date = None
        try:
            total = response["totalAmount"]["data"]  # get date
            try:
                currency = response["totalAmount"][
                    "currencyCode"
                ]  # try to get currency
                if date_obj:  # if we have a date
                    total = CurrencyConverter.convert(
                        total,
                        currency,
                        "GBP",  # convert to GBP
                        date_obj,
                    )
                else:
                    total = CurrencyConverter.convert(total, currency, "GBP")
                    # If no date, just convert using historic rate
                total = round(total, 2)
                return {"date_receipt": date, "total": total, "currency": currency}
            except KeyError:
                total = round(total, 2)  # if we don't have a currency, don't convert
        except KeyError:
            total = None  # if everthing fails don't give a total
    return {"date_receipt": date, "total": total, "currency": None}


def run(filename, taggun=False):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(recognise, filename, taggun)
        try:
            return_value = future.result(timeout=12)  # set 12 second timeout
        except concurrent.futures.TimeoutError:
            return_value = {"date_receipt": None, "total": None}
        return return_value
