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
        
        # 1. Obtener todos los IDs de la columna Q (17) de una vez
        ids = sheet.col_values(17)[1:] 
        
        fila_encontrada = None
        for index, valor_celda in enumerate(ids):
            # 2. Limpieza extrema: quitamos espacios, puntos y pasamos a mayúsculas
            valor_limpio = str(valor_celda).strip().replace(".", "").upper()
            qr_limpio = qr_code.strip().replace(".", "").upper()
            
            if valor_limpio == qr_limpio and valor_limpio != "":
                fila_encontrada = index + 2 # +2 porque empezamos desde la fila 2
                break
        
        if not fila_encontrada:
            return jsonify({"status": "not_found", "message": "❌ Entrada no encontrada en el sistema."}), 404
        
        # 3. Leer datos (Según tu imagen: B=Apellido, C=Nombre, R=Estado)
        apellido = str(sheet.cell(fila_encontrada, 2).value or "")
        nombre = str(sheet.cell(fila_encontrada, 3).value or "")
        estado_actual = str(sheet.cell(fila_encontrada, 18).value or "").strip()
        
        nombre_completo = f"{nombre} {apellido}".strip()
        
        if estado_actual == "Ingresado":
            return jsonify({
                "status": "already_used",
                "message": f"⚠️ ¡Entrada ya utilizada!\n{nombre_completo} ya ingresó antes.",
                "name": nombre_completo
            }), 200
        
        # 4. Actualizar el estado en la columna R (18)
        sheet.update_cell(fila_encontrada, 18, "Ingresado")
        
        return jsonify({
            "status": "success",
            "message": f"✅ ¡Acceso Concedido!\nBienvenido/a, {nombre_completo}.",
            "name": nombre_completo
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)