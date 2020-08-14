from openpyxl import load_workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import colors, fills, Font, Border, Side
import config as c
import re
import os

# wscell1 = ws.cell(number, letter (number))
# Cells B7 - B26 = Date
# Cells C7 - C26 = Description
# Cells D7 - D26 = Miles
# Cells E7 - E26 = Account code
# Cells F7 - F26 = Amount
# info = [date, amount of miles and description, amount of miles, account code, total calculated]

def requirements(name: list, date, bookname):
    wb = getBook(bookname)
    ws = wb["Expense Claim Form 14-11-19"]
    bottomRow = 28
    if findAvailableRow(ws) >= 27:
        bottomRow = findAvailableRow(ws) + 1
    # Name at top
    for i in range(2, 4):
        namecell = ws.cell(4, i)
        namecell.value = name[i - 2]
    # Date at bottom
    datecell = ws.cell(bottomRow, 6)
    datecell.value = date
    # Name at bottom
    namecell = ws.cell(bottomRow, 3)
    namecell.value = name[0] + " " + name[1]
    wb.save(c.Config.RECLAIM_ROUTE + bookname)


def editRow(info: list, bookname, row=None):
    wb = getBook(bookname)
    ws = wb["Expense Claim Form 14-11-19"]
    if not row:
        row = findAvailableRow(ws)
        if ws.cell(row, 5).value:
            merged_cells_range = ws.merged_cells.ranges
            for merged_cell in merged_cells_range:
                if ord(re.sub(r'\d+', '', str(merged_cell).split(":")[0]).lower()) - 96 < 7:
                    merged_cell.shift(0, 1)
            ws.insert_rows(row)
    wcell = ws.cell(row, 1)
    wcell.value = row - 6
    for j in range(1, 7):  # row 2 - row 5 (last value is calculated)
        if j != 1:
            wcell = ws.cell(row, j)
            wcell.value = info[j - 2]
            grey = colors.Color(rgb='D9D9D9')
            wcell.fill = fills.PatternFill(patternType='solid', fgColor=grey)
        if j == 6:
            wcell.number_format = '_-[$£-en-GB]* #,##0.00_-;-[$£-en-GB]* #,##0.00_-;_-[$£-en-GB]* "-"??_-;_-@_-'
        wcell.font = Font(bold=False)
        thin_border = Border(left=Side(style='thin'),
                             right=Side(style='thin'),
                             top=Side(style='thin'),
                             bottom=Side(style='thin'))
        wcell.border = thin_border
        wb.save(c.Config.RECLAIM_ROUTE + bookname)


def addImages(bookname, row, filename:str):
    wb = getBook(bookname)
    sheetname = "Receipt for row " + str(row)
    wb.create_sheet(sheetname)
    ws = wb[sheetname]
    img = Image(c.Config.IMAGE_UPLOADS + filename)
    img.anchor = 'A1'
    ws.add_image(img)
    wb.save(c.Config.RECLAIM_ROUTE + bookname)


def findAvailableRow(ws):
    row = 7
    while ws.cell(row, 2).value:
        row += 1
    return row

def deleteAllSheets():
    files = [f for f in os.listdir(c.Config.RECLAIM_ROUTE)]
    for f in files:
        os.remove(os.path.join(c.Config.RECLAIM_ROUTE,f))

def createNewsheet(bookname):
    wb = load_workbook(c.Config.STATIC + "Expenses form.xlsx")
    wb.save(c.Config.RECLAIM_ROUTE + bookname)


def getBook(bookname):
    try:
       load_workbook(c.Config.RECLAIM_ROUTE + bookname)
    except:
        createNewsheet(bookname)
    return load_workbook(c.Config.RECLAIM_ROUTE + bookname)