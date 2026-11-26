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
        
        # 1. Obtener todos los IDs de la columna Q (17)
        ids = sheet.col_values(17)
        
        if len(ids) <= 1:
            return jsonify({"status": "error", "message": "⚠️ La columna Q (17) está VACÍA."}), 400
            
        # 2. Buscar TODAS las filas que coincidan con el QR
        qr_limpio = qr_code.strip().replace(".", "").upper()
        filas_encontradas = []
        
        for index, valor_celda in enumerate(ids[1:]): # Empezamos desde la fila 2
            valor_limpio = str(valor_celda).strip().replace(".", "").upper()
            if valor_limpio == qr_limpio and valor_limpio != "":
                filas_encontradas.append(index + 2) # +2 porque empezamos en la fila 2
                
        if not filas_encontradas:
            return jsonify({"status": "not_found", "message": "❌ Entrada no encontrada en el sistema."}), 404
        
        # 3. Revisar las filas para ver si hay al menos una disponible
        info_persona = ""
        fila_disponible = None
        
        for fila in filas_encontradas:
            # Leemos las columnas: B(2)=Apellido, C(3)=Nombre, E(5)=Correo, R(18)=Estado
            apellido = str(sheet.cell(fila, 2).value or "").strip()
            nombre = str(sheet.cell(fila, 3).value or "").strip()
            correo = str(sheet.cell(fila, 5).value or "").strip()
            estado_actual = str(sheet.cell(fila, 18).value or "").strip()
            
            # Armamos el texto: Nombre Apellido \n Correo
            if not info_persona:
                info_persona = f"{nombre} {apellido}\n{correo}".strip()
                
            # Si encontramos una fila que NO esté "Ingresado", la guardamos y paramos de buscar
            if estado_actual != "Ingresado":
                fila_disponible = fila
                break
        
        # 4. Si NO hay ninguna fila disponible (todas dicen "Ingresado")
        if not fila_disponible:
            return jsonify({
                "status": "already_used",
                "message": f"⚠️ ¡Entrada ya utilizada!\n{info_persona} ya ingresó antes.",
                "name": info_persona
            }), 200
        
        # 5. Si hay una fila disponible, le damos acceso y actualizamos SOLO esa fila
        sheet.update_cell(fila_disponible, 18, "Ingresado")
        
        return jsonify({
            "status": "success",
            "message": f"✅ ¡Acceso Concedido!\nBienvenido/a, {info_persona}.",
            "name": info_persona
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)