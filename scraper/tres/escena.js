// Motor 3D de los reels de Lonjas CyL (three.js, MIT). Se abre en Chromium sin pantalla desde scraper/tres3d.py:
//   await montar(spec) -> duración en segundos;   cuadro(t) -> fotograma JPEG (dataURL) del segundo t.
// Todo lo que se ve sale del «spec» (textos y cifras reales que prepara Python): aquí no se inventa ningún dato.
import * as THREE from "three";

const W = 1080, H = 1920, TRANS = 0.4;
const C = { pino: 0x24503c, pino2: 0x3d7a5c, paja: 0xb9861f, paja2: 0xe0b252, papel: 0xeef1ea, suelo: 0xdde5d8,
  tinta: 0x18241d, sube: 0x23774a, baja: 0xb3402a, gris: 0x8a958d, hoja: 0xffffff, cristal: 0xcfe3ea };
const hex = n => "#" + n.toString(16).padStart(6, "0");
const ease = p => 1 - Math.pow(1 - Math.min(1, Math.max(0, p)), 3);
const tramo = (p, a, b) => Math.min(1, Math.max(0, (p - a) / (b - a)));

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.autoClear = false;
document.body.appendChild(renderer.domElement);

const escena = new THREE.Scene();
escena.background = new THREE.Color(0xe4ebe0);
escena.fog = new THREE.Fog(0xe4ebe0, 22, 60);
const camara = new THREE.PerspectiveCamera(55, W / H, 0.1, 200);
const HF = Math.tan(THREE.MathUtils.degToRad(55 / 2)) * W / H;             // media anchura visible por unidad de distancia
const lejos = media => media / HF;                                            // distancia para que quepa ±media
escena.add(new THREE.HemisphereLight(0xffffff, 0xa9b8a2, 1.3));
const sol = new THREE.DirectionalLight(0xfff4e0, 2.4);
sol.position.set(7, 14, 9);
sol.castShadow = true;
sol.shadow.mapSize.set(1024, 1024);
Object.assign(sol.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 1, far: 50 });
escena.add(sol);
const suelo = new THREE.Mesh(new THREE.CircleGeometry(40, 64), new THREE.MeshStandardMaterial({ color: C.suelo, roughness: 1 }));
suelo.rotation.x = -Math.PI / 2;
suelo.receiveShadow = true;
escena.add(suelo);

// Capa 2D (títulos y textos) encima del 3D
const hud = new THREE.Scene();
const hudCam = new THREE.OrthographicCamera(0, W, H, 0, -10, 10);

// ---------- texto ----------
function lienzo(w, h, dibujar) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d");
  dibujar(g, w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
function partir(g, texto, ancho) {
  const out = [];
  for (const parrafo of String(texto ?? "").split("\n")) {
    let linea = "";
    for (const p of parrafo.split(/\s+/).filter(Boolean)) {
      const prueba = linea ? linea + " " + p : p;
      if (g.measureText(prueba).width > ancho && linea) { out.push(linea); linea = p; } else linea = prueba;
    }
    out.push(linea);
  }
  return out;
}
function redondo(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}
/** Plano 2D en la capa de títulos (coordenadas de píxel, y hacia arriba). */
function placa(x, y, w, h, dibujar) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: lienzo(w, h, dibujar), transparent: true, depthTest: false }));
  m.position.set(x + w / 2, H - y - h / 2, 0);
  m.visible = false;
  hud.add(m);
  return m;
}
/** Cartel 3D que siempre mira a la cámara. */
function cartel(texto, { tam = 64, color = C.tinta, fondo = null, peso = 700, fuente = "Barlow Condensed", alto = 0.6, ancho = 900 } = {}) {
  let lineas = [];
  const medir = document.createElement("canvas").getContext("2d");
  medir.font = `${peso} ${tam}px "${fuente}"`;
  lineas = partir(medir, texto, ancho);
  const w = Math.ceil(Math.min(ancho, Math.max(...lineas.map(l => medir.measureText(l).width))) + (fondo != null ? 48 : 12));
  const h = Math.ceil(lineas.length * tam * 1.12 + (fondo != null ? 30 : 10));
  const tex = lienzo(w, h, g => {
    if (fondo != null) { g.fillStyle = hex(fondo); redondo(g, 0, 0, w, h, Math.min(28, h / 2)); g.fill(); }
    g.font = `${peso} ${tam}px "${fuente}"`; g.fillStyle = hex(color); g.textAlign = "center"; g.textBaseline = "middle";
    lineas.forEach((l, i) => g.fillText(l, w / 2, h / 2 + (i - (lineas.length - 1) / 2) * tam * 1.12));
  });
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  s.scale.set(alto * w / h * lineas.length / Math.max(1, lineas.length), alto * lineas.length, 1);
  s.scale.set(alto * (w / h) * lineas.length, alto * lineas.length, 1);
  return s;
}

// ---------- capa de títulos común ----------
function titular(titulo, sub, { y = 250, oscuro = false } = {}) {
  return placa(40, y - 30, 960, 380, (g, w0) => {
    const w = w0 - 60;
    g.font = '700 96px "Barlow Condensed"';
    const l = partir(g, titulo, w).slice(0, 2);
    g.font = '600 40px "Public Sans"';
    const ls = sub ? partir(g, sub, w).slice(0, 2) : [];
    const alto = 40 + l.length * 100 + (ls.length ? 24 + ls.length * 50 : 0);
    g.fillStyle = oscuro ? "rgba(24,36,29,.55)" : "rgba(238,241,234,.82)"; redondo(g, 0, 0, w0, alto, 30); g.fill();
    g.translate(30, 26);
    g.font = '700 96px "Barlow Condensed"';
    g.fillStyle = oscuro ? "#ffffff" : hex(C.tinta);
    g.textBaseline = "top";
    l.forEach((x, i) => g.fillText(x, 0, i * 100));
    if (sub) {
      g.font = '600 40px "Public Sans"';
      g.fillStyle = oscuro ? hex(C.paja2) : hex(C.pino);
      partir(g, sub, w).slice(0, 2).forEach((x, i) => g.fillText(x, 0, l.length * 100 + 18 + i * 50));
    }
  });
}
function marca(oscuro = false) {
  return placa(70, 150, 600, 70, g => {
    g.fillStyle = oscuro ? "#ffffff" : hex(C.pino);
    g.font = '700 46px "Barlow Condensed"'; g.textBaseline = "middle";
    g.fillText("LONJAS CyL", 0, 35);
  });
}
const fundido = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.MeshBasicMaterial({ color: 0xe4ebe0, transparent: true, opacity: 0, depthTest: false }));
fundido.position.set(W / 2, H / 2, 5);
hud.add(fundido);

// ---------- piezas 3D ----------
const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.05, ...extra });
function sombra(o) { o.traverse(m => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } }); return o; }
function pieza(forma, color, alto) {
  const g = new THREE.Group();
  if (forma === "silo") {
    const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 1, 40), mat(color));
    const techo = new THREE.Mesh(new THREE.ConeGeometry(0.62, 0.5, 40), mat(0x9aa59c, { metalness: 0.5, roughness: 0.35 }));
    for (let i = 1; i < 6; i++) {
      const aro = new THREE.Mesh(new THREE.TorusGeometry(0.56, 0.018, 8, 40), mat(0x6f7a72, { metalness: 0.6 }));
      aro.rotation.x = Math.PI / 2; aro.userData.f = i / 6; g.add(aro);
    }
    g.add(cuerpo, techo); g.userData = { cuerpo, techo, tipo: forma };
  } else if (forma === "tarro") {
    const vidrio = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 1, 40, 1, true),
      new THREE.MeshPhysicalMaterial({ color: C.cristal, transmission: 0.6, transparent: true, opacity: 0.35, roughness: 0.1 }));
    const relleno = new THREE.Mesh(new THREE.CylinderGeometry(0.54, 0.54, 1, 40), mat(color, { roughness: 0.9 }));
    const tapa = new THREE.Mesh(new THREE.CylinderGeometry(0.64, 0.64, 0.14, 40), mat(C.paja, { metalness: 0.4 }));
    g.add(vidrio, relleno, tapa); g.userData = { cuerpo: relleno, vidrio, techo: tapa, tipo: forma };
  } else if (forma === "saco") {
    const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.62, 1, 8), mat(color, { roughness: 1, flatShading: true }));
    const nudo = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 8), mat(color, { roughness: 1 }));
    g.add(cuerpo, nudo); g.userData = { cuerpo, techo: nudo, tipo: forma };
  } else if (forma === "gota") {
    const cuerpo = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 1, 32), mat(color, { roughness: 0.25, metalness: 0.2 }));
    const techo = new THREE.Mesh(new THREE.SphereGeometry(0.5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), mat(color, { roughness: 0.25, metalness: 0.2 }));
    g.add(cuerpo, techo); g.userData = { cuerpo, techo, tipo: forma };
  } else {                                                   // «columna»: podio de caja
    const cuerpo = new THREE.Mesh(new THREE.BoxGeometry(1.05, 1, 1.05), mat(color));
    const techo = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.12, 1.15), mat(C.hoja));
    g.add(cuerpo, techo); g.userData = { cuerpo, techo, tipo: forma };
  }
  fijarAlto(g, alto);
  return sombra(g);
}
function fijarAlto(g, h) {
  const { cuerpo, techo, vidrio, tipo } = g.userData;
  h = Math.max(0.02, h);
  cuerpo.scale.y = h; cuerpo.position.y = h / 2;
  if (vidrio) { const v = g.userData.altoMax || h; vidrio.scale.y = v; vidrio.position.y = v / 2; techo.position.y = v + 0.07; }
  else techo.position.y = h + (tipo === "silo" ? 0.25 : tipo === "saco" ? 0.12 : tipo === "gota" ? 0 : 0.06);
  g.children.filter(c => c.userData.f).forEach(a => { a.position.y = a.userData.f * h; a.visible = h > 0.3; });
}
function corona() {
  const g = new THREE.Group();
  const aro = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.38, 0.22, 24, 1, true), mat(C.paja2, { metalness: 0.8, roughness: 0.25, side: THREE.DoubleSide }));
  g.add(aro);
  for (let i = 0; i < 5; i++) {
    const p = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.26, 8), mat(C.paja2, { metalness: 0.8, roughness: 0.25 }));
    const a = i / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.4, 0.22, Math.sin(a) * 0.4); g.add(p);
  }
  return sombra(g);
}
function flecha(dir) {
  const color = dir > 0 ? C.sube : dir < 0 ? C.baja : C.gris;
  const g = new THREE.Group();
  if (dir === 0) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.22, 0.22), mat(color)); g.add(b);
  } else {
    const t = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.6, 16), mat(color));
    const p = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.42, 20), mat(color));
    t.position.y = -0.15; p.position.y = 0.35; g.add(t, p);
    if (dir < 0) g.rotation.z = Math.PI;
  }
  return sombra(g);
}
function persona(color) {
  const g = new THREE.Group();
  const cuerpo = new THREE.Mesh(new THREE.CapsuleGeometry(0.32, 0.6, 6, 16), mat(color));
  const cabeza = new THREE.Mesh(new THREE.SphereGeometry(0.26, 24, 16), mat(0xe8c9a6, { roughness: 0.8 }));
  cuerpo.position.y = 0.62; cabeza.position.y = 1.4; g.add(cuerpo, cabeza);
  return sombra(g);
}
function tarjeta3d(titulo, texto, { color = C.hoja, tinta = C.tinta, acento = C.pino, ancho = 3.8 } = {}) {
  const w = 760, h = 520;
  const tex = lienzo(w, h, g => {
    g.fillStyle = hex(color); redondo(g, 0, 0, w, h, 40); g.fill();
    g.fillStyle = hex(acento); redondo(g, 0, 0, w, 22, 11); g.fill(); g.fillRect(0, 11, w, 11);
    g.fillStyle = hex(acento); g.font = '700 96px "Barlow Condensed"'; g.textBaseline = "top";
    const tl = partir(g, titulo, w - 80).slice(0, 2); tl.forEach((l, i) => g.fillText(l, 40, 50 + i * 98));
    g.fillStyle = hex(tinta); g.font = '600 50px "Public Sans"';
    partir(g, texto, w - 80).slice(0, 5).forEach((l, i) => g.fillText(l, 40, 80 + tl.length * 98 + i * 64));
  });
  const m = new THREE.Mesh(new THREE.BoxGeometry(ancho, ancho * h / w, 0.06),
    [mat(color), mat(color), mat(color), mat(color), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7 }), mat(color)]);
  return sombra(m);
}

// ---------- tipos de escena ----------
// Cada uno devuelve { grupo, placas, anim(p, t), cam(p) -> [x,y,z, mx,my,mz] }
const TIPOS = {
  portada(e) {
    const grupo = new THREE.Group();
    const alturas = [1.2, 2.1, 1.6, 2.8, 1.9, 2.4, 1.4];
    alturas.forEach((h, i) => {
      const p = pieza(i % 2 ? "silo" : "columna", i % 3 === 0 ? C.paja : i % 2 ? C.pino2 : C.pino, h);
      const a = i / alturas.length * Math.PI * 2;
      p.position.set(Math.cos(a) * 3, 0, Math.sin(a) * 3); p.userData.h = h; grupo.add(p);
    });
    const placas = [marca(), titular(e.titulo, e.sub, { y: 1180 })];
    return { grupo, placas,
      anim(p) { grupo.children.forEach((c, i) => fijarAlto(c, c.userData.h * ease(tramo(p, i * 0.05, 0.4 + i * 0.05)))); grupo.rotation.y = p * 0.8; },
      cam: p => [0, 6.2 - p, 14 - p * 1.5, 0, 2.6, 0] };
  },

  barras(e) {
    const grupo = new THREE.Group(), items = e.items || [], n = items.length;
    const vals = items.map(i => i.valor), vmin = Math.min(...vals), vmax = Math.max(...vals);
    const altoDe = v => vmax === vmin ? 2.8 : 1.2 + 3.2 * (v - vmin) / (vmax - vmin);
    const paso = n > 6 ? 1.45 : 1.75, x0 = -(n - 1) * paso / 2;
    const color = C[e.color] ?? C.pino;
    const piezas = items.map((it, i) => {
      const g = pieza(e.forma || "columna", it.destacar ? (e.forma === "tarro" ? color : C.paja) : color, 0.02);
      g.userData.h = altoDe(it.valor); g.userData.altoMax = 5.4;
      if (e.forma === "tarro") g.userData.altoMax = 5.4;
      const z = n > 5 ? -Math.abs(i - (n - 1) / 2) * 0.35 : 0;
      g.position.set(x0 + i * paso, 0, z);
      const valor = cartel(it.texto, { tam: 70, fondo: it.destacar ? C.paja : C.pino, color: C.hoja, alto: 0.95 });
      const nombre = cartel(it.etiqueta, { tam: 54, color: C.tinta, alto: 0.62, ancho: 360, fuente: "Public Sans", peso: 700, fondo: C.hoja });
      nombre.position.set(g.position.x, 0.5, g.position.z + 1.25);
      valor.material.opacity = 0; nombre.material.opacity = 0;
      grupo.add(g, valor, nombre);
      let c = null;
      if (it.destacar) { c = corona(); c.visible = false; grupo.add(c); }
      return { g, valor, nombre, c, it };
    });
    const placas = [marca(), titular(e.titulo, e.sub)];
    if (e.nota) placas.push(placa(70, 1560, 900, 90, g => { g.font = '600 38px "Public Sans"'; g.fillStyle = hex(C.pino); g.textBaseline = "middle"; g.fillText(e.nota, 0, 45); }));
    const ancho = Math.max(4, (n - 1) * paso + 2);
    return { grupo, placas,
      anim(p, t) {
        piezas.forEach(({ g, valor, nombre, c }, i) => {
          const k = ease(tramo(p, 0.05 + i * 0.04, 0.45 + i * 0.04));
          fijarAlto(g, g.userData.h * k);
          valor.position.set(g.position.x, g.userData.h * k + (g.userData.tipo === "silo" ? 1.45 : 1.15) + (c ? 0.75 : 0), g.position.z);
          valor.material.opacity = tramo(p, 0.4 + i * 0.04, 0.55 + i * 0.04);
          nombre.material.opacity = tramo(p, 0.15, 0.35);
          if (c) { c.visible = k > 0.98; c.position.set(g.position.x, g.userData.h + (g.userData.tipo === "silo" ? 0.62 : 0.3), g.position.z); c.rotation.y = t * 1.5; }
        });
      },
      cam: p => { const a = -0.22 + p * 0.4, r = lejos(ancho / 2 + 0.7) * (1.1 - p * 0.06); return [Math.sin(a) * r, 1.6 + r * 0.12, Math.cos(a) * r, 0, 3.6, 0]; } };
  },

  flechas(e) {
    const grupo = new THREE.Group(), items = (e.items || []).slice(0, 8), n = items.length;
    const cols = n > 4 ? 2 : 1, filas = Math.ceil(n / cols);
    const piezas = items.map((it, i) => {
      const col = cols === 2 ? (i % 2) : 0, fila = cols === 2 ? Math.floor(i / 2) : i;
      const x = cols === 2 ? (col ? 1.7 : -1.7) : 0, y = 0.9 + (filas - 1 - fila) * 1.55;
      const base = new THREE.Mesh(new THREE.BoxGeometry(cols === 2 ? 3.2 : 4.6, 1.25, 0.25), mat(C.hoja));
      base.position.set(x, y, 0); sombra(base);
      const f = flecha(it.dir); f.position.set(x - (cols === 2 ? 1.05 : 1.7), y, 0.45); f.scale.setScalar(0.85);
      const txt = cartel(it.etiqueta, { tam: 64, alto: 0.5, ancho: 520 });
      txt.position.set(x + 0.35, y + 0.18, 0.2);
      const det = cartel(it.texto || "", { tam: 52, alto: 0.36, color: it.dir > 0 ? C.sube : it.dir < 0 ? C.baja : C.gris, fuente: "Public Sans", ancho: 520 });
      det.position.set(x + 0.35, y - 0.28, 0.2);
      grupo.add(base, f, txt, det);
      return { base, f, txt, det, y };
    });
    const placas = [marca(), titular(e.titulo, e.sub)];
    return { grupo, placas,
      anim(p, t) {
        piezas.forEach(({ base, f, txt, det, y }, i) => {
          const k = ease(tramo(p, 0.05 + i * 0.06, 0.3 + i * 0.06));
          [base, f].forEach(o => { o.scale.setScalar(o === f ? 0.85 * k : k); });
          base.position.y = y - (1 - k) * 0.6;
          txt.material.opacity = det.material.opacity = k;
          f.rotation.y = t * 1.2;
        });
      },
      cam: p => { const r = lejos(cols === 2 ? 3.7 : 2.7); const a = -0.18 + p * 0.3; return [Math.sin(a) * r, 1.4 + filas * 0.7, Math.cos(a) * r, 0, 1.1 + filas * 0.78, 0]; } };
  },

  curva(e) {
    const grupo = new THREE.Group(), series = e.series || [];
    const todos = series.flatMap(s => s.valores), vmin = Math.min(...todos), vmax = Math.max(...todos);
    const tubos = series.map((s, k) => {
      const n = s.valores.length;
      const pts = s.valores.map((v, i) => new THREE.Vector3(-4 + 8 * i / Math.max(1, n - 1), 0.8 + 4 * (vmax === vmin ? 0.5 : (v - vmin) / (vmax - vmin)), -k * 1.2));
      const curva = new THREE.CatmullRomCurve3(pts);
      const geo = new THREE.TubeGeometry(curva, 120, 0.16, 12, false);
      const m = sombra(new THREE.Mesh(geo, mat(C[s.color] ?? C.pino, { roughness: 0.35 })));
      grupo.add(m);
      const ini = cartel(s.inicio, { tam: 52, alto: 0.75, fondo: C.hoja, color: C.tinta, fuente: "Public Sans" });
      const fin = cartel(s.fin, { tam: 60, alto: 0.95, fondo: C[s.color] ?? C.pino, color: C.hoja });
      const nom = cartel(s.nombre, { tam: 60, alto: 0.85, color: C[s.color] ?? C.pino });
      ini.position.copy(pts[0]).add(new THREE.Vector3(0, 0.9, 0)); fin.position.copy(pts[n - 1]).add(new THREE.Vector3(-0.4, 1.0, 0));
      nom.position.copy(pts[0]).add(new THREE.Vector3(0.9, 1.9, 0));
      [ini, fin, nom].forEach(c => { c.material.opacity = 0; grupo.add(c); });
      return { geo, ini, fin, nom, total: geo.index.count };
    });
    const placas = [marca(), titular(e.titulo, e.sub)];
    return { grupo, placas,
      anim(p) {
        tubos.forEach(({ geo, ini, fin, nom, total }) => {
          const k = ease(tramo(p, 0.05, 0.6));
          geo.setDrawRange(0, Math.floor(total * k / 6) * 6);
          ini.material.opacity = nom.material.opacity = tramo(p, 0.05, 0.2);
          fin.material.opacity = tramo(p, 0.58, 0.7);
        });
      },
      cam: p => { const r = lejos(5.4); return [-1.5 + p * 3, 2.6, r - p * 0.8, 0, 3.6, -0.5]; } };
  },

  tarjetas(e) {
    const grupo = new THREE.Group(), items = (e.items || []).slice(0, 5), n = Math.max(1, items.length);
    const piezas = items.map((it, i) => { const m = tarjeta3d(it.titulo, it.texto, { acento: i % 2 ? C.paja : C.pino }); grupo.add(m); return m; });
    const placas = [marca(), titular(e.titulo, e.sub)];
    return { grupo, placas,
      anim(p, t) {
        piezas.forEach((m, i) => {
          const q = p * n - i;                                            // 0..1 mientras le toca a esta tarjeta
          m.visible = q > -0.05 && q < 1.05;
          const entra = ease(tramo(q, 0, 0.25)), sale = tramo(q, 0.85, 1);
          m.position.set(-sale * 5, 3 + Math.sin(t * 1.3) * 0.06, 0);
          m.rotation.set(0.05, (1 - entra) * -Math.PI / 2 + Math.sin(t * 0.8) * 0.06 - sale * 0.6, 0);
        });
      },
      cam: () => [0, 3.1, lejos(2.2), 0, 3.25, 0] };
  },

  movil(e) {
    const grupo = new THREE.Group(), items = (e.items || []).slice(0, 5);
    const cuerpo = sombra(new THREE.Mesh(new THREE.BoxGeometry(2.6, 5.2, 0.28), mat(0x1c1f1d, { roughness: 0.3, metalness: 0.4 })));
    cuerpo.position.y = 3;
    const pantallas = items.map((it, i) => lienzo(540, 1080, g => {
      g.fillStyle = "#f4f6f1"; g.fillRect(0, 0, 540, 1080);
      g.fillStyle = hex(C.pino); g.fillRect(0, 0, 540, 140);
      g.fillStyle = "#fff"; g.font = '700 54px "Barlow Condensed"'; g.textBaseline = "middle"; g.fillText("Lonjas CyL", 32, 84);
      g.fillStyle = "#fff"; redondo(g, 28, 180, 484, 820, 30); g.fill();
      g.fillStyle = hex(C.paja); g.font = '700 40px "Public Sans"'; g.textBaseline = "top"; g.fillText(`${i + 1}/${items.length}`, 56, 210);
      g.fillStyle = hex(C.pino); g.font = '700 88px "Barlow Condensed"';
      const tl = partir(g, it.titulo, 430).slice(0, 3); tl.forEach((l, j) => g.fillText(l, 56, 270 + j * 90));
      g.fillStyle = hex(C.tinta); g.font = '600 48px "Public Sans"';
      partir(g, it.texto, 430).slice(0, 9).forEach((l, j) => g.fillText(l, 56, 300 + tl.length * 90 + j * 62));
    }));
    const pantalla = new THREE.Mesh(new THREE.PlaneGeometry(2.36, 4.72), new THREE.MeshBasicMaterial({ map: pantallas[0] }));
    pantalla.position.set(0, 3, 0.145);
    grupo.add(cuerpo, pantalla);
    const placas = [marca(), titular(e.titulo, e.sub)];
    return { grupo, placas,
      anim(p, t) {
        const i = Math.min(pantallas.length - 1, Math.floor(p * pantallas.length));
        if (pantalla.material.map !== pantallas[i]) { pantalla.material.map = pantallas[i]; pantalla.material.needsUpdate = true; }
        grupo.rotation.y = Math.sin(t * 0.7) * 0.22; grupo.position.y = Math.sin(t * 1.1) * 0.08;
      },
      cam: p => [0.5, 2.6, 8.8 - p * 0.5, 0, 3.4, 0] };
  },

  mesa(e) {
    const grupo = new THREE.Group();
    const tablero = sombra(new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, 0.16, 64), mat(0x8a5a32, { roughness: 0.7 })));
    const pata = sombra(new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.5, 1.1, 24), mat(0x6b4426)));
    tablero.position.y = 1.15; pata.position.y = 0.55; grupo.add(tablero, pata);
    const gente = [];
    for (let i = 0; i < 6; i++) {
      const a = (i < 3 ? Math.PI * 0.62 + i * 0.38 : -Math.PI * 0.38 + (i - 3) * 0.38);
      const pz = persona(i < 3 ? C.paja : C.pino); pz.position.set(Math.cos(a) * 3.3, 0, Math.sin(a) * 3.3); pz.lookAt(0, 0, 0);
      grupo.add(pz); gente.push(pz);
    }
    const comp = cartel(e.izquierda || "Compradores", { tam: 60, fondo: C.paja, color: C.hoja, alto: 0.8 });
    const vend = cartel(e.derecha || "Vendedores", { tam: 60, fondo: C.pino, color: C.hoja, alto: 0.8 });
    comp.position.set(-1.55, 2.55, 2.6); vend.position.set(1.55, 2.55, 2.6);
    const pizarra = sombra(new THREE.Mesh(new THREE.BoxGeometry(3.4, 2.1, 0.08), [mat(0x2c3a33), mat(0x2c3a33), mat(0x2c3a33), mat(0x2c3a33),
      new THREE.MeshStandardMaterial({ map: lienzo(640, 400, g => { g.fillStyle = "#2c3a33"; g.fillRect(0, 0, 640, 400); g.strokeStyle = "#8a5a32"; g.lineWidth = 18; g.strokeRect(9, 9, 622, 382);
        g.fillStyle = "#f1efe6"; g.font = '700 92px "Barlow Condensed"'; g.textAlign = "center"; g.textBaseline = "middle";
        partir(g, e.pizarra || "Precio de referencia", 580).slice(0, 3).forEach((l, i, a) => g.fillText(l, 320, 200 + (i - (a.length - 1) / 2) * 96)); }) }), mat(0x2c3a33)]));
    grupo.add(comp, vend, pizarra);
    const placas = [marca(), titular(e.titulo, e.sub)];
    return { grupo, placas,
      anim(p, t) {
        comp.material.opacity = vend.material.opacity = tramo(p, 0.1, 0.25);
        const k = ease(tramo(p, 0.35, 0.65));
        pizarra.position.set(0, 1.25 + k * 1.9, 0); pizarra.scale.setScalar(0.001 + k); pizarra.rotation.y = (1 - k) * Math.PI * 1.5;
        gente.forEach((g, i) => { g.position.y = Math.max(0, Math.sin(t * 3 + i)) * 0.06; });
      },
      cam: p => { const a = 0.2 - p * 0.4, r = lejos(3.9); return [Math.sin(a) * r, 5.2 - p * 1.2, Math.cos(a) * r, 0, 2.4, 0]; } };
  },

  cierre(e) {
    const grupo = new THREE.Group();
    const alturas = [1.4, 2.2, 1.8, 2.9, 2.0];
    alturas.forEach((h, i) => { const p = pieza("columna", i === 3 ? C.paja : C.pino, h); p.position.set(-2.4 + i * 1.2, 0, 0); p.userData.h = h; grupo.add(p); });
    const placas = [placa(40, 1100, 1000, 560, (g, w0) => {
      g.fillStyle = "rgba(238,241,234,.9)"; redondo(g, 0, 0, w0, 500, 30); g.fill(); g.translate(30, 30); const w = w0 - 60;
      g.fillStyle = hex(C.pino); g.font = '700 120px "Barlow Condensed"'; g.textBaseline = "top"; g.fillText("Lonjas CyL", 0, 0);
      g.fillStyle = hex(C.tinta); g.font = '600 44px "Public Sans"';
      partir(g, e.texto || "Todos los precios de las lonjas de Castilla y León, gratis.", w).slice(0, 3).forEach((l, i) => g.fillText(l, 0, 150 + i * 56));
      g.fillStyle = hex(C.paja); g.font = '700 44px "Public Sans"'; g.fillText(e.web || "lonjas-cyl-khaki.vercel.app", 0, 340);
      g.fillStyle = hex(C.gris); g.font = '600 30px "Public Sans"'; g.fillText("Precios orientativos · fuente: cada lonja", 0, 420);
    })];
    return { grupo, placas,
      anim(p) { grupo.children.forEach((c, i) => fijarAlto(c, c.userData.h * ease(tramo(p, i * 0.06, 0.4 + i * 0.06)))); },
      cam: p => [0.4, 1.2, lejos(3.4) - p * 0.6, 0, 0.2, 0] };
  },
};

// ---------- línea de tiempo ----------
let partes = [], total = 0;
window.montar = async spec => {
  await document.fonts.load('700 40px "Barlow Condensed"'); await document.fonts.load('600 40px "Barlow Condensed"');
  await document.fonts.load('600 40px "Public Sans"'); await document.fonts.load('700 40px "Public Sans"');
  partes = []; total = 0;
  for (const e of spec.escenas) {
    const hacer = TIPOS[e.tipo];
    if (!hacer) throw new Error("Tipo de escena desconocido: " + e.tipo);
    const p = hacer(e);
    p.grupo.visible = false; escena.add(p.grupo);
    partes.push({ ...p, ini: total, dur: e.dur });
    total += e.dur;
  }
  return total;
};
window.cuadro = t => {
  const i = Math.max(0, partes.findIndex(p => t < p.ini + p.dur));
  const actual = partes[i === -1 ? partes.length - 1 : i];
  partes.forEach(p => { const v = p === actual; p.grupo.visible = v; p.placas.forEach(m => { m.visible = v; }); });
  const local = Math.min(actual.dur, t - actual.ini), p = local / actual.dur;
  actual.anim(p, t);
  const [x, y, z, mx, my, mz] = actual.cam(p);
  camara.position.set(x, y, z); camara.lookAt(mx, my, mz);
  const entra = actual.ini > 0 ? 1 - Math.min(1, local / TRANS) : 0;
  const sale = actual.ini + actual.dur < total ? Math.max(0, (local - (actual.dur - TRANS)) / TRANS) : 0;
  fundido.material.opacity = Math.max(entra, sale);
  actual.placas.forEach(m => { m.material.opacity = Math.min(1, local / 0.5); });
  renderer.clear();
  renderer.render(escena, camara);
  renderer.clearDepth();
  renderer.render(hud, hudCam);
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
window.listo = true;
