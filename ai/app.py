# app.py

from flask import Flask, render_template, request, redirect, url_for
import os
import requests
from PIL import Image
import google.generativeai as genai
import pandas as pd
import string

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GOOGLE_APPS_SCRIPT_URL = os.environ.get('GOOGLE_APPS_SCRIPT_URL')

# Ensure they are set
if not GOOGLE_API_KEY or not GOOGLE_APPS_SCRIPT_URL:
    raise Exception("Environment variables for API keys are not set.")


# Configure the API with the API key
genai.configure(api_key=GOOGLE_API_KEY)

# Allowed extensions for uploaded files
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_excel_column_from_header(header):
    """Get the Excel column letter based on the header."""
    # Get the first letter of the header (uppercase)
    first_letter = header.strip().upper()[0]
    # Only map letters A to J
    if first_letter in string.ascii_uppercase[:10]:  # 'A' to 'J'
        return first_letter
    return None


@app.route('/', methods=['GET', 'POST'])
def upload_image():
    if request.method == 'POST':
        # Check if an image file was uploaded
        if 'image' not in request.files:
            return 'No image file uploaded', 400
        file = request.files['image']
        if file.filename == '':
            return 'No selected file', 400
        if file and allowed_file(file.filename):
            # Save the uploaded image
            filename = file.filename
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)

            # Open the image
            image = Image.open(image_path)

            # Define the prompt
            prompt = "Analyze this image and generate a table with headers based on its content"

            # Ensure the model supports image recognition or analyze accordingly
            try:
                model = genai.GenerativeModel(model_name="gemini-1.5-flash")
                # If the model supports image input, you can proceed as per your original code
                response = model.generate_content([prompt, image])
                response_text = response.text
            except Exception as e:
                # Handle exceptions appropriately
                return f"An error occurred during model processing: {e}", 500

            # Assuming the response is a string representing a table
            # Parse the response into a list of lists (data for the table)
            data_lines = [
                line.split('|')[1:-1] for line in response_text.split('\n')
                if '|' in line
            ]

            # Remove any unwanted header dividers (like "---" rows)
            data = [
                row for row in data_lines
                if not any('---' in cell for cell in row)
            ]

            # Create a DataFrame to represent the table
            df = pd.DataFrame(
                data[1:],
                columns=data[0])  # First row as headers, rest as data

            # Create a dictionary to store header to Google Sheets column mappings
            header_to_column = {}

            # Loop through the headers and assign them to their Google Sheets columns
            for header in df.columns:
                excel_column = get_excel_column_from_header(header)
                if excel_column:
                    header_to_column[header] = excel_column

            # Prepare the data to be sent to the Google Apps Script
            table_data = {
                "headers": list(header_to_column.keys()),
                "rows": df.values.tolist(),
                "header_to_column": header_to_column
            }

            # Send the data to Google Sheets via Google Apps Script
            try:
                response = requests.post(GOOGLE_APPS_SCRIPT_URL,
                                         json=table_data)
            except Exception as e:
                return f"An error occurred while sending data to Google Apps Script: {e}", 500

            # Remove the uploaded image after processing
            os.remove(image_path)

            # Return the response to the user
            return f"Response from Google Apps Script: {response.text}"

        else:
            return 'Invalid file type', 400
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
