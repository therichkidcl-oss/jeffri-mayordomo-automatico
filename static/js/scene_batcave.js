// Escena Canvas 2D de la Batcave. Carga sprites reales.

const canvas = document.getElementById('batcave-canvas');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;

const SCALE = 3;
const W = canvas.width;
const H = canvas.height;

const assets = {
  floor: null,
  desk: null,
  chair: null,
  bookshelf: null,
  pc: null,
  jeffri: null,
};

let bobPhase = 0;
let speechText = 'Sus ordenes, senor.';
let speechExpire = Infinity;

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

async function loadAssets() {
  const [floor, desk, chair, bookshelf, pc, jeffri] = await Promise.all([
    loadImage('/static/assets/floors/floor_3.png'),
    loadImage('/static/assets/furniture/DESK/DESK_FRONT.png').catch(() => null),
    loadImage('/static/assets/furniture/WOODEN_CHAIR/WOODEN_CHAIR_FRONT.png').catch(() => null),
    loadImage('/static/assets/furniture/BOOKSHELF/BOOKSHELF.png').catch(() => null),
    loadImage('/static/assets/furniture/PC/PC_FRONT_ON_1.png').catch(() =>
      loadImage('/static/assets/furniture/PC/PC_FRONT_OFF.png').catch(() => null)),
    loadImage('/static/assets/characters/char_0.png'),
  ]);
  assets.floor = floor;
  assets.desk = desk;
  assets.chair = chair;
  assets.bookshelf = bookshelf;
  assets.pc = pc;
  assets.jeffri = jeffri;
}

function drawFloor() {
  if (!assets.floor) return;
  const tileW = assets.floor.width;
  const tileH = assets.floor.height;
  for (let y = H - tileH * SCALE; y < H; y += tileH * SCALE) {
    for (let x = 0; x < W; x += tileW * SCALE) {
      ctx.drawImage(assets.floor, x, y, tileW * SCALE, tileH * SCALE);
    }
  }
}

function drawBackground() {
  ctx.fillStyle = '#0a0e1a';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#1a1f2e';
  for (let i = 0; i < 6; i++) {
    const x = (W / 6) * i + 20;
    const h = 40 + Math.sin(i * 1.7) * 20;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + 30, 0);
    ctx.lineTo(x + 15, h);
    ctx.closePath();
    ctx.fill();
  }
  ctx.fillStyle = '#1c2335';
  ctx.fillRect(W - 220, 50, 180, 110);
  ctx.fillStyle = '#10b981';
  ctx.fillRect(W - 215, 55, 170, 100);
  ctx.fillStyle = 'rgba(16, 185, 129, 0.3)';
  ctx.font = '10px Courier New';
  ctx.fillText('JEFFRI v1.0', W - 210, 70);
  ctx.fillText('STATUS: ON', W - 210, 85);
  ctx.fillText('AGENT: READY', W - 210, 100);
}

function drawFurniture() {
  const baseY = H - 100;
  if (assets.bookshelf) {
    const w = assets.bookshelf.width * SCALE;
    const h = assets.bookshelf.height * SCALE;
    ctx.drawImage(assets.bookshelf, 30, baseY - h + 50, w, h);
  }
  if (assets.pc) {
    const w = assets.pc.width * SCALE;
    const h = assets.pc.height * SCALE;
    ctx.drawImage(assets.pc, W / 2 - w / 2 - 30, baseY - 50, w, h);
  }
  if (assets.desk) {
    const w = assets.desk.width * SCALE;
    const h = assets.desk.height * SCALE;
    ctx.drawImage(assets.desk, W / 2 - w / 2, baseY, w, h);
  }
  if (assets.chair) {
    const w = assets.chair.width * SCALE;
    const h = assets.chair.height * SCALE;
    ctx.drawImage(assets.chair, W / 2 - w / 2 + 80, baseY + 20, w, h);
  }
}

const JEFFRI_FRAME_W = 16;
const JEFFRI_FRAME_H = 32;

function drawJeffri() {
  if (!assets.jeffri) return;
  const sx = 0;  // column 0
  const sy = 0;  // row 0
  const sw = JEFFRI_FRAME_W;
  const sh = JEFFRI_FRAME_H;
  const w = sw * SCALE;
  const h = sh * SCALE;
  const x = W / 2 - w / 2;
  const y = H - 100 - h + 30 + Math.sin(bobPhase) * 2;
  ctx.drawImage(assets.jeffri, sx, sy, sw, sh, x, y, w, h);

  if (speechText && Date.now() < speechExpire) {
    const txt = speechText.slice(0, 40);
    ctx.font = '14px Courier New';
    const tw = ctx.measureText(txt).width;
    const bx = x + w / 2 - tw / 2 - 8;
    const by = y - 30;
    ctx.fillStyle = '#0a0e1a';
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 2;
    ctx.fillRect(bx, by, tw + 16, 22);
    ctx.strokeRect(bx, by, tw + 16, 22);
    ctx.fillStyle = '#fbbf24';
    ctx.fillText(txt, bx + 8, by + 16);
  }
}

function render() {
  drawBackground();
  drawFloor();
  drawFurniture();
  drawJeffri();
  bobPhase += 0.04;
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
