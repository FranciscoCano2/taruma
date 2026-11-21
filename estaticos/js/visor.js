// Visor 3D de la pagina de producto (T12a). Mejora progresiva: sin JavaScript el boton
// "Ver en 3D" queda oculto y la pagina se ve completa con la imagen fija.
// Ningun texto vive aca: salen del HTML del servidor (data-* de #visor y el
// <template id="visor-plantilla">), asi respetan ES/EN. model-viewer se importa recien
// al apretar el boton.

const raiz = document.getElementById("visor");
const abrir = document.querySelector(".ver3d");
const plantilla = document.getElementById("visor-plantilla");
const estado = document.querySelector(".visor-estado");
const quieto = matchMedia("(prefers-reduced-motion: reduce)");

const PASO = Math.PI / 8; // 22,5 grados por toque de los botones de girar
const ZOOM = 0.8; // cada toque de acercar achica el campo visual un 20 %

let biblioteca = null; // promesa del import de model-viewer
let marco = null;
let mv = null;
let intento = 0; // invalida eventos de cargas canceladas o reintentadas
let destino = null; // angulo pedido por los botones de girar, mientras la camara llega

function cargarBiblioteca() {
  if (!biblioteca) {
    const { mv: url, meshopt } = raiz.dataset;
    // model-viewer lee esta configuracion al crear el primer visor: decodificador local, sin CDN.
    self.ModelViewerElement = Object.assign(self.ModelViewerElement || {},
      { meshoptDecoderLocation: meshopt });
    biblioteca = import(url).then((modulo) => {
      modulo.ModelViewerElement.meshoptDecoderLocation = meshopt;
      return modulo;
    }, (error) => {
      biblioteca = null; // que "Reintentar" lo vuelva a pedir
      throw error;
    });
  }
  return biblioteca;
}

function parte(selector) {
  return marco.querySelector(selector);
}

function mostrar(fase) {
  // Mientras no termina de cargar, el visor es invisible y se ve la imagen fija de abajo.
  marco.classList.toggle("cargando", fase !== "listo");
  parte(".visor-carga").hidden = fase !== "carga";
  parte(".visor-error").hidden = fase !== "error";
  parte(".visor-ayuda").hidden = fase !== "listo";
  parte(".visor-botones").hidden = fase !== "listo";
}

function progreso(fraccion) {
  const n = Math.max(0, Math.min(100, Math.round(fraccion * 100)));
  parte("progress").value = n;
  parte(".visor-porcentaje").textContent = raiz.dataset.progreso.replace("{n}", String(n));
}

function quitarVisor() {
  destino = null;
  if (mv) {
    mv.remove();
    mv = null;
  }
}

async function cargarModelo() {
  const yo = ++intento;
  quitarVisor();
  mostrar("carga");
  progreso(0);
  parte('[data-accion="cancelar"]').focus();
  try {
    await cargarBiblioteca();
  } catch {
    if (yo === intento && marco) fallo();
    return;
  }
  if (yo !== intento || !marco) return;
  const d = raiz.dataset;
  mv = document.createElement("model-viewer");
  mv.setAttribute("alt", d.alt);
  mv.setAttribute("poster", d.poster);
  mv.setAttribute("camera-controls", "");
  mv.setAttribute("touch-action", "pan-y");
  mv.setAttribute("interaction-prompt", "none");
  mv.setAttribute("shadow-intensity", "1");
  mv.setAttribute("loading", "eager");
  if (!quieto.matches) mv.setAttribute("auto-rotate", "");
  mv.addEventListener("progress", (e) => {
    if (yo === intento) progreso(e.detail.totalProgress);
  });
  mv.addEventListener("load", () => {
    if (yo === intento) listo();
  });
  mv.addEventListener("camera-change", (e) => {
    if (e.detail.source === "user-interaction") destino = null;
  });
  mv.addEventListener("error", () => {
    if (yo === intento) fallo();
  });
  mv.setAttribute("src", d.modelo);
  const hojas = sacarEstilos(mv);
  marco.prepend(mv);
  const sombra = mv.shadowRoot;
  sombra.adoptedStyleSheets = [...sombra.adoptedStyleSheets, ...hojas];
}

// model-viewer arma en su constructor un <style> dentro de su shadow DOM, y la CSP
// (style-src 'self') lo bloquearia al conectarse. Antes de conectarlo pasamos ese CSS (el de
// la propia biblioteca, servida desde 'self') a hojas construidas y sacamos el <style>. Las
// hojas se adoptan despues de conectarlo: al conectarse, Lit reemplaza adoptedStyleSheets.
function sacarEstilos(elemento) {
  const hojas = [];
  for (const estilo of elemento.shadowRoot?.querySelectorAll("style") ?? []) {
    const hoja = new CSSStyleSheet();
    hoja.replaceSync(estilo.textContent);
    hojas.push(hoja);
    estilo.remove();
  }
  return hojas;
}

function listo() {
  progreso(1);
  mostrar("listo");
  parte(".visor-botones button").focus();
  enfocarModelo();
}

// El area que recibe las flechas es interna de model-viewer y recien se puede enfocar cuando
// se muestra el modelo (a veces despues de "load"). Si no se pudo, se reintenta al quitarse
// el poster, siempre que el foco siga dentro del visor. Si nada de eso anda, queda el boton.
function enfocarModelo() {
  const area = mv?.shadowRoot?.querySelector(".userInput");
  if (!area) return;
  area.focus();
  if (mv.shadowRoot.activeElement === area) return;
  const yo = mv;
  mv.addEventListener("poster-dismissed", () => {
    if (yo === mv && marco?.contains(document.activeElement)) area.focus();
  }, { once: true });
}

function fallo() {
  quitarVisor();
  mostrar("error");
  parte('[data-accion="reintentar"]').focus();
}

function armar() {
  if (marco) return;
  estado.textContent = "";
  marco = plantilla.content.firstElementChild.cloneNode(true);
  marco.addEventListener("click", alClic);
  marco.addEventListener("keydown", alTecla);
  document.addEventListener("keydown", alEscape);
  raiz.append(marco);
  abrir.hidden = true;
  cargarModelo();
}

function cerrar(cancelado) {
  if (!marco) return;
  intento++;
  quitarVisor();
  marco.remove();
  marco = null;
  document.removeEventListener("keydown", alEscape);
  abrir.hidden = false;
  abrir.focus();
  estado.textContent = cancelado ? raiz.dataset.cancelado : "";
}

// getCameraOrbit() da la posicion de ese momento: con dos toques seguidos, el segundo
// leeria la camara a mitad de camino. Sumamos sobre el angulo pedido hasta que el usuario
// mueva la camara con el mouse, el dedo o las flechas.
function girar(delta) {
  const o = mv.getCameraOrbit();
  destino = (destino ?? o.theta) + delta;
  mv.autoRotate = false;
  mv.cameraOrbit = `${destino}rad ${o.phi}rad ${o.radius}m`;
}

// mv.zoom() simula la rueda y no siempre la toma: cambiamos el campo visual
// (model-viewer lo limita a su minimo y maximo).
function acercar(factor) {
  mv.autoRotate = false;
  mv.fieldOfView = `${mv.getFieldOfView() * factor}deg`;
}

// Arrastrar o la rueda no cambian las propiedades: si ya valen "auto", asignar "auto" de
// nuevo no haria nada. Un valor vacio antes fuerza la actualizacion (Lit la junta en una).
function forzar(propiedad, valor) {
  mv[propiedad] = "";
  mv[propiedad] = valor;
}

function restablecer() {
  destino = null;
  mv.autoRotate = !quieto.matches;
  mv.resetTurntableRotation(0);
  forzar("cameraOrbit", "auto auto auto");
  forzar("fieldOfView", "auto");
}

const ACCIONES = {
  cancelar: () => cerrar(true),
  cerrar: () => cerrar(false),
  reintentar: () => cargarModelo(),
  izquierda: () => girar(-PASO),
  derecha: () => girar(PASO),
  acercar: () => acercar(ZOOM),
  alejar: () => acercar(1 / ZOOM),
  restablecer,
};

function alClic(e) {
  const boton = e.target.closest("button[data-accion]");
  if (!boton) return;
  const accion = ACCIONES[boton.dataset.accion];
  if (accion && (mv || !["izquierda", "derecha", "acercar", "alejar", "restablecer"]
    .includes(boton.dataset.accion))) accion();
}

function alTecla(e) {
  // Las flechas las maneja model-viewer; + y - acercan y alejan.
  if (!mv || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "+" || e.key === "=") acercar(ZOOM);
  else if (e.key === "-" || e.key === "−") acercar(1 / ZOOM);
  else return;
  e.preventDefault();
}

function alEscape(e) {
  if (e.key !== "Escape") return;
  e.preventDefault();
  cerrar(!parte(".visor-carga").hidden);
}

if (raiz && abrir && plantilla && estado) {
  abrir.hidden = false;
  abrir.addEventListener("click", armar);
}
