// ===== Validación del formulario en el navegador =====
// Da respuesta inmediata al usuario. El servidor vuelve a validar todo,
// así que esta capa es solo una comodidad, no una medida de seguridad.

const formulario = document.getElementById("formulario-registro");

// Campos del formulario que se validan
const campos = ["nombre", "email", "empresa", "area"].map(
  (id) => document.getElementById(id)
);

// Expresión regular para validar el formato del correo electrónico
const REGEX_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// Mensajes de error en español para cada campo vacío
const MENSAJES_OBLIGATORIO = {
  nombre: "Ingresa tu nombre completo.",
  email: "Ingresa tu correo electrónico.",
  empresa: "Ingresa el nombre de tu empresa u organización.",
  area: "Selecciona un área de interés."
};

/**
 * Valida un campo y devuelve el mensaje de error correspondiente,
 * o una cadena vacía si el valor es válido.
 */
function validarCampo(campo) {
  const valor = campo.value.trim();

  if (valor === "") {
    return MENSAJES_OBLIGATORIO[campo.id];
  }

  if (campo.id === "email" && !REGEX_EMAIL.test(valor)) {
    return "Ingresa un correo electrónico válido (ej. nombre@empresa.com).";
  }

  return "";
}

/**
 * Muestra u oculta el mensaje de error de un campo y actualiza su estilo.
 */
function mostrarError(campo, mensaje) {
  const contenedor = campo.closest(".campo");
  const spanError = document.getElementById("error-" + campo.id);

  spanError.textContent = mensaje;
  contenedor.classList.toggle("invalido", mensaje !== "");
  campo.setAttribute("aria-invalid", mensaje !== "" ? "true" : "false");
}

// ===== Envío del formulario =====
formulario.addEventListener("submit", (evento) => {
  let primerInvalido = null;

  // Validar todos los campos y mostrar sus errores
  campos.forEach((campo) => {
    const mensaje = validarCampo(campo);
    mostrarError(campo, mensaje);
    if (mensaje && !primerInvalido) {
      primerInvalido = campo;
    }
  });

  // Si hay errores, cancelar el envío y llevar el foco al primer campo inválido
  if (primerInvalido) {
    evento.preventDefault();
    primerInvalido.focus();
  }
});

// ===== Validación en vivo: se quita el error en cuanto el usuario lo corrige =====
campos.forEach((campo) => {
  const tipoEvento = campo.tagName === "SELECT" ? "change" : "input";
  campo.addEventListener(tipoEvento, () => {
    if (campo.closest(".campo").classList.contains("invalido")) {
      mostrarError(campo, validarCampo(campo));
    }
  });
});
