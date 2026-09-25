"""
Servidor Flask de registro de asistentes para la Cumbre Digital COLOMBIA 2026.

Rutas:
    GET  /                    → formulario de registro
    POST /registro            → valida y guarda un asistente
    GET  /confirmacion/<id>   → pantalla de registro exitoso
    GET  /admin               → listado de asistentes
"""

import os
import re
import sqlite3

from flask import Flask, abort, g, redirect, render_template, render_template_string, request, url_for

# ===== Configuración =====
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evento.db")

AREAS = ["Tecnología", "Marketing", "Negocios", "Emprendimiento"]

# Misma regla que usa la validación en el navegador (static/js/validacion.js)
REGEX_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

LONGITUD_MAXIMA = {"nombre": 120, "email": 254, "empresa": 120}

MENSAJES_OBLIGATORIO = {
    "nombre": "Ingresa tu nombre completo.",
    "email": "Ingresa tu correo electrónico.",
    "empresa": "Ingresa el nombre de tu empresa u organización.",
    "area": "Selecciona un área de interés.",
}

app = Flask(__name__)


# ===== Base de datos =====
def obtener_bd():
    """Devuelve la conexión a SQLite de la petición actual (se abre una sola vez por petición)."""
    if "bd" not in g:
        g.bd = sqlite3.connect(RUTA_BD)
        g.bd.row_factory = sqlite3.Row  # permite acceder a las columnas por nombre
    return g.bd


@app.teardown_appcontext
def cerrar_bd(_error):
    """Cierra la conexión al terminar cada petición."""
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def inicializar_bd():
    """Crea la tabla de asistentes si todavía no existe."""
    areas_sql = ", ".join(f"'{area}'" for area in AREAS)
    with sqlite3.connect(RUTA_BD) as bd:
        bd.execute(f"""
            CREATE TABLE IF NOT EXISTS asistentes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre         TEXT NOT NULL,
                email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
                empresa        TEXT NOT NULL,
                area           TEXT NOT NULL CHECK (area IN ({areas_sql})),
                fecha_registro TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def numero_registro(id_asistente):
    """Convierte el id de la base de datos al formato REG-0001."""
    return f"REG-{id_asistente:04d}"


def a_diccionario(fila):
    """Convierte una fila de SQLite en diccionario y le agrega el número de registro."""
    asistente = dict(fila)
    asistente["numero"] = numero_registro(asistente["id"])
    return asistente


# ===== Validación =====
def validar(datos):
    """Devuelve un diccionario {campo: mensaje} con los errores encontrados (vacío si todo es válido)."""
    errores = {}

    for campo, mensaje in MENSAJES_OBLIGATORIO.items():
        if not datos[campo]:
            errores[campo] = mensaje

    for campo, maximo in LONGITUD_MAXIMA.items():
        if campo not in errores and len(datos[campo]) > maximo:
            errores[campo] = f"Máximo {maximo} caracteres."

    if "email" not in errores and not REGEX_EMAIL.match(datos["email"]):
        errores["email"] = "Ingresa un correo electrónico válido (ej. nombre@empresa.com)."

    if "area" not in errores and datos["area"] not in AREAS:
        errores["area"] = "Selecciona un área de interés válida."

    return errores


# ===== Rutas =====
@app.get("/")
def inicio():
    """Muestra el formulario de registro vacío."""
    return render_template("index.html", areas=AREAS, datos={}, errores={})


@app.post("/registro")
def registrar():
    """Valida los datos, guarda al asistente y redirige a la confirmación."""
    datos = {
        "nombre": request.form.get("nombre", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "empresa": request.form.get("empresa", "").strip(),
        "area": request.form.get("area", "").strip(),
    }

    errores = validar(datos)

    if not errores:
        bd = obtener_bd()
        try:
            # Consulta con parámetros (?) para evitar inyección SQL
            cursor = bd.execute(
                "INSERT INTO asistentes (nombre, email, empresa, area) VALUES (?, ?, ?, ?)",
                (datos["nombre"], datos["email"], datos["empresa"], datos["area"]),
            )
            bd.commit()
        except sqlite3.IntegrityError:
            errores["email"] = "Este correo ya está registrado."
        else:
            # Redirigir después del POST evita registros duplicados al recargar la página
            return redirect(url_for("confirmacion", id_asistente=cursor.lastrowid))

    # Hubo errores: se vuelve a mostrar el formulario con los mensajes y los datos escritos
    return render_template("index.html", areas=AREAS, datos=datos, errores=errores), 400


@app.get("/confirmacion/<int:id_asistente>")
def confirmacion(id_asistente):
    """Muestra la pantalla de registro exitoso de un asistente."""
    fila = obtener_bd().execute(
        "SELECT * FROM asistentes WHERE id = ?", (id_asistente,)
    ).fetchone()

    if fila is None:
        abort(404)

    return render_template("confirmacion.html", asistente=a_diccionario(fila))


@app.get("/admin")
def admin():
    """Lista todos los asistentes con el total y el conteo por área."""
    filas = obtener_bd().execute(
        "SELECT * FROM asistentes ORDER BY id DESC"
    ).fetchall()
    asistentes = [a_diccionario(fila) for fila in filas]

    conteo_areas = {area: 0 for area in AREAS}
    for asistente in asistentes:
        conteo_areas[asistente["area"]] += 1

    return render_template("admin.html", asistentes=asistentes, conteo_areas=conteo_areas)


@app.errorhandler(404)
def no_encontrado(_error):
    """Página 404 en español con el mismo diseño del sitio."""
    plantilla = """
        {% extends "base.html" %}
        {% block titulo %}Página no encontrada{% endblock %}
        {% block contenido %}
          <h2>Página no encontrada</h2>
          <p class="ayuda">El registro o la página que buscas no existe.</p>
          <a href="{{ url_for('inicio') }}" class="boton">Ir al formulario de registro</a>
        {% endblock %}
    """
    return render_template_string(plantilla), 404


# La tabla se crea al importar el módulo, así funciona tanto con `flask run` como con gunicorn
inicializar_bd()


if __name__ == "__main__":
    # Solo para desarrollo local; en Render se usa gunicorn (ver Procfile)
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=puerto, debug=True)
