"use strict";
/* Ayuda (#ayuda): para qué sirve cada apartado y cómo se usa. Se abre con el botón «i» de la cabecera.
   Cada apartado es un desplegable con «Para qué sirve», «Cómo se usa» y un botón para ir allí. */

const AYUDA = [
  { id: "hoy", icono: "🏠", titulo: "Hoy", ir: "hoy",
    para: "Es la portada: lo más importante de un vistazo, sin tener que entrar en cada lonja.",
    pasos: [
      "<b>Pizarra de la semana</b>: los productos principales (trigo, cebada, maíz, cerdo, lechazo…) con la media de las lonjas que los cotizan y la horquilla de la más baja a la más alta. Toca uno para ver dónde se paga más.",
      "<b>Para decidir</b>: acceso directo a tus herramientas (Mi explotación, ¿Me están pagando bien?, ¿Caro o barato? y la calculadora).",
      "<b>Resumen de la semana</b>: lo que más ha subido y bajado, y un botón para compartirlo por WhatsApp.",
      "<b>Plazos del campo</b>: los cobros y trámites de la PAC con su cuenta atrás.",
      "Debajo, el estado de cada lonja: cuándo fue su última sesión y cuándo es la próxima.",
    ] },
  { id: "lonjas", icono: "📋", titulo: "Lonjas", ir: "lonjas",
    para: "Todos los precios de cada lonja de Castilla y León (Salamanca, León, Segovia, Lerma…), tal y como los publica.",
    pasos: [
      "Toca una lonja para ver su última sesión, ordenada por mesas (cereales, porcino, ovino, vacuno…).",
      "Usa los botones de arriba para quedarte con una mesa, o el buscador para encontrar un producto escribiendo parte de su nombre.",
      "Cada fila tiene el precio de hoy y la diferencia con la sesión anterior: <b>▲</b> sube, <b>▼</b> baja, <b>=</b> repite.",
      "«Sin cotizar» quiere decir que ese producto no salió en la última sesión; verás su último precio y la fecha.",
      "Toca cualquier producto para abrir su ficha (más abajo). Toca la estrella ☆ para guardarlo en Favoritos.",
      "Al final están «Estado de las fuentes», «Fuentes y método» y «Datos abiertos y widget».",
    ] },
  { id: "ficha", icono: "📈", titulo: "Ficha de un producto", ir: "lonjas",
    para: "Todo sobre un producto de una lonja: su evolución, si está caro o barato y los avisos.",
    pasos: [
      "Ábrela tocando un producto en cualquier lista.",
      "El gráfico enseña cómo ha ido el precio; debajo, el histórico oficial de la Junta y la etiqueta <b>¿Caro o barato?</b> (Alto, Normal, Bajo…).",
      "<b>Avisarme del precio</b>: escribe una cifra y la app te avisa cuando la lonja la cruce, hacia arriba o hacia abajo.",
      "<b>Calcular cuánto me pagan</b>: abre la calculadora con ese producto.",
      "<b>☆ Añadir a favoritos</b>: lo guarda en Favoritos. Para verlo en todas las lonjas a la vez, ve a Comparar.",
    ] },
  { id: "comparar", icono: "📊", titulo: "Comparar", ir: "comparar",
    para: "Saber qué lonja paga más por un producto esta semana.",
    pasos: [
      "Elige el producto arriba (trigo, cebada, cerdo, lechazo…).",
      "Las lonjas salen ordenadas de la que más paga a la que menos, con la fecha de su sesión.",
      "<b>Diferencias habituales</b>: cuánto suele pagar una lonja más que otra, semana a semana, y si esta semana la diferencia es la de siempre.",
      "Recuerda: cada lonja cotiza en sus condiciones (calidad, punto de entrega, porte), así que parte de la diferencia viene de ahí.",
    ] },
  { id: "historico", icono: "🗓️", titulo: "Histórico", ir: "historico",
    para: "Ver cómo han ido los precios semana a semana desde 2025, con los datos oficiales de la Junta de Castilla y León.",
    pasos: [
      "Elige el ámbito (Castilla y León o toda España), la categoría, el producto, la provincia, la lonja y el periodo.",
      "Compara este año con el anterior, mira la tendencia de las últimas sesiones o pon varias lonjas en el mismo gráfico.",
      "Toca o pasa el dedo por el gráfico para ver el precio de cada semana.",
      "Con <b>⇩ Imagen</b> guardas o compartes el gráfico; con <b>⇩ Excel (CSV)</b> te llevas los datos.",
      "Los cereales se muestran en €/t, como en las lonjas (la Junta los publica en €/100 kg).",
    ] },
  { id: "favoritos", icono: "⭐", titulo: "Favoritos y avisos", ir: "favoritos",
    para: "Tener juntos los productos que te interesan y tus avisos de precio.",
    pasos: [
      "Toca la estrella ☆ junto a cualquier producto y aparecerá aquí, en «Mis precios».",
      "En «Mis avisos» ves los avisos que has creado desde la ficha de un producto y puedes borrarlos.",
      "En Android con la app instalada, el aviso llega aunque la tengas cerrada. En iPhone, salta al abrir la app; para recibirlo siempre, usa el robot de Telegram (más abajo).",
    ] },
  { id: "explotacion", icono: "🌾", titulo: "Mi explotación", ir: "explotacion",
    para: "Saber cuánto vale esta semana lo que tienes en el silo o en la granja.",
    pasos: [
      "Elige el producto, escribe la cantidad (toneladas o kilos) y con qué precio valorarlo: la media de las lonjas, la que más paga o una lonja concreta. Pulsa «Añadir».",
      "Arriba verás el valor total y cuánto ha cambiado desde la sesión anterior.",
      "Para el ganado se valora por kilo: pon los kilos de todos los animales juntos (300 lechazos de 11 kg son 3.300 kg).",
      "Es una valoración orientativa: no descuenta portes, comisiones ni diferencias de calidad.",
    ] },
  { id: "oferta", icono: "🤝", titulo: "¿Me están pagando bien?", ir: "oferta",
    para: "Comparar lo que te ofrece tu almacén, cooperativa o tratante con lo que han pagado las lonjas esta semana.",
    pasos: [
      "Elige el producto y escribe el precio que te ofrecen (en la misma unidad: €/t para el cereal).",
      "Si escribes también la cantidad, te dice cuántos euros supone la diferencia.",
      "Verde: tu oferta paga más que esa lonja. Rojo: paga menos.",
    ] },
  { id: "termometro", icono: "🌡️", titulo: "¿Caro o barato?", ir: "termometro",
    para: "Ver si el precio de hoy está alto o bajo comparado con todas las semanas desde 2025.",
    pasos: [
      "Cada fila es un producto en una lonja, con una barra que va de «Bajo» a «Alto», el mínimo, el máximo y cómo está frente a hace un año.",
      "Toca una fila para ver su gráfico.",
      "No es una previsión: dice cómo está el precio comparado con lo que ha sido, no lo que va a hacer.",
    ] },
  { id: "calculadora", icono: "🧮", titulo: "Calculadora de venta", ir: "calculadora",
    para: "Calcular cuánto te pagaría cada lonja por una partida.",
    pasos: [
      "Elige el producto y escribe la cantidad.",
      "Si quieres, descuenta el porte o los gastos por tonelada.",
      "Verás lo que saldría en cada lonja y cuánto ganas o pierdes frente a la que más paga.",
    ] },
  { id: "plazos", icono: "⏳", titulo: "Plazos del campo", ir: "plazos",
    para: "No olvidar los cobros y trámites de la PAC.",
    pasos: [
      "Cada plazo tiene su cuenta atrás y una barra que avanza mientras está abierto.",
      "Toca uno para ver los detalles y el documento oficial del que sale.",
      "«Fecha prevista» quiere decir que aún no se ha publicado para ese año: confírmalo con tu entidad colaboradora.",
    ] },
  { id: "telegram", icono: "✈️", titulo: "Telegram: canal y avisos", enlace: "https://t.me/lonjascyl_bot",
    para: "Recibir los precios y tus avisos en el móvil, también en iPhone y con la app cerrada.",
    pasos: [
      "Únete al canal <b>t.me/lonjas_cyl</b>: publica cada sesión nueva de cada lonja.",
      "Escribe al robot <b>@lonjascyl_bot</b> el nombre de un producto (trigo, lechazo…) o de una lonja (Salamanca…) y te contesta con los precios.",
      "Para un aviso: <b>/aviso trigo salamanca 240</b>. Ver los tuyos: <b>/avisos</b>. Borrar: <b>/borrar 1</b> o <b>/borrar todos</b>.",
    ] },
  { id: "instalar", icono: "📲", titulo: "Instalarla en el móvil",
    para: "Tenerla como una app más, con su icono, sin pasar por la tienda de aplicaciones.",
    pasos: [
      "<b>iPhone</b>: abre la web en Safari → botón Compartir (en iOS 26, dentro de «⋯») → «Añadir a pantalla de inicio» → «Añadir».",
      "<b>Android</b>: abre la web en Chrome → menú ⋮ → «Instalar aplicación» (o «Añadir a pantalla de inicio»).",
      "Una vez instalada funciona sin cobertura con los últimos precios que descargó.",
      "Tus favoritos, avisos y Mi explotación se guardan en el teléfono y en esa dirección: si cambias de dirección o de navegador, tendrás que volver a marcarlos.",
    ] },
  { id: "botones", icono: "🔘", titulo: "Botones de arriba",
    para: "Ajustes rápidos que están siempre a mano.",
    pasos: [
      "<b>Aa</b>: letra más grande en toda la app. Tócalo otra vez para volver al tamaño normal.",
      "<b>⟳</b>: busca precios nuevos al momento (la app también lo hace sola al abrirse).",
      "<b>i</b>: esta ayuda.",
    ] },
];

const PREGUNTAS = [
  ["¿De dónde salen los precios?", "De las publicaciones oficiales de cada lonja. Un robot las revisa tres veces al día de lunes a sábado (a mediodía, por la tarde y por la noche), y la app no cambia ninguna cifra. El detalle está en <a href=\"#metodo\">Fuentes y método</a>."],
  ["¿Por qué una lonja tiene precios de hace días?", "Cada lonja cotiza un día fijo a la semana (por ejemplo, Salamanca los lunes, León los miércoles, Segovia los jueves y Lerma los viernes), y en semanas con festivo puede cambiar. Junto a cada lonja verás cuándo es la próxima sesión."],
  ["¿Puedo comparar el precio de dos lonjas tal cual?", "Con cuidado: cada una cotiza en sus condiciones (calidad, punto de entrega, quién paga el porte). Los precios son orientativos y no son una oferta de compra."],
  ["¿Qué guarda la app de mí?", "Nada fuera de tu teléfono: no hay cuentas ni cookies. Las visitas se cuentan de forma anónima. Más en <a href=\"#metodo\">Fuentes y método → Privacidad</a>."],
  ["¿Funciona sin cobertura?", "Sí: enseña los últimos precios que descargó. Cuando vuelva la conexión, se actualiza sola."],
];

function vistaAyuda() {
  const ir = a => a.ir ? `<button class="chip auto" type="button" data-ir="${a.ir}">Ir a ${esc(a.titulo)} ›</button>`
    : a.enlace ? `<a class="chip auto" href="${esc(a.enlace)}" target="_blank" rel="noopener noreferrer">Abrir el robot ›</a>` : "";
  return `<section class="seccion ayuda">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>Cómo se usa</h2>
      <div class="meta">Toca un apartado para ver para qué sirve y cómo usarlo.</div></div>
    <nav class="ayuda-indice" aria-label="Apartados de la ayuda">${AYUDA.map(a => `<a class="chip" href="#ayuda-${a.id}">${a.icono} ${esc(a.titulo)}</a>`).join("")}</nav>
    <div class="ayuda-lista">${AYUDA.map(a => `<details class="ayuda-item" id="ayuda-${a.id}">
        <summary><span class="ayuda-ico" aria-hidden="true">${a.icono}</span><span><b>${esc(a.titulo)}</b><small>${esc(a.para)}</small></span></summary>
        <div class="ayuda-cuerpo">
          <p class="etiqueta">Cómo se usa</p>
          <ol>${a.pasos.map(p => `<li>${p}</li>`).join("")}</ol>
          ${ir(a)}
        </div>
      </details>`).join("")}</div>
    <h3 class="sub-h">Preguntas frecuentes</h3>
    <div class="ayuda-lista">${PREGUNTAS.map(([q, r]) => `<details class="ayuda-item"><summary><span><b>${esc(q)}</b></span></summary><div class="ayuda-cuerpo"><p>${r}</p></div></details>`).join("")}</div>
    <p class="nota">¿Algo no está claro o falta alguna explicación? Escríbenos por Telegram a <a href="https://t.me/lonjascyl_bot" target="_blank" rel="noopener noreferrer">@lonjascyl_bot</a>.</p>
  </section>`;
}

/* Los enlaces del índice abren y muestran su apartado (sin cambiar la ruta de la app). */
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#ayuda-"]');
  if (!a) return;
  e.preventDefault();
  const d = document.getElementById(a.getAttribute("href").slice(1));
  if (!d) return;
  d.open = true;
  d.scrollIntoView({ behavior: "smooth", block: "start" });
  d.querySelector("summary")?.focus({ preventScroll: true });
});
