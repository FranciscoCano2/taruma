"""Textos ES/EN de Tarumá, por clave.

Los valores salen sin escapar: quien arma el HTML los escapa (S15).
"""
import string

IDIOMAS = ('es', 'en')

TEXTOS = {}

TEXTOS.update({
    "aviso.franja": (
        "Tienda de mentira: no se cobra ni se envía nada.",
        "Pretend shop: nothing is charged or shipped.",
    ),
    "aviso.modal.titulo": ("Acá todo es de mentira", "It's all made up here"),
    "aviso.modal.cuerpo": (
        "Tarumá es una tienda de prueba dentro de un portfolio. No se cobra ni se envía nada, y hasta la plata es ficticia. Probá sin miedo: lo que cargues se borra al salir o, si comprás, apenas te mandamos el correo de gracias.",
        "Tarumá is a test shop inside a portfolio. Nothing is charged or shipped, and even the money is made up. Go ahead and try it: whatever you enter is deleted when you leave or, if you buy, as soon as we send the thank-you email.",
    ),
    "aviso.modal.boton": ("Entendido", "Got it"),
    "aviso.precio.nota": (
        "Chispas: moneda ficticia. No se cobra nada.",
        "Sparks are made-up money. Nothing is charged.",
    ),
    "precio.formato": ("✦ {monto}", "✦ {monto}"),
    "aviso.pie": (
        "Tarumá es un proyecto de portfolio. Los productos no existen y las chispas (✦) no valen nada. No se cobra ni se envía nada.",
        "Tarumá is a portfolio project. The products don't exist and Sparks (✦) are worth nothing. Nothing is charged or shipped.",
    ),
    "aviso.tab.titulo": ("Tarumá · Tienda de prueba", "Tarumá · Demo shop"),
    "aviso.tab.descripcion": (
        "Tienda ficticia con modelos 3D, hecha como demo de portfolio. No se cobra ni se envía nada.",
        "A made-up shop with 3D models, built as a portfolio demo. Nothing is charged or shipped.",
    ),
    "aviso.tab.titulo.pagina": ("{pagina} · Tarumá", "{pagina} · Tarumá"),
    "etiqueta.muestra": ("Muestra sin valor", "Specimen · No value"),
    "etiqueta.muestra.aria": ("Producto de muestra, sin valor real", "Specimen product, no real value"),
    "nav.marca": ("Tarumá", "Tarumá"),
    "nav.lema": ("Objetos para una casa que no existe", "Objects for a house that doesn't exist"),
    "nav.catalogo": ("Catálogo", "Catalog"),
    "nav.carrito": ("Carrito", "Cart"),
    "nav.carrito.aria": ("Carrito, {n} productos", "Cart, {n} items"),
    "nav.ingresar": ("Ingresar", "Sign in"),
    "nav.salir": ("Salir", "Sign out"),
    "nav.volver": ("Volver al portfolio", "Back to portfolio"),
    "cat.todo": ("Todo", "All"),
    "cat.tecnologia": ("Tecnología", "Tech"),
    "cat.bazar": ("Bazar", "Housewares"),
    "idioma.etiqueta": ("Idioma", "Language"),
})
TEXTOS.update({
    "idioma.aria": ("Cambiar idioma", "Change language"),
    "idioma.es": ("Español", "Español"),
    "idioma.en": ("English", "English"),
    "idioma.leer.es": ("Leer esta página en español", "Leer esta página en español"),
    "idioma.leer.en": ("Read this page in English", "Read this page in English"),
    "nav.principal": ("Principal", "Main"),
    "nav.marca.aria": ("Tarumá, ir al catálogo", "Tarumá, go to catalog"),
    "ficha.cantidad.aria": ("Cantidad de {producto}", "Quantity of {producto}"),
    "salir.boton": ("Salir", "Sign out"),
    "salir.confirmar.titulo": ("¿Salir ahora?", "Sign out now?"),
    "salir.confirmar.cuerpo": (
        "Se borran tu correo y todo lo que cargaste. Solo quedan contadores anónimos.",
        "Your email and everything you entered will be deleted. Only anonymous counters stay.",
    ),
    "salir.confirmar.si": ("Salir", "Sign out"),
    "salir.confirmar.no": ("Quedarme", "Stay"),
    "salir.hecho": (
        "Saliste. Borramos tu correo y todo lo que cargaste; solo guardamos contadores anónimos de visitas y de correos enviados.",
        "You're signed out. We deleted your email and everything you entered; we only keep anonymous counters of visits and emails sent.",
    ),
    "ficha.ver3d": ("Ver en 3D", "View in 3D"),
    "visor.progreso": ("Cargando el modelo… {n}%", "Loading the model… {n}%"),
    "visor.progreso.nota": (
        "Mientras tanto, ves una imagen fija.",
        "You're looking at a still image for now.",
    ),
    "visor.error": (
        "No se pudo cargar el modelo 3D. Probá de nuevo; si sigue igual, quedate con la imagen.",
        "The 3D model didn't load. Try again, or stick with the still image.",
    ),
    "visor.error.boton": ("Reintentar", "Retry"),
    "visor.gestos.girar": ("Arrastrá para girar.", "Drag to rotate."),
    "visor.gestos.acercar": (
        "Pellizcá o usá la rueda del mouse para acercar.",
        "Pinch or scroll to zoom in.",
    ),
    "visor.cerrar": ("Cerrar", "Close"),
    "ficha.agregar": ("Agregar al carrito", "Add to cart"),
    "ficha.agregado": ("Agregado al carrito.", "Added to cart."),
    "visor.cancelar": ("Cancelar", "Cancel"),
    "visor.cancelado": (
        "Carga cancelada. Seguís viendo la imagen fija.",
        "Loading canceled. You're still looking at the still image.",
    ),
    "visor.progreso.aria": ("Progreso de carga", "Loading progress"),
    "visor.lienzo.aria": ("Modelo 3D de {producto}", "3D model of {producto}"),
    "visor.teclado.ayuda": (
        "Con teclado: flechas para girar, + y − para acercar.",
        "With a keyboard: arrow keys to rotate, + and − to zoom in.",
    ),
})
TEXTOS.update({
    "visor.girar.izquierda": ("Girar a la izquierda", "Rotate left"),
    "visor.girar.derecha": ("Girar a la derecha", "Rotate right"),
    "visor.acercar": ("Acercar", "Zoom in"),
    "visor.alejar": ("Alejar", "Zoom out"),
    "visor.restablecer": ("Restablecer vista", "Reset view"),
    "visor.cerrar.aria": ("Cerrar el visor 3D", "Close the 3D viewer"),
    "carrito.titulo": ("Carrito", "Cart"),
    "carrito.vacio": (
        "El carrito está vacío. Mirá el catálogo y sumá lo que quieras: total, es de mentira.",
        "Your cart is empty. Browse the catalog and add whatever you like. None of it is real anyway.",
    ),
    "carrito.vacio.boton": ("Ver catálogo", "Browse catalog"),
    "carrito.cantidad": ("{n} producto / {n} productos", "{n} item / {n} items"),
    "carrito.unidades": ("Cantidad", "Quantity"),
    "carrito.unidades.mas": ("Sumar una", "Add one"),
    "carrito.unidades.menos": ("Restar una", "Remove one"),
    "carrito.unidades.aria": ("{producto}: {n} unidades", "{producto}: {n} units"),
    "carrito.unidades.aria.uno": ("{producto}: 1 unidad", "{producto}: 1 unit"),
    "carrito.linea": ("{n} × ✦ {monto}", "{n} × ✦ {monto}"),
    "ficha.agregado.otra": (
        "Ya estaba en el carrito: ahora tenés {n}.",
        "It was already in your cart: now you have {n}.",
    ),
    "carrito.quitar": ("Quitar", "Remove"),
    "carrito.quitado": ("Quitaste {producto}.", "Removed {producto}."),
    "carrito.total": (
        "Total: ✦ {monto} chispas (moneda ficticia)",
        "Total: ✦ {monto} Sparks (made-up currency)",
    ),
    "carrito.continuar": ("Continuar", "Continue"),
    "carrito.nota": (
        "Para seguir hace falta ingresar con tu correo.",
        "You'll need to sign in with your email to go on.",
    ),
    "ingreso.titulo": ("Ingresar", "Sign in"),
    "ingreso.cuerpo": (
        "Solo te pedimos el correo. Te mandamos un enlace para entrar, sin contraseña. No hace falta tarjeta ni dirección. El enlace sirve una sola vez y vence en 15 minutos.",
        "We only ask for your email. We send you a link to get in, no password. No card or address needed. The link works once and expires in 15 minutes.",
    ),
})
TEXTOS.update({
    "ingreso.dato": (
        "Usamos tu correo para mandarte el enlace y, si hacés la compra de prueba, un mensaje al final. Se borra cuando tocás Salir, si no comprás, o apenas te mandamos ese mensaje, si comprás. Solo guardamos contadores anónimos de visitas y de correos enviados.",
        "We use your email to send the link and, if you run the test purchase, one message at the end. It's deleted when you tap Sign out, if you don't buy, or as soon as we send that message, if you do. We only keep anonymous counters of visits and emails sent.",
    ),
    "ingreso.campo": ("Correo", "Email"),
    "ingreso.campo.ejemplo": ("vos@ejemplo.com", "you@example.com"),
    "ingreso.boton": ("Enviar enlace", "Send link"),
    "ingreso.enviado.titulo": ("Revisá tu correo", "Check your email"),
    "ingreso.enviado.cuerpo": (
        "Te mandamos un enlace a {correo}. Tocalo para entrar. Vence en 15 minutos y sirve una sola vez. Si no llega, mirá en spam.",
        "We sent a link to {correo}. Tap it to get in. It expires in 15 minutes and works once. If it doesn't show up, check spam.",
    ),
    "ingreso.enviado.boton": ("Pedir otro", "Send another"),
    "ingreso.vencido.titulo": ("El enlace venció", "This link has expired"),
    "ingreso.vencido.cuerpo": (
        "Los enlaces duran 15 minutos, por seguridad. Pedí uno nuevo y entrás enseguida.",
        "Links last 15 minutes, for safety. Ask for a new one and you're in.",
    ),
    "ingreso.vencido.boton": ("Pedir otro", "Send another"),
    "ingreso.enlace.titulo": ("Este enlace no sirve", "This link doesn't work"),
    "ingreso.enlace.cuerpo": (
        "Puede que ya se haya usado o que esté incompleto: cada enlace sirve una sola vez. Pedí uno nuevo y entrás enseguida.",
        "It may have been used already or be incomplete: each link works once. Ask for a new one and you're in.",
    ),
    "ingreso.enlace.boton": ("Pedir otro", "Send another"),
    "ingreso.invalido": (
        "Ese correo no parece válido. Fijate que tenga @ y un dominio, como nombre@correo.com.",
        "That email doesn't look valid. Check for an @ and a domain, like name@mail.com.",
    ),
    "correo.enlace.asunto": ("Tu enlace para entrar a Tarumá", "Your link to sign in to Tarumá"),
    "correo.enlace.saludo": ("Hola,", "Hi,"),
    "correo.enlace.cuerpo": (
        "Pediste entrar a Tarumá, la tienda de prueba. Tocá el botón y listo.",
        "You asked to sign in to Tarumá, the test shop. Tap the button and you're in.",
    ),
    "correo.enlace.boton": ("Entrar a Tarumá", "Enter Tarumá"),
    "correo.enlace.vence": (
        "El enlace sirve una sola vez y vence en 15 minutos.",
        "The link works once and expires in 15 minutes.",
    ),
    "correo.enlace.ignorar": (
        "Si no fuiste vos, ignorá este mensaje. Mientras nadie toque el enlace, no pasa nada.",
        "If this wasn't you, ignore this message. As long as nobody taps the link, nothing happens.",
    ),
    "correo.enlace.pie": (
        "Tarumá es una demo de portfolio. No se cobra ni se envía nada.",
        "Tarumá is a portfolio demo. Nothing is charged or shipped.",
    ),
    "checkout.titulo": ("Resumen", "Summary"),
    "checkout.subtitulo": ("Tu pedido de prueba", "Your test order"),
    "checkout.total": (
        "Total: ✦ {monto} chispas (moneda ficticia)",
        "Total: ✦ {monto} Sparks (made-up currency)",
    ),
})
TEXTOS.update({
    "checkout.correo": ("Te escribimos a {correo}.", "We'll write to {correo}."),
    "checkout.boton": ("Comprar de mentira", "Pretend to buy"),
    "checkout.aclaracion": (
        "No se cobra ni se envía nada. No hay tarjeta ni dirección que cargar. Al terminar te mandamos un correo y, apenas sale, se borra todo lo que ingresaste.",
        "Nothing is charged and nothing ships. There's no card or address to enter. When you finish we send you an email and, as soon as it's out, everything you entered is deleted.",
    ),
    "confirmacion.titulo": ("Compra de prueba hecha", "Test purchase done"),
    "confirmacion.cuerpo": (
        "No se cobró nada y no hay nada en camino. Te escribimos a {correo} para agradecerte y pedirte tu opinión. Apenas sale ese correo, se borra lo que cargaste.",
        "Nothing was charged and nothing is on its way. We're writing to {correo} to thank you and ask what you thought. As soon as that email goes out, what you entered is deleted.",
    ),
    "confirmacion.boton": ("Seguir mirando", "Keep browsing"),
    "correo.gracias.asunto": ("Gracias por probar Tarumá", "Thanks for trying Tarumá"),
    "correo.gracias.saludo": ("Hola,", "Hi,"),
    "correo.gracias.agradece": (
        "Gracias por hacer la compra de prueba en Tarumá.",
        "Thanks for running the test purchase at Tarumá.",
    ),
    "correo.gracias.borrado": (
        "Como quedamos, no se cobró ni se envió nada. Y con este correo ya enviado, borramos todo lo que ingresaste en la demo, tu correo incluido. Lo único que guardamos son contadores anónimos (cuántas visitas hubo y cuántos correos se enviaron), sin nada tuyo. Este mensaje queda en tu casilla, no en la nuestra. Google puede guardar registros del envío según su propia política.",
        "As promised, nothing was charged and nothing shipped. With this email sent, we've deleted everything you entered in the demo, your email included. All we keep are anonymous counters (how many visits, how many emails sent), nothing about you. This message sits in your inbox, not ours. Google may keep delivery logs under its own policy.",
    ),
    "correo.gracias.pregunta": (
        "Una pregunta: ¿en qué pantalla dudaste o te perdiste primero? Con una línea alcanza.",
        "One question: which screen was the first place you hesitated or got lost? One line is plenty.",
    ),
    "correo.gracias.responder": (
        "Para contestar, respondé este correo. Las respuestas las leo yo.",
        "To answer, just reply to this email. I read the replies myself.",
    ),
    "correo.gracias.salida": (
        "Si preferís no opinar, también está bien.",
        "If you'd rather not say, that's fine too.",
    ),
    "correo.gracias.firma": ("Francisco Cano, de Tarumá", "Francisco Cano, from Tarumá"),
    "error.offline.titulo": ("Sin conexión", "You're offline"),
    "error.offline.cuerpo": (
        "Parece que se cortó internet. Revisá la conexión y probá de nuevo.",
        "Your internet seems to have dropped. Check your connection and try again.",
    ),
    "error.offline.boton": ("Reintentar", "Try again"),
    "error.404.titulo": ("No encontramos esta página", "Page not found"),
    "error.404.cuerpo": (
        "El enlace está mal o la página ya no existe. Este sí es un error de verdad.",
        "The link is wrong or the page is gone. This error, at least, is real.",
    ),
    "error.404.boton": ("Ir al catálogo", "Go to catalog"),
    "error.apagada.titulo": ("La demo está fuera de línea", "The demo is offline"),
    "error.apagada.cuerpo": (
        "Tarumá está apagada por ahora. El resto del portfolio sigue en pie.",
        "Tarumá is switched off for now. The rest of the portfolio is still up.",
    ),
    "error.apagada.boton": ("Volver al portfolio", "Back to portfolio"),
    "error.intentos.titulo": ("Demasiados intentos", "Too many attempts"),
})
TEXTOS.update({
    "error.intentos.cuerpo": (
        "Pediste varios enlaces seguidos. Esperá 10 minutos y probá de nuevo.",
        "You asked for several links in a row. Wait 10 minutes and try again.",
    ),
    "error.intentos.boton": ("Volver", "Back"),
    "error.generico": (
        "Algo falló de nuestro lado. Probá de nuevo en un rato.",
        "Something broke on our end. Try again in a bit.",
    ),
    "ingreso.dato.abandono": (
        "Si cerrás sin tocar Salir, se borra solo a las 2 horas.",
        "If you close the tab without signing out, it's deleted on its own after 2 hours.",
    ),
    "ingreso.dato.gmail": (
        "Los correos salen por Gmail y borramos la copia enviada apenas sale. Google puede guardar registros del envío según su propia política.",
        "Emails go out through Gmail, and we delete the sent copy right away. Google may keep delivery logs under its own policy.",
    ),
    "ingreso.confirmar.titulo": ("Entrar a Tarumá", "Sign in to Tarumá"),
    "ingreso.confirmar.cuerpo": (
        "Tocá el botón para entrar. El enlace se usa una sola vez.",
        "Tap the button to get in. The link works only once.",
    ),
    "ingreso.confirmar.boton": ("Entrar", "Sign in"),
    "checkout.saldo": ("Tu saldo: ✦ {monto} chispas", "Your balance: ✦ {monto} Sparks"),
    "checkout.sin_saldo": (
        "No te alcanzan las chispas. Sacá algo del carrito.",
        "You don't have enough Sparks. Take something out of your cart.",
    ),
    "ficha.agregado.ver": ("Ver carrito", "View cart"),
    "nav.saltar": ("Ir al contenido", "Skip to content"),
})
TEXTOS.update({
    "saldo.disponible": (
        "Saldo disponible: ✦ {monto} chispas",
        "Available balance: ✦ {monto} Sparks",
    ),
    "carrito.subtotal": ("Subtotal: ✦ {monto}", "Subtotal: ✦ {monto}"),
    "carrito.saldo": ("Te quedan ✦ {monto} chispas", "You have ✦ {monto} Sparks left"),
    "carrito.actualizar": ("Cambiar", "Update"),
    "carrito.sin_saldo": (
        "No te alcanzan las chispas para eso. Probá con menos unidades o sacá algo del carrito.",
        "You don't have enough Sparks for that. Try fewer units or take something out of your cart.",
    ),
    "carrito.maximo": ("Hasta 9 unidades por producto.", "Up to 9 units per item."),
})
TEXTOS.update({
    "ingreso.enviado.cuerpo.anonimo": (
        "Te mandamos un enlace al correo que escribiste. Tocalo para entrar. Vence en 15 minutos y sirve una sola vez. Si no llega, mirá en spam.",
        "We sent a link to the email you entered. Tap it to get in. It expires in 15 minutes and works once. If it doesn't show up, check spam.",
    ),
    "ingreso.hecho": (
        "Listo, entraste. Tu carrito sigue como lo dejaste.",
        "You're in. Your cart is just as you left it.",
    ),
    "ingreso.ya": (
        "Ya entraste a Tarumá. Cuando quieras, tocá Salir y se borra todo.",
        "You're already signed in to Tarumá. Whenever you like, tap Sign out and everything is deleted.",
    ),
})
TEXTOS.update({
    "confirmacion.cuerpo.anonimo": (
        "No se cobró nada y no hay nada en camino. Te escribimos al correo con el que entraste para agradecerte y pedirte tu opinión. Ese correo ya salió, así que borramos lo que cargaste.",
        "Nothing was charged and nothing is on its way. We wrote to the email you signed in with to thank you and ask what you thought. That email is out, so we deleted what you entered.",
    ),
    "carrito.ingresar.boton": ("Ingresar para comprar", "Sign in to buy"),
    "carrito.comprando": (
        "Tu compra de prueba se está enviando: el carrito no se puede cambiar ahora.",
        "Your test purchase is being sent: the cart can't change right now.",
    ),
})


def campos(texto):
    """Nombres de los {valores} que pide un texto."""
    return {c for _, c, _, _ in string.Formatter().parse(texto) if c}


def t(clave, idioma, **valores):
    if idioma not in IDIOMAS:
        raise ValueError('idioma')
    texto = TEXTOS[clave][IDIOMAS.index(idioma)]
    faltan = sorted(campos(texto) - set(valores))
    if faltan:
        raise KeyError(clave + ': falta ' + ', '.join(faltan))
    return string.Formatter().vformat(texto, (), valores)


def unidades(n, producto, idioma):
    """Rótulo accesible del grupo de cantidad; producto es el nombre ya traducido (R#11)."""
    if type(n) is not int or not 1 <= n <= 9:
        raise ValueError('n')
    if n == 1:
        return t('carrito.unidades.aria.uno', idioma, producto=producto)
    return t('carrito.unidades.aria', idioma, producto=producto, n=n)
