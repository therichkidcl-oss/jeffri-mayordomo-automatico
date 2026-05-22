// Escena Canvas 2D de la Batcave — version cinematica.

const canvas = document.getElementById('batcave-canvas');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;

const SCALE = 4;
const W = canvas.width;
const H = canvas.height;
const JEFFRI_FRAME_W = 16;
const JEFFRI_FRAME_H = 32;

const assets = {
  floor: null,
  desk: null,
  chair: null,
  bookshelf: null,
  doubleBookshelf: null,
  pcFrames: [],
  jeffri: null,
  largePlant: null,
  plant: null,
  largePainting: null,
  clock: null,
  sofa: null,
  whiteboard: null,
};

let bobPhase = 0;
let pcFrameIdx = 0;
let pcFrameCounter = 0;
let speechText = 'Sus ordenes, senor.';
let speechExpire = Infinity;

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

async function loadAssets() {
  const results = await Promise.all([
    loadImage('/static/assets/floors/floor_0.png'),
    loadImage('/static/assets/furniture/DESK/DESK_FRONT.png'),
    loadImage('/static/assets/furniture/WOODEN_CHAIR/WOODEN_CHAIR_FRONT.png'),
    loadImage('/static/assets/furniture/BOOKSHELF/BOOKSHELF.png'),
    loadImage('/static/assets/furniture/DOUBLE_BOOKSHELF/DOUBLE_BOOKSHELF.png'),
    loadImage('/static/assets/furniture/PC/PC_FRONT_ON_1.png'),
    loadImage('/static/assets/furniture/PC/PC_FRONT_ON_2.png'),
    loadImage('/static/assets/furniture/PC/PC_FRONT_ON_3.png'),
    loadImage('/static/assets/characters/char_0.png'),
    loadImage('/static/assets/furniture/LARGE_PLANT/LARGE_PLANT.png'),
    loadImage('/static/assets/furniture/PLANT/PLANT.png'),
    loadImage('/static/assets/furniture/LARGE_PAINTING/LARGE_PAINTING.png'),
    loadImage('/static/assets/furniture/CLOCK/CLOCK.png'),
    loadImage('/static/assets/furniture/SOFA/SOFA_FRONT.png'),
    loadImage('/static/assets/furniture/WHITEBOARD/WHITEBOARD.png'),
  ]);
  assets.floor = results[0];
  assets.desk = results[1];
  assets.chair = results[2];
  assets.bookshelf = results[3];
  assets.doubleBookshelf = results[4];
  assets.pcFrames = [results[5], results[6], results[7]].filter(Boolean);
  assets.jeffri = results[8];
  assets.largePlant = results[9];
  assets.plant = results[10];
  assets.largePainting = results[11];
  assets.clock = results[12];
  assets.sofa = results[13];
  assets.whiteboard = results[14];
}

function drawBackground() {
  // Pared oscura con gradiente
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, '#05070d');
  grad.addColorStop(0.4, '#0a0e1a');
  grad.addColorStop(1, '#101725');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Estalactitas mas dramaticas
  ctx.fillStyle = '#1a1f2e';
  const stals = 10;
  for (let i = 0; i < stals; i++) {
    const x = (W / stals) * i + 10;
    const h = 50 + Math.sin(i * 1.3) * 30;
    const w = 40;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + w, 0);
    ctx.lineTo(x + w / 2, h);
    ctx.closePath();
    ctx.fill();
  }
}

function drawCurtains() {
  // Cortinas rojo oscuro a los lados
  const curtainW = 80;
  const drawCurtain = (xStart) => {
    const grad = ctx.createLinearGradient(xStart, 0, xStart + curtainW, 0);
    grad.addColorStop(0, '#1a0407');
    grad.addColorStop(0.5, '#3d0a10');
    grad.addColorStop(1, '#1a0407');
    ctx.fillStyle = grad;
    ctx.fillRect(xStart, 0, curtainW, H);
    // Pliegues (lineas verticales)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    for (let i = 0; i < 6; i++) {
      ctx.fillRect(xStart + (curtainW / 6) * i + 5, 0, 2, H);
    }
  };
  drawCurtain(0);
  drawCurtain(W - curtainW);
}

function drawBatmobile() {
  // Silueta del Batmovil al fondo (dibujado con shapes)
  const cx = W / 2;
  const cy = H - 240;
  ctx.fillStyle = '#02030a';
  // Carroceria
  ctx.fillRect(cx - 140, cy, 280, 40);
  // Capot inclinado
  ctx.beginPath();
  ctx.moveTo(cx - 140, cy);
  ctx.lineTo(cx - 100, cy - 20);
  ctx.lineTo(cx + 100, cy - 20);
  ctx.lineTo(cx + 140, cy);
  ctx.closePath();
  ctx.fill();
  // Cabina
  ctx.fillRect(cx - 60, cy - 35, 120, 18);
  // Ruedas
  ctx.beginPath();
  ctx.arc(cx - 100, cy + 40, 22, 0, Math.PI * 2);
  ctx.arc(cx + 100, cy + 40, 22, 0, Math.PI * 2);
  ctx.fill();
  // Detalles rojos (luz trasera)
  ctx.fillStyle = '#7a0a0a';
  ctx.fillRect(cx - 138, cy + 5, 6, 10);
  ctx.fillRect(cx + 132, cy + 5, 6, 10);
  // Brillo cabina
  ctx.fillStyle = 'rgba(40, 80, 150, 0.2)';
  ctx.fillRect(cx - 58, cy - 33, 116, 14);
}

function drawBatSymbol(cx, cy, scale = 1) {
  // Logo del murcielago hecho con shapes (Batman classic)
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);
  ctx.fillStyle = '#fbbf24';
  ctx.beginPath();
  // Cabeza y orejas (centro)
  ctx.moveTo(0, -8);
  ctx.lineTo(-3, -18);
  ctx.lineTo(-5, -14);
  ctx.lineTo(-7, -6);
  // Ala izquierda
  ctx.lineTo(-22, -10);
  ctx.lineTo(-30, -2);
  ctx.lineTo(-26, 0);
  ctx.lineTo(-20, -2);
  ctx.lineTo(-14, 2);
  ctx.lineTo(-22, 6);
  ctx.lineTo(-10, 4);
  ctx.lineTo(-8, 8);
  // Cola
  ctx.lineTo(-4, 4);
  ctx.lineTo(0, 8);
  ctx.lineTo(4, 4);
  ctx.lineTo(8, 8);
  // Ala derecha (espejada)
  ctx.lineTo(10, 4);
  ctx.lineTo(22, 6);
  ctx.lineTo(14, 2);
  ctx.lineTo(20, -2);
  ctx.lineTo(26, 0);
  ctx.lineTo(30, -2);
  ctx.lineTo(22, -10);
  ctx.lineTo(7, -6);
  ctx.lineTo(5, -14);
  ctx.lineTo(3, -18);
  ctx.closePath();
  ctx.fill();
  // Oval amarillo de fondo (clasico)
  ctx.restore();
}

function drawBatSymbolWithBg(cx, cy, scale = 1) {
  ctx.save();
  // Oval amarillo
  ctx.translate(cx, cy);
  ctx.fillStyle = '#fbbf24';
  ctx.beginPath();
  ctx.ellipse(0, 0, 50 * scale, 28 * scale, 0, 0, Math.PI * 2);
  ctx.fill();
  // Bat negro encima
  ctx.fillStyle = '#000';
  ctx.scale(scale, scale);
  ctx.beginPath();
  ctx.moveTo(0, -10);
  ctx.lineTo(-3, -16);
  ctx.lineTo(-6, -10);
  ctx.lineTo(-18, -8);
  ctx.lineTo(-28, 0);
  ctx.lineTo(-22, 2);
  ctx.lineTo(-12, 0);
  ctx.lineTo(-16, 6);
  ctx.lineTo(-6, 4);
  ctx.lineTo(-4, 8);
  ctx.lineTo(0, 6);
  ctx.lineTo(4, 8);
  ctx.lineTo(6, 4);
  ctx.lineTo(16, 6);
  ctx.lineTo(12, 0);
  ctx.lineTo(22, 2);
  ctx.lineTo(28, 0);
  ctx.lineTo(18, -8);
  ctx.lineTo(6, -10);
  ctx.lineTo(3, -16);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawBatcomputer() {
  const x = W - 380;
  const y = 70;
  const w = 320;
  const h = 180;
  // Marco del monitor
  ctx.fillStyle = '#0d0f17';
  ctx.fillRect(x - 10, y - 10, w + 20, h + 20);
  ctx.fillStyle = '#1c2335';
  ctx.fillRect(x, y, w, h);
  // Pantalla verde con glow
  const screenGrad = ctx.createRadialGradient(x + w / 2, y + h / 2, 20, x + w / 2, y + h / 2, w);
  screenGrad.addColorStop(0, '#1de9b6');
  screenGrad.addColorStop(0.6, '#0f9e7e');
  screenGrad.addColorStop(1, '#04392c');
  ctx.fillStyle = screenGrad;
  ctx.fillRect(x + 5, y + 5, w - 10, h - 10);
  // Lineas de escaneo
  ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
  for (let i = y + 5; i < y + h - 5; i += 4) {
    ctx.fillRect(x + 5, i, w - 10, 2);
  }
  // Texto de la Batcomputer
  ctx.fillStyle = 'rgba(220, 255, 240, 0.9)';
  ctx.font = '16px Courier New';
  ctx.fillText('▶ JEFFRI v1.0', x + 20, y + 30);
  ctx.fillText('▶ STATUS: ON DUTY', x + 20, y + 52);
  ctx.fillText('▶ AGENT: STANDBY', x + 20, y + 74);
  ctx.fillText('▶ THREATS: 0', x + 20, y + 96);
  ctx.fillText('▶ COFFEE: 73%', x + 20, y + 118);
  ctx.font = '12px Courier New';
  ctx.fillStyle = 'rgba(220, 255, 240, 0.5)';
  ctx.fillText('// Batcave OS - All systems nominal', x + 20, y + 145);

  // Glow alrededor del monitor
  const glow = ctx.createRadialGradient(x + w / 2, y + h / 2, w / 2, x + w / 2, y + h / 2, w);
  glow.addColorStop(0, 'rgba(29, 233, 182, 0.15)');
  glow.addColorStop(1, 'rgba(29, 233, 182, 0)');
  ctx.fillStyle = glow;
  ctx.fillRect(x - 100, y - 100, w + 200, h + 200);
}

function drawBatSign() {
  // Bat-signal proyectado en la pared encima del Batcomputer
  drawBatSymbolWithBg(W - 220, 35, 0.8);
}

function drawFloor() {
  if (!assets.floor) return;
  const tileW = assets.floor.width * SCALE;
  const tileH = assets.floor.height * SCALE;
  for (let y = H - tileH * 2; y < H; y += tileH) {
    for (let x = 0; x < W; x += tileW) {
      ctx.drawImage(assets.floor, x, y, tileW, tileH);
    }
  }
  // Oscurecer piso
  ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
  ctx.fillRect(0, H - tileH * 2, W, tileH * 2);
}

function drawFurniture() {
  const baseY = H - 160;

  // Estanteria doble a la izquierda
  if (assets.doubleBookshelf) {
    const w = assets.doubleBookshelf.width * SCALE;
    const h = assets.doubleBookshelf.height * SCALE;
    ctx.drawImage(assets.doubleBookshelf, 120, baseY - h + 30, w, h);
  } else if (assets.bookshelf) {
    const w = assets.bookshelf.width * SCALE;
    const h = assets.bookshelf.height * SCALE;
    ctx.drawImage(assets.bookshelf, 120, baseY - h + 30, w, h);
    ctx.drawImage(assets.bookshelf, 120, baseY - h * 2 + 30, w, h);
  }

  // Planta grande a la izquierda
  if (assets.largePlant) {
    const w = assets.largePlant.width * SCALE;
    const h = assets.largePlant.height * SCALE;
    ctx.drawImage(assets.largePlant, 250, baseY - h + 50, w, h);
  }

  // Sofa al fondo izquierdo
  if (assets.sofa) {
    const w = assets.sofa.width * SCALE;
    const h = assets.sofa.height * SCALE;
    ctx.drawImage(assets.sofa, 350, baseY - h + 40, w, h);
  }

  // Reloj en pared
  if (assets.clock) {
    const w = assets.clock.width * SCALE;
    const h = assets.clock.height * SCALE;
    ctx.drawImage(assets.clock, 220, 60, w, h);
  }

  // Cuadro grande en pared izquierda
  if (assets.largePainting) {
    const w = assets.largePainting.width * SCALE;
    const h = assets.largePainting.height * SCALE;
    ctx.drawImage(assets.largePainting, 90, 80, w, h);
  }

  // PC encima del escritorio (animado)
  if (assets.pcFrames.length > 0) {
    const pc = assets.pcFrames[pcFrameIdx % assets.pcFrames.length];
    const w = pc.width * SCALE;
    const h = pc.height * SCALE;
    ctx.drawImage(pc, W / 2 - w / 2 - 50, baseY - 80, w, h);
  }

  // Escritorio principal
  if (assets.desk) {
    const w = assets.desk.width * SCALE;
    const h = assets.desk.height * SCALE;
    ctx.drawImage(assets.desk, W / 2 - w / 2, baseY, w, h);
  }

  // Silla
  if (assets.chair) {
    const w = assets.chair.width * SCALE;
    const h = assets.chair.height * SCALE;
    ctx.drawImage(assets.chair, W / 2 - w / 2 + 130, baseY + 30, w, h);
  }

  // Planta pequena a la derecha
  if (assets.plant) {
    const w = assets.plant.width * SCALE;
    const h = assets.plant.height * SCALE;
    ctx.drawImage(assets.plant, W - 200, baseY - h + 40, w, h);
  }

  // Whiteboard al lado derecho
  if (assets.whiteboard) {
    const w = assets.whiteboard.width * SCALE;
    const h = assets.whiteboard.height * SCALE;
    ctx.drawImage(assets.whiteboard, W - 320, 280, w, h);
  }
}

function drawJeffriAlfred() {
  if (!assets.jeffri) return;
  const sw = JEFFRI_FRAME_W;
  const sh = JEFFRI_FRAME_H;
  const w = sw * SCALE;
  const h = sh * SCALE;
  const x = W / 2 - w / 2;
  const y = H - 160 - h + 40 + Math.sin(bobPhase) * 2;

  // Sprite base
  ctx.drawImage(assets.jeffri, 0, 0, sw, sh, x, y, w, h);

  // OVERLAY: pajarita blanca + bigote (Alfred custom)
  // Detectar el cuello aprox a 1/3 del top del sprite
  const neckY = y + h * 0.35;
  // Pajarita (bowtie blanca)
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.moveTo(x + w / 2 - 8, neckY - 4);
  ctx.lineTo(x + w / 2 + 8, neckY + 4);
  ctx.lineTo(x + w / 2 + 8, neckY - 4);
  ctx.lineTo(x + w / 2 - 8, neckY + 4);
  ctx.closePath();
  ctx.fill();
  // Nudo central
  ctx.fillStyle = '#cccccc';
  ctx.fillRect(x + w / 2 - 2, neckY - 4, 4, 8);

  // Bigote (debajo de los ojos del sprite)
  const moustacheY = y + h * 0.25;
  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(x + w / 2 - 7, moustacheY, 14, 2);

  // Speech bubble
  if (speechText && Date.now() < speechExpire) {
    const txt = speechText.slice(0, 50);
    ctx.font = 'bold 16px Courier New';
    const tw = ctx.measureText(txt).width;
    const bx = x + w / 2 - tw / 2 - 12;
    const by = y - 40;
    ctx.fillStyle = '#0a0e1a';
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 2;
    ctx.fillRect(bx, by, tw + 24, 28);
    ctx.strokeRect(bx, by, tw + 24, 28);
    // Triangulo apuntando a Jeffri
    ctx.beginPath();
    ctx.moveTo(x + w / 2 - 6, by + 28);
    ctx.lineTo(x + w / 2 + 6, by + 28);
    ctx.lineTo(x + w / 2, by + 38);
    ctx.closePath();
    ctx.fillStyle = '#0a0e1a';
    ctx.fill();
    ctx.strokeStyle = '#fbbf24';
    ctx.stroke();
    ctx.fillStyle = '#fbbf24';
    ctx.fillText(txt, bx + 12, by + 19);
  }
}

function drawVignette() {
  // Vignette cinematico
  const grad = ctx.createRadialGradient(W / 2, H / 2, W / 3, W / 2, H / 2, W);
  grad.addColorStop(0, 'rgba(0, 0, 0, 0)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0.7)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function render() {
  drawBackground();
  drawBatSign();
  drawBatcomputer();
  drawBatmobile();
  drawCurtains();
  drawFloor();
  drawFurniture();
  drawJeffriAlfred();
  drawVignette();

  bobPhase += 0.04;
  pcFrameCounter++;
  if (pcFrameCounter > 30) {
    pcFrameCounter = 0;
    pcFrameIdx++;
  }
  requestAnimationFrame(render);
}

export function showSpeech(text, durationMs = 5000) {
  speechText = text;
  speechExpire = Date.now() + durationMs;
}

window.batcaveShowSpeech = showSpeech;

loadAssets().then(() => {
  console.log('Batcave assets cargados');
  render();
}).catch(e => {
  console.error('Error cargando assets:', e);
  drawBackground();
});
