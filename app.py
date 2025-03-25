from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
from graphviz import Digraph
import os
import psycopg2

DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "159753",
    "host": "localhost",
    "port": "5433"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

app = Flask(__name__)

# Configuración de la sesión
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = "159753"

Session(app)

data = {}
title_main = None

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("organigram"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre = request.form["nombre"]
        contraseña = request.form["contraseña"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT idUsuario, contraseña FROM usuarios WHERE nombre = %s", (nombre,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[1], contraseña):
            session["user_id"] = user[0]
            return redirect(url_for("organigram"))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form["nombre"]
        contraseña = generate_password_hash(request.form["contraseña"])

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO usuarios (nombre, contraseña) VALUES (%s, %s) RETURNING idUsuario",
                           (nombre, contraseña))
            user_id = cursor.fetchone()[0]
            conn.commit()
            session["user_id"] = user_id
            return redirect(url_for("organigram"))
        except psycopg2.IntegrityError:
            conn.rollback()
            return render_template("register.html", error="El usuario ya existe")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/organigram")
def organigram():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/add_person", methods=["POST"])
def add_person():
    global title_main
    req = request.json
    title = req.get("title").strip()
    name = req.get("name").strip()
    boss = req.get("boss").strip()

    if not title or not name or not boss:
        return jsonify({"success": False, "error": "Faltan datos"})

    if not title_main:
        title_main = title
        data[title_main] = []

    if boss not in data:
        data[boss] = []

    if name not in data[boss]:
        data[boss].append(name)

    data[name] = []
    create_organogram()
    return jsonify({"success": True})
def create_organogram():
    global title_main
    if not title_main:
        return  

    try:
        print("Generando organigrama...")  # 🟢 Verificar si entra en la función

        dot = Digraph(format='png')
        dot.attr(rankdir='TB', splines='ortho')  # 🟢 Asegura líneas rectas

        dot.node(title_main, shape="box", style="filled", fillcolor="lightblue")

        for boss, employees in data.items():
            if boss != title_main and not any(boss in sub for sub in data.values()):
                dot.edge(title_main, boss, constraint="true")

            for employee in employees:
                dot.node(employee, shape="box", style="filled", fillcolor="lightgray")
                dot.edge(boss, employee, constraint="true")

        filepath = "static/organigram.png"
        dot.render(filepath.replace(".png", ""))
        print("Organigrama generado correctamente.")  # 🟢 Mensaje de éxito

    except Exception as e:
        print(f"❌ Error al generar organigrama: {e}")  # 🔴 Captura de error

@app.route("/download_organigram")
def download_organigram():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return send_file("static/organigram.png", as_attachment=True, download_name="organigrama.png")
@app.route("/edit_person", methods=["POST"])
def edit_person():
    global data
    req = request.json
    old_name = req.get("oldName").strip()
    new_name = req.get("newName").strip()
    new_boss = req.get("newBoss").strip()

    if not old_name or not new_name or not new_boss:
        return jsonify({"success": False, "error": "Faltan datos"})

    if old_name not in data:
        return jsonify({"success": False, "error": "La persona no existe en el organigrama."})

    # Actualizar la estructura del organigrama
    for boss, employees in data.items():
        if old_name in employees:
            employees.remove(old_name)
            data[boss].append(new_name)
            break

    data[new_name] = data.pop(old_name)
    create_organogram()
    
    return jsonify({"success": True})
@app.route("/reset_organigram", methods=["POST"])
def reset_organigram():
    global data, title_main
    data = {}
    title_main = None

    # Eliminar la imagen actual del organigrama
    try:
        os.remove("static/organigram.png")
    except FileNotFoundError:
        pass

    return jsonify({"success": True})
@app.route("/delete_person", methods=["POST"])
def delete_person():
    req = request.json
    name = req.get("name").strip()

    if not name or name not in data:
        return jsonify({"success": False, "error": "La persona no existe en el organigrama."})

    # Buscar y eliminar a la persona en los valores de cada jefe
    for boss, employees in data.items():
        if name in employees:
            employees.remove(name)

    # Eliminar la persona del diccionario principal
    del data[name]

    create_organogram()
    return jsonify({"success": True})

@app.route("/get_organigram")
def get_organigram():
    return send_file("static/organigram.png", mimetype="image/png")

if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
    app.run(debug=True)
