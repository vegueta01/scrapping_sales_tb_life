from flask import Flask, request, render_template, send_file, jsonify, redirect, url_for, session as flask_session
import requests
from bs4 import BeautifulSoup
import unicodedata
import re
import pandas as pd
import time
import threading

app = Flask(__name__)

app.secret_key = 'my_secret_key_01928374652' # Cambia esto a un valor seguro y único

# Variables globales para el progreso
progress = {"current": 0, "total": 0, "status": ""}

# URL para iniciar sesión
login_url = "https://app.milifehuni.com/admin/login"
# URL para obtener el ID del empresario
get_empresarios_url = "https://app.milifehuni.com/ajax/get_empresarios/"
# URL para realizar la consulta de cliente
consultar_url = "https://app.milifehuni.com/info/administrativos21/consultar/"

# Headers comunes
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "es",
    "cache-control": "max-age=0",
    "content-type": "application/x-www-form-urlencoded",
    "priority": "u=0, i",
    "sec-ch-ua": "\"Google Chrome\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "Referer": "https://app.milifehuni.com/admin",
    "Referrer-Policy": "no-referrer-when-downgrade"
}

# Función para iniciar sesión y obtener la sesión
def iniciar_sesion(login_data):
    session = requests.Session()
    response = session.post(login_url, headers=headers, data=login_data)
    if response.status_code == 200:
        print("Inicio de sesión exitoso")
        return session
    else:
        print(f"Error al iniciar sesión: {response.status_code}")
        return None

# Función para normalizar nombres eliminando caracteres especiales
def normalizar_nombre(nombre):
    normalized = unicodedata.normalize('NFD', nombre)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

# Función para obtener el ID del empresario a partir del nombre
def obtener_empresario_id(session, nombre):
    headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    body = f"filtro_empresario={nombre.strip()}&campo_select=emp_empresario_id&inactivos=1"
    print(f"body: {body}")
    response = session.post(get_empresarios_url, headers=headers, data=body)
    print(f"Obteniendo ID del empresario para {nombre} - {response.status_code}")
    if response.status_code == 200:
        script_content = response.text
        match = re.search(r"append\('<option value=\"(\d+)\">", script_content)
        if match:
            emp_id = match.group(1)
            print(f"ID del empresario para {nombre}: {emp_id}")
            return emp_id
        print(f"Contenido del script: {script_content}")
    print(f"Error al obtener el ID del empresario para {nombre}")
    return None

# Función para realizar la consulta de un cliente
def consultar_cliente(session, filtro_empresario, emp_empresario_id, periodo, periodofin):
    consultar_headers = headers.copy()
    consultar_headers["content-type"] = "multipart/form-data; boundary=----WebKitFormBoundaryYmvko1kxJeEr3xZV"

    body = f"------WebKitFormBoundaryYmvko1kxJeEr3xZV\r\nContent-Disposition: form-data; name=\"filtro_empresario\"\r\n\r\n{filtro_empresario}\r\n------WebKitFormBoundaryYmvko1kxJeEr3xZV\r\nContent-Disposition: form-data; name=\"emp_empresario_id\"\r\n\r\n{emp_empresario_id}\r\n------WebKitFormBoundaryYmvko1kxJeEr3xZV\r\nContent-Disposition: form-data; name=\"periodo\"\r\n\r\n{periodo}\r\n------WebKitFormBoundaryYmvko1kxJeEr3xZV\r\nContent-Disposition: form-data; name=\"periodofin\"\r\n\r\n{periodofin}\r\n------WebKitFormBoundaryYmvko1kxJeEr3xZV--\r\n"

    response = session.post(consultar_url, headers=consultar_headers, data=body)
    return response.text

# Función para extraer la información de las compras de la respuesta HTML
def extraer_compras(html):
    soup = BeautifulSoup(html, 'html.parser')
    tabla = soup.find('table', class_='table table-striped table-bordered')
    compras = []

    if tabla:
        rows = tabla.find_all('tr')[1:-1]  # Omitir encabezados y fila de suma
        for row in rows:
            cols = row.find_all('td')
            compra = {
                "Cnt": cols[0].text.strip(),
                "Documento": cols[1].text.strip(),
                "Fecha": cols[2].text.strip(),
                "Cantidad": cols[3].text.strip(),
                "Productos": cols[4].text.strip(),
                "Puntos": cols[5].text.strip(),
                "Total": float(cols[6].text.strip().replace('.', '').replace(',', '.'))
            }
            compras.append(compra)
    return compras

# Función para procesar los datos
def procesar_datos(login_data, nombres, periodo, periodofin, porcentaje_comision):
    sesion = iniciar_sesion(login_data)
    if not sesion:
        print("No se pudo iniciar sesión.")
        return None

    resultados = []
    global progress
    progress["total"] = len(nombres)
    progress["current"] = 0

    for nombre in nombres:
        nombre_normalizado = normalizar_nombre(nombre)
        emp_empresario_id = obtener_empresario_id(sesion, nombre_normalizado)
        if emp_empresario_id:
            respuesta_html = consultar_cliente(sesion, nombre_normalizado, emp_empresario_id, periodo, periodofin)
            compras = extraer_compras(respuesta_html)
            if compras:
                total_compras = sum(compra["Total"] for compra in compras)
                comision = total_compras * (porcentaje_comision / 100)
                productos_comprados = ', '.join(f'{compra["Cantidad"]} {compra["Productos"]}' for compra in compras)
                resultados.append({
                    "Nombre": nombre,
                    "Productos Comprados": productos_comprados,
                    "Comisión": round(comision, 2),
                    "Total Compras": round(total_compras, 2)
                })
            else:
                resultados.append({
                    "Nombre": nombre,
                    "Productos Comprados": "",
                    "Comisión": 0.0,
                    "Total Compras": 0.0
                })
        else:
            resultados.append({
                "Nombre": nombre,
                "Productos Comprados": "",
                "Comisión": 0.0,
                "Total Compras": 0.0
            })

        progress["current"] += 1
        progress["status"] = f"Consultado: {nombre}"
        print(f"Progreso: {progress['current']}/{progress['total']} - {progress['status']}")
        time.sleep(2)  # Aumentar el retraso para evitar limitaciones de la API

    df_resultados = pd.DataFrame(resultados)
    df_resultados.to_excel('resultados_compras.xlsx', index=False)
    print("Proceso completado y archivo Excel generado.")
    return 'resultados_compras.xlsx'

@app.route('/')
def index():
    if 'loggedin' in flask_session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        flask_session['username'] = username
        flask_session['password'] = password
        flask_session['loggedin'] = True
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    flask_session.pop('loggedin', None)
    flask_session.pop('username', None)
    flask_session.pop('password', None)
    return redirect(url_for('login'))

@app.route('/progreso')
def progreso():
    return jsonify(progress)

@app.route('/procesar', methods=['POST'])
def procesar():
    global progress
    progress = {"current": 0, "total": 0, "status": "Iniciando..."}

    nombres = [nombre.strip() for nombre in request.form['nombres'].strip().split('\n')]
    periodo = request.form['periodo']
    periodofin = request.form['periodofin']
    porcentaje_comision = float(request.form['porcentaje_comision'])
    login_data = {
        "login": flask_session.get('username'),
        "password": flask_session.get('password')
    }

    threading.Thread(target=procesar_datos, args=(login_data, nombres, periodo, periodofin, porcentaje_comision)).start()
    return jsonify({"status": "Procesando en segundo plano"}), 202

@app.route('/descargar')
def descargar():
    return send_file('resultados_compras.xlsx', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)