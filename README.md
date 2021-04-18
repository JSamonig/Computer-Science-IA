# Computer Science IA

This project was made as part of my computer science IA. The purpose of this application is to automise expense
reclaiming at my school, which is done manually using excel sheets. The application uses Python's Flask, HTML, CSS, 
Javascript, and bootstrap.

## Setup
1) locate the project files
2) cd to directory containing the `app` folder
3) Setup python virtual environment
4) Install Tesseract.exe from [here](https://github.com/tesseract-ocr/tessdoc/blob/master/Downloads.md), and update `TESSERACT_LOCATION` in `config.py`
5) Install packages from `requirements.txt`
6) set environment variable: `set FLASK_APP=run.py`
7) run `flask db init`
8) run `flask db migrate`
9) run `flask db upgrade`
10) run `IA/app/updating/update_database.py`
11) run `flask run`
12) open `localhost:5000`

### Running
1) set environment variable: `set FLASK_APP=run.py`
2) run the command: `flask run`
3) open `localhost:5000`

### Debugging
1) set environment variable `set FLASK_APP=run.py`
2) set environment variable `set FLASK_ENV=development`
3) run the command: `flask run`
4) open `localhost:5000`

###### Note: the command `set` is windows specific, for linux use `export`.
