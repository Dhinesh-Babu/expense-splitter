import os
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from pdf_parser import parse_walmart_pdf


# Initialize the Flask application
app = Flask(__name__)

# Configure the upload folder and allowed extensions
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", receipt=None)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(request.url)

    file = request.files["file"]

    if file.filename == "":
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Parse the PDF to extract the entire receipt object
        try:
            # The parser now returns a dictionary with 'items' and 'summary' keys
            receipt_data = parse_walmart_pdf(filepath)
            # print("Parsed receipt data:", receipt_data["items"], receipt_data["summary"], len(receipt_data["items"]), len(receipt_data["summary"]))

            return render_template("index.html", receipt=receipt_data, error=None)
        except Exception as e:
            error_message = f"An error occurred during parsing: {e}"
            return render_template("index.html", receipt=None, error=error_message)

    # If the file is not a PDF or something goes wrong
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Runs the app in debug mode
    app.run(debug=True)
