import os
import json
from flask import Flask, render_template, request, jsonify
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    
    client = gspread.authorize(creds)
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    sheet = client.open_by_key(sheet_id).worksheet("Respuestas de formulario 1")
    return sheet

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    qr_code = str(data.get("qr_code", "")).strip()
    
    if not qr_code:
        return jsonify({"status": "error", "message": "Código QR no válido."}), 400

    try:
        sheet = get_sheets_client()
        
        # CORRECCIÓN: Buscar en la columna 17 (Columna Q)
        cell = sheet.find(qr_code, in_column=17)
        
        if not cell:
            return jsonify({"status": "not_found", "message": "❌ Entrada no encontrada en el sistema."}), 404
        
        row = cell.row
        # CORRECCIÓN: Ajustamos las columnas a tu hoja real
        # Columna 3 = Nombre (C), Columna 4 = Apellido (D), Columna 18 = Estado (R)
        nombre = sheet.cell(row, 3).value
        apellido = sheet.cell(row, 4).value
        estado_actual = sheet.cell(row, 18).value
        
        nombre_completo = f"{nombre} {apellido}".strip()
        
        if estado_actual == "Ingresado":
            return jsonify({
                "status": "already_used",
                "message": f"⚠️ ¡Entrada ya utilizada!\n{nombre_completo} ya ingresó antes.",
                "name": nombre_completo
            }), 200
        
        # CORRECCIÓN: Actualizar el estado en la columna 18 (R)
        sheet.update_cell(row, 18, "Ingresado")
        
        return jsonify({
            "status": "success",
            "message": f"✅ ¡Acceso Concedido!\nBienvenido/a, {nombre_completo}.",
            "name": nombre_completo
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)