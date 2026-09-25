// Three.js hero stage: the illustration floats as a gilded panel in front of a
// crimson sun, orbited by playing cards, poker chips and drifting gold dust.
import * as THREE from "three";

const canvas = document.getElementById("stage");
const hero = document.getElementById("hero");

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
} catch (e) {
  document.documentElement.classList.add("no-webgl");
  window.dispatchEvent(new Event("stage-ready"));
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x07080f, 0.045);
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
camera.position.set(0, 0, 11);

// ---------- Lights ----------
scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xfff1d6, 2.2);
key.position.set(4, 6, 8);
scene.add(key);
const rim = new THREE.PointLight(0xd3261c, 60, 30);
rim.position.set(-5, -2, 3);
scene.add(rim);
const goldLight = new THREE.PointLight(0xd8b25a, 40, 20);
goldLight.position.set(4, 3, 4);
scene.add(goldLight);

// ---------- Helpers: canvas textures ----------
function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return t;
}

function cardFace(rank, suit, red) {
  return canvasTexture(256, 358, (g, w, h) => {
    g.fillStyle = "#fbf8ef";
    roundRect(g, 0, 0, w, h, 18); g.fill();
    g.strokeStyle = "#d8b25a"; g.lineWidth = 4;
    roundRect(g, 8, 8, w - 16, h - 16, 12); g.stroke();
    g.fillStyle = red ? "#d3261c" : "#0b0c14";
    g.font = "700 54px Cinzel, serif";
    g.textAlign = "center";
    g.fillText(rank, 40, 64);
    g.font = "40px serif"; g.fillText(suit, 40, 106);
    g.save(); g.translate(w - 40, h - 64); g.rotate(Math.PI);
    g.font = "700 54px Cinzel, serif"; g.fillText(rank, 0, 0);
    g.font = "40px serif"; g.fillText(suit, 0, -42);
    g.restore();
    g.font = "150px serif"; g.textBaseline = "middle";
    g.fillText(suit, w / 2, h / 2 + 6);
  });
}

const cardBack = canvasTexture(256, 358, (g, w, h) => {
  g.fillStyle = "#8e140f"; roundRect(g, 0, 0, w, h, 18); g.fill();
  g.strokeStyle = "#d8b25a"; g.lineWidth = 6; roundRect(g, 12, 12, w - 24, h - 24, 12); g.stroke();
  // seigaiha (wave) pattern
  g.save(); roundRect(g, 18, 18, w - 36, h - 36, 8); g.clip();
  g.lineWidth = 2; g.strokeStyle = "rgba(243,220,154,.55)";
  for (let y = 0; y < h + 30; y += 18) {
    for (let x = (y / 18) % 2 ? 0 : 18; x < w + 36; x += 36) {
      for (let r = 18; r > 0; r -= 6) { g.beginPath(); g.arc(x, y, r, Math.PI, 0); g.stroke(); }
    }
  }
  g.restore();
  g.fillStyle = "#07080f"; g.beginPath(); g.arc(w / 2, h / 2, 52, 0, Math.PI * 2); g.fill();
  g.strokeStyle = "#d8b25a"; g.lineWidth = 3; g.stroke();
  g.fillStyle = "#f3dc9a"; g.font = "800 48px 'Shippori Mincho B1', serif";
  g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("紅", w / 2, h / 2 + 2);
});

function chipTexture(base, stripe) {
  return canvasTexture(256, 256, (g, w) => {
    const c = w / 2;
    g.fillStyle = base; g.beginPath(); g.arc(c, c, c, 0, Math.PI * 2); g.fill();
    for (let i = 0; i < 8; i++) {
      g.save(); g.translate(c, c); g.rotate((i / 8) * Math.PI * 2);
      g.fillStyle = stripe; g.fillRect(-14, -c, 28, 40);
      g.restore();
    }
    g.strokeStyle = "#d8b25a"; g.lineWidth = 5; g.setLineDash([10, 8]);
    g.beginPath(); g.arc(c, c, c * 0.62, 0, Math.PI * 2); g.stroke();
    g.setLineDash([]);
    g.fillStyle = base; g.beginPath(); g.arc(c, c, c * 0.56, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#f3dc9a"; g.font = "800 64px 'Shippori Mincho B1', serif";
    g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("扇", c, c + 4);
  });
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

// ---------- Crimson sun ----------
const sun = new THREE.Mesh(
  new THREE.CircleGeometry(4.2, 96),
  new THREE.MeshBasicMaterial({
    map: canvasTexture(512, 512, (g, w) => {
      const grd = g.createRadialGradient(w * 0.42, w * 0.38, 10, w / 2, w / 2, w / 2);
      grd.addColorStop(0, "#ff4a36"); grd.addColorStop(0.6, "#d3261c"); grd.addColorStop(1, "#7a0f0a");
      g.fillStyle = grd; g.fillRect(0, 0, w, w);
    }),
    fog: false,
  })
);
sun.position.set(1.6, 0.6, -6);
scene.add(sun);

// halo
const halo = new THREE.Mesh(
  new THREE.RingGeometry(4.35, 4.45, 128),
  new THREE.MeshBasicMaterial({ color: 0xd8b25a, transparent: true, opacity: 0.6, fog: false })
);
halo.position.copy(sun.position);
scene.add(halo);

// ---------- Main art panel ----------
const artGroup = new THREE.Group();
scene.add(artGroup);
const ART_H = 5.4, ART_W = ART_H * (896 / 1344);

const loader = new THREE.TextureLoader();
const artTex = loader.load("assets/geisha.jpg", () => window.dispatchEvent(new Event("stage-ready")));
artTex.colorSpace = THREE.SRGBColorSpace;
artTex.anisotropy = renderer.capabilities.getMaxAnisotropy();

const art = new THREE.Mesh(
  new THREE.PlaneGeometry(ART_W, ART_H),
  new THREE.MeshStandardMaterial({ map: artTex, roughness: 0.55, metalness: 0.0 })
);
art.position.z = 0.09;
artGroup.add(art);

const goldMat = new THREE.MeshStandardMaterial({ color: 0xd8b25a, metalness: 1, roughness: 0.28 });
const frame = new THREE.Mesh(new THREE.BoxGeometry(ART_W + 0.3, ART_H + 0.3, 0.16), goldMat);
artGroup.add(frame);
// inner lacquer line
const lacquer = new THREE.Mesh(
  new THREE.BoxGeometry(ART_W + 0.1, ART_H + 0.1, 0.17),
  new THREE.MeshStandardMaterial({ color: 0x07080f, roughness: 0.3 })
);
artGroup.add(lacquer);
// reverse side: lacquered card-back pattern, seen when the panel spins on shuffle
const artBack = new THREE.Mesh(
  new THREE.PlaneGeometry(ART_W, ART_H),
  new THREE.MeshStandardMaterial({ map: cardBack, roughness: 0.4 })
);
artBack.rotation.y = Math.PI;
artBack.position.z = -0.09;
artGroup.add(artBack);

// ---------- Cards ----------
const CARD_W = 0.9, CARD_H = CARD_W * 1.4;
const cardGeo = new THREE.BoxGeometry(CARD_W, CARD_H, 0.012);
const edgeMat = new THREE.MeshStandardMaterial({ color: 0xf3ecd8 });
const backMat = new THREE.MeshStandardMaterial({ map: cardBack, roughness: 0.45 });
const faces = [
  ["A", "♠", false], ["A", "♥", true], ["K", "♣", false], ["Q", "♦", true],
  ["J", "♠", false], ["7", "♥", true], ["A", "♦", true], ["K", "♠", false],
  ["Q", "♥", true], ["10", "♣", false],
];
const cards = faces.map(([r, s, red], i) => {
  const mesh = new THREE.Mesh(cardGeo, [
    edgeMat, edgeMat, edgeMat, edgeMat,
    new THREE.MeshStandardMaterial({ map: cardFace(r, s, red), roughness: 0.4 }),
    backMat,
  ]);
  const a = (i / faces.length) * Math.PI * 2;
  mesh.userData = {
    angle: a,
    radius: 4 + (i % 3) * 0.6,
    y: (Math.random() - 0.5) * 3.6,
    speed: 0.12 + Math.random() * 0.08,
    spin: new THREE.Vector3(Math.random() * 0.6, Math.random() * 0.9 + 0.3, Math.random() * 0.4),
    burst: 0,
  };
  scene.add(mesh);
  return mesh;
});

// ---------- Chips ----------
const chipGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.09, 48);
const chipDefs = [
  ["#d3261c", "#ede6d4"], ["#1b2847", "#ede6d4"], ["#0b0c14", "#d8b25a"], ["#d3261c", "#1b2847"],
];
const chips = [];
for (let i = 0; i < 14; i++) {
  const [base, stripe] = chipDefs[i % chipDefs.length];
  const top = new THREE.MeshStandardMaterial({ map: chipTexture(base, stripe), roughness: 0.35 });
  const side = new THREE.MeshStandardMaterial({ color: base, roughness: 0.4 });
  const chip = new THREE.Mesh(chipGeo, [side, top, top]);
  chip.position.set((Math.random() - 0.5) * 12, (Math.random() - 0.5) * 7, -2 + Math.random() * 5);
  if (Math.abs(chip.position.x) < 2.2 && chip.position.z > -1) chip.position.x += chip.position.x < 0 ? -2.6 : 2.6;
  chip.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
  chip.userData = {
    base: chip.position.clone(),
    phase: Math.random() * Math.PI * 2,
    rot: new THREE.Vector3((Math.random() - 0.5) * 1.4, (Math.random() - 0.5) * 1.4, 0),
    vel: new THREE.Vector3(),
  };
  scene.add(chip);
  chips.push(chip);
}

// ---------- Gold dust ----------
const DUST = 900;
const dustGeo = new THREE.BufferGeometry();
const pos = new Float32Array(DUST * 3);
const seeds = new Float32Array(DUST);
for (let i = 0; i < DUST; i++) {
  pos[i * 3] = (Math.random() - 0.5) * 24;
  pos[i * 3 + 1] = (Math.random() - 0.5) * 14;
  pos[i * 3 + 2] = (Math.random() - 0.5) * 14 - 2;
  seeds[i] = Math.random();
}
dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
dustGeo.setAttribute("seed", new THREE.BufferAttribute(seeds, 1));
const dustMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  uniforms: { uTime: { value: 0 }, uPR: { value: renderer.getPixelRatio() } },
  vertexShader: `
    attribute float seed; uniform float uTime; uniform float uPR; varying float vA;
    void main(){
      vec3 p = position;
      p.y += mod(uTime * (0.15 + seed * 0.25) + seed * 14.0, 14.0) - 7.0 - position.y * 0.0;
      p.x += sin(uTime * 0.5 + seed * 20.0) * 0.3;
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = (18.0 + seed * 26.0) * uPR / -mv.z;
      vA = 0.35 + 0.65 * abs(sin(uTime * 1.5 + seed * 40.0));
    }`,
  fragmentShader: `
    varying float vA;
    void main(){
      float d = length(gl_PointCoord - 0.5);
      float a = smoothstep(0.5, 0.0, d);
      gl_FragColor = vec4(vec3(1.0, 0.82, 0.45) * 1.4, a * vA);
    }`,
});
scene.add(new THREE.Points(dustGeo, dustMat));

// ---------- Interaction ----------
const mouse = new THREE.Vector2();
const target = new THREE.Vector2();
window.addEventListener("pointermove", (e) => {
  target.x = (e.clientX / window.innerWidth) * 2 - 1;
  target.y = -(e.clientY / window.innerHeight) * 2 + 1;
});
window.addEventListener("deviceorientation", (e) => {
  if (e.gamma == null) return;
  target.x = THREE.MathUtils.clamp(e.gamma / 30, -1, 1);
  target.y = THREE.MathUtils.clamp((e.beta - 45) / 30, -1, 1);
});

let shuffleT = 0;
canvas.addEventListener("click", () => {
  shuffleT = 1;
  cards.forEach((c) => { c.userData.burst = 1; c.userData.spin.multiplyScalar(-1); });
  chips.forEach((c) => {
    c.userData.vel.set((Math.random() - 0.5) * 6, 3 + Math.random() * 4, (Math.random() - 0.5) * 3);
  });
});

let scrollP = 0;
window.addEventListener("scroll", () => {
  scrollP = Math.min(window.scrollY / hero.offsetHeight, 1);
}, { passive: true });

// Keep the art to the right of the copy on wide screens, centered on narrow ones.
let artX = 2.2, artY = 0;
function resize() {
  const w = hero.clientWidth, h = hero.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  const narrow = w / h < 0.9;
  artX = narrow ? 0 : THREE.MathUtils.clamp((w / h - 0.9) * 2.4, 0.8, 2.4);
  camera.position.z = narrow ? 15.5 : 11;
  artY = narrow ? 1.9 : 0;
}
window.addEventListener("resize", resize);
resize();

// ---------- Loop ----------
const clock = new THREE.Clock();
let visible = true;
new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(hero);

function tick() {
  requestAnimationFrame(tick);
  if (!visible) return;
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  mouse.lerp(target, 0.05);
  shuffleT = Math.max(0, shuffleT - dt * 0.8);

  // art panel: float + tilt toward the pointer + tilt away with scroll
  artGroup.position.x = artX;
  artGroup.position.y = artY + Math.sin(t * 0.8) * 0.12;
  artGroup.rotation.y = mouse.x * 0.35 - 0.18 + Math.sin(t * 0.4) * 0.05 + shuffleT * Math.PI * 2 * easeOut(shuffleT);
  artGroup.rotation.x = -mouse.y * 0.22 + scrollP * 0.6;
  art.position.z = 0.09 + Math.sin(t * 0.8) * 0.01;

  sun.position.x = 1.6 + mouse.x * -0.4;
  sun.position.y = 0.6 + mouse.y * -0.3 + scrollP * 2;
  halo.position.copy(sun.position);
  halo.scale.setScalar(1 + Math.sin(t * 1.2) * 0.015);

  // cards orbit the panel like a dealer's fan
  cards.forEach((c, i) => {
    const u = c.userData;
    u.burst = Math.max(0, u.burst - dt * 0.7);
    u.angle += dt * (u.speed + u.burst * 1.6);
    const r = u.radius + u.burst * 2.5;
    c.position.set(
      artX + Math.cos(u.angle) * r,
      u.y + Math.sin(t * 0.7 + i) * 0.3 + artGroup.position.y,
      Math.sin(u.angle) * r * 0.55 - 0.5
    );
    c.rotation.x += dt * u.spin.x * (1 + u.burst * 6);
    c.rotation.y += dt * u.spin.y * (1 + u.burst * 6);
    c.rotation.z += dt * u.spin.z;
  });

  // chips bob; on shuffle they get tossed and fall back with a spring
  chips.forEach((c) => {
    const u = c.userData;
    u.vel.y -= dt * 9;
    c.position.addScaledVector(u.vel, dt);
    const home = u.base.clone();
    home.y += Math.sin(t * 0.9 + u.phase) * 0.25;
    c.position.lerp(home, u.vel.lengthSq() > 0.01 ? 0.02 : 0.08);
    u.vel.multiplyScalar(0.96);
    c.rotation.x += dt * u.rot.x * (1 + shuffleT * 8);
    c.rotation.y += dt * u.rot.y * (1 + shuffleT * 8);
  });

  dustMat.uniforms.uTime.value = t;

  camera.position.x = mouse.x * 0.6;
  camera.position.y = mouse.y * 0.4 - scrollP * 1.5;
  camera.lookAt(artX * 0.4, -scrollP * 1.2, 0);
  goldLight.position.x = 4 + Math.sin(t) * 2;

  renderer.render(scene, camera);
}
function easeOut(x) { return 1 - Math.pow(1 - x, 3); }
tick();
