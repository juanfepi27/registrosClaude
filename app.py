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

import psycopg
from dotenv import load_dotenv
from flask import Flask, abort, g, redirect, render_template, render_template_string, request, url_for
from psycopg import errors
from psycopg.rows import dict_row

# ===== Configuración =====
# En local lee el archivo .env; en Render no existe y la variable viene del panel (Environment)
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL. "
        "Cópiala en el archivo .env (ver .env.example) o configúrala en Render."
    )

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
    """Devuelve la conexión a PostgreSQL (Supabase) de la petición actual (se abre una sola vez por petición)."""
    if "bd" not in g:
        # dict_row permite acceder a las columnas por nombre;
        # prepare_threshold=None evita errores si se usa el pooler de Supabase en modo transacción
        g.bd = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)
    return g.bd


@app.teardown_appcontext
def cerrar_bd(_error):
    """Cierra la conexión al terminar cada petición."""
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def numero_registro(id_asistente):
    """Convierte el id de la base de datos al formato REG-0001."""
    return f"REG-{id_asistente:04d}"


def a_diccionario(fila):
    """Convierte una fila de PostgreSQL en diccionario y le agrega el número de registro."""
    asistente = dict(fila)
    asistente["numero"] = numero_registro(asistente["id"])
    # PostgreSQL devuelve la fecha como datetime; se muestra sin microsegundos
    asistente["fecha_registro"] = asistente["fecha_registro"].strftime("%Y-%m-%d %H:%M:%S")
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
            # Consulta con parámetros (%s) para evitar inyección SQL; RETURNING devuelve el id creado
            id_asistente = bd.execute(
                "INSERT INTO asistentes (nombre, email, empresa, area) VALUES (%s, %s, %s, %s) RETURNING id",
                (datos["nombre"], datos["email"], datos["empresa"], datos["area"]),
            ).fetchone()["id"]
            bd.commit()
        except errors.UniqueViolation:
            # En PostgreSQL la transacción queda abortada tras un error: hay que deshacerla
            bd.rollback()
            errores["email"] = "Este correo ya está registrado."
        else:
            # Redirigir después del POST evita registros duplicados al recargar la página
            return redirect(url_for("confirmacion", id_asistente=id_asistente))

    # Hubo errores: se vuelve a mostrar el formulario con los mensajes y los datos escritos
    return render_template("index.html", areas=AREAS, datos=datos, errores=errores), 400


@app.get("/confirmacion/<int:id_asistente>")
def confirmacion(id_asistente):
    """Muestra la pantalla de registro exitoso de un asistente."""
    fila = obtener_bd().execute(
        "SELECT * FROM asistentes WHERE id = %s", (id_asistente,)
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


if __name__ == "__main__":
    # Solo para desarrollo local; en Render se usa gunicorn (ver Procfile)
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=puerto, debug=True)
