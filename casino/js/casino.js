// UI motion + slot machine for 紅扇 BENI-OUGI
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Hero title: split into characters ----------
  $$(".hero-title .split").forEach((el) => {
    el.innerHTML = [...el.textContent].map((ch, i) =>
      `<span class="char" style="transition-delay:${0.25 + i * 0.06}s">${ch}</span>`).join("");
  });

  // ---------- Loader ----------
  let loaded = false;
  const finishLoading = () => {
    if (loaded) return;
    loaded = true;
    $("#loader").classList.add("done");
    document.body.classList.add("is-loaded");
    $$(".hero .reveal").forEach((el, i) => setTimeout(() => el.classList.add("in"), 700 + i * 150));
  };
  window.addEventListener("stage-ready", () => setTimeout(finishLoading, 400));
  setTimeout(finishLoading, 4000); // safety net if the CDN or texture is slow

  // ---------- Header ----------
  const header = $("#header");
  window.addEventListener("scroll", () => header.classList.toggle("scrolled", window.scrollY > 40), { passive: true });
  $("#menu-btn").addEventListener("click", () => document.body.classList.toggle("menu-open"));
  $$("#nav a").forEach((a) => a.addEventListener("click", () => document.body.classList.remove("menu-open")));

  // ---------- Cursor glow ----------
  const glow = $("#cursor-glow");
  let gx = innerWidth / 2, gy = innerHeight / 2, cx = gx, cy = gy;
  window.addEventListener("pointermove", (e) => { gx = e.clientX; gy = e.clientY; });
  (function glowLoop() {
    cx += (gx - cx) * 0.12; cy += (gy - cy) * 0.12;
    glow.style.transform = `translate(${cx}px, ${cy}px)`;
    requestAnimationFrame(glowLoop);
  })();

  // ---------- Reveal on scroll + counters ----------
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      $$("[data-count]", e.target).forEach(countUp);
      io.unobserve(e.target);
    });
  }, { threshold: 0.2 });
  $$("section:not(.hero) .reveal").forEach((el) => io.observe(el));

  function countUp(el) {
    const end = +el.dataset.count, start = performance.now(), dur = 1600;
    (function step(now) {
      const p = Math.min((now - start) / dur, 1);
      el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    })(start);
  }

  // ---------- Concept: layered parallax (mouse + scroll) ----------
  const visual = $("#concept-visual");
  const layers = $$(".layer", visual);
  let vx = 0, vy = 0;
  visual.addEventListener("pointermove", (e) => {
    const r = visual.getBoundingClientRect();
    vx = (e.clientX - r.left) / r.width - 0.5;
    vy = (e.clientY - r.top) / r.height - 0.5;
    applyParallax();
  });
  visual.addEventListener("pointerleave", () => { vx = vy = 0; applyParallax(); });
  window.addEventListener("scroll", applyParallax, { passive: true });
  function applyParallax() {
    const r = visual.getBoundingClientRect();
    const sp = (r.top + r.height / 2 - innerHeight / 2) / innerHeight; // -1..1 around viewport center
    layers.forEach((l) => {
      const d = +l.dataset.depth;
      l.style.transform =
        `translate3d(${vx * d * 0.6}px, ${vy * d * 0.6 + sp * d * 1.2}px, ${d}px)` +
        ` rotateY(${vx * 14}deg) rotateX(${-vy * 14}deg)`;
    });
    visual.style.setProperty("--shine", `${50 + vx * 100}%`);
    $(".frame-shine", visual).style.backgroundPosition = `${50 - vx * 120}% 0`;
  }

  // ---------- Game cards: 3D tilt with light follow ----------
  $$("[data-tilt]").forEach((card) => {
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      card.style.setProperty("--ry", `${(x - 0.5) * 22}deg`);
      card.style.setProperty("--rx", `${(0.5 - y) * 22}deg`);
      card.style.setProperty("--mx", `${x * 100}%`);
      card.style.setProperty("--my", `${y * 100}%`);
    });
    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
    });
  });

  // ---------- VIP card flip on tap ----------
  $("#vip-card").addEventListener("click", (e) => e.currentTarget.classList.toggle("flipped"));

  // ---------- Slot machine ----------
  // Each reel is a 3D drum: symbols sit on the faces of a prism and the reel
  // rotates around X, so spinning reads as a real cylinder.
  const SYMBOLS = [
    { ch: "扇", cls: "s-fan", pay: 50 },
    { ch: "7", cls: "s-7", pay: 20 },
    { ch: "♠", cls: "s-spade", pay: 10 },
    { ch: "♥", cls: "s-heart", pay: 10 },
    { ch: "桜", cls: "s-sakura", pay: 5 },
    { ch: "鶴", cls: "s-crane", pay: 3 },
    { ch: "♦", cls: "s-dia", pay: 3 },
    { ch: "月", cls: "s-moon", pay: 3 },
  ];
  // Weighted strip: rarer symbols appear less often
  const STRIP = ["桜", "♠", "鶴", "7", "月", "♥", "♦", "桜", "扇", "鶴", "♠", "月"]
    .map((c) => SYMBOLS.find((s) => s.ch === c));
  const N = STRIP.length, STEP = 360 / N;

  const reels = $$(".reel");
  const state = reels.map(() => ({ angle: 0, index: 0 }));

  function buildReels() {
    const cell = $(".reel-window").clientHeight;
    const radius = cell / 2 / Math.tan(Math.PI / N);
    reels.forEach((reel) => {
      reel.innerHTML = STRIP.map((s, i) =>
        `<div class="sym ${s.cls}" style="transform: rotateX(${-i * STEP}deg) translateZ(${radius}px)">${s.ch}</div>`
      ).join("");
      reel.dataset.radius = radius;
    });
    reels.forEach((r, i) => setReel(r, state[i].angle));
  }
  function setReel(reel, angle) {
    reel.style.transform = `translateZ(-${reel.dataset.radius}px) rotateX(${angle}deg)`;
  }
  buildReels();
  window.addEventListener("resize", buildReels);

  let credits = 1000, bet = 50, spinning = false;
  const creditsEl = $("#credits"), betEl = $("#bet"), msg = $("#slot-msg");
  const fmt = (n) => n.toLocaleString("en-US");
  function setCredits(n) {
    credits = n;
    creditsEl.textContent = fmt(n);
    const box = creditsEl.parentElement;
    box.classList.remove("bump"); void box.offsetWidth; box.classList.add("bump");
  }
  $("#bet-up").addEventListener("click", () => { bet = Math.min(bet + 50, 500); betEl.textContent = bet; });
  $("#bet-down").addEventListener("click", () => { bet = Math.max(bet - 50, 50); betEl.textContent = bet; });

  // jackpot ticker
  let jackpot = 77777;
  setInterval(() => { jackpot += Math.floor(Math.random() * 9); $("#jackpot").textContent = fmt(jackpot); }, 900);

  $("#spin-btn").addEventListener("click", spin);
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && isInView($("#slot-machine"))) { e.preventDefault(); spin(); }
  });

  function spin() {
    if (spinning) return;
    if (credits < bet) {
      msg.textContent = "クレジットが足りません — 1,000 を補充しました";
      setCredits(1000);
      return;
    }
    spinning = true;
    $("#spin-btn").disabled = true;
    $("#reels").classList.remove("win");
    setCredits(credits - bet);
    msg.textContent = "…";

    const results = reels.map(() => Math.floor(Math.random() * N));
    // A little mercy: occasionally line up the first two reels
    if (Math.random() < 0.18) results[1] = results[0];

    const done = reels.map((reel, i) => new Promise((resolve) => {
      const s = state[i];
      const turns = 3 + i;
      // rotating the drum by +STEP brings the next symbol (index+1) to the front
      const current = ((s.angle % 360) + 360) % 360;
      const targetMod = results[i] * STEP;
      let delta = targetMod - current; if (delta < 0) delta += 360;
      const from = s.angle, to = s.angle + turns * 360 + delta;
      const dur = reduced ? 10 : 1500 + i * 450;
      const t0 = performance.now();
      reel.classList.add("blur");
      (function frame(now) {
        const p = Math.min((now - t0) / dur, 1);
        const e = backOut(p);
        s.angle = from + (to - from) * e;
        setReel(reel, s.angle);
        if (p > 0.8) reel.classList.remove("blur");
        if (p < 1) requestAnimationFrame(frame);
        else { s.angle = to; s.index = results[i]; resolve(); }
      })(t0);
    }));

    Promise.all(done).then(() => {
      const syms = results.map((r) => STRIP[r]);
      const win = evaluate(syms);
      if (win > 0) {
        setCredits(credits + win);
        msg.textContent = win >= bet * 20 ? `大当たり！ ＋${fmt(win)}` : `当たり！ ＋${fmt(win)}`;
        $("#reels").classList.add("win");
        coinBurst(Math.min(12 + win / 20, 60));
      } else {
        msg.textContent = "はずれ — もう一勝負？";
      }
      spinning = false;
      $("#spin-btn").disabled = false;
    });
  }

  function evaluate([a, b, c]) {
    if (a === b && b === c) return bet * a.pay;
    if (a === b || b === c || a === c) return bet * 2;
    return 0;
  }

  function backOut(p) {
    const s = 0.9;
    return 1 + (s + 1) * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2);
  }

  function coinBurst(count) {
    if (reduced) return;
    const r = $("#reels").getBoundingClientRect();
    for (let i = 0; i < count; i++) {
      const coin = document.createElement("span");
      coin.className = "coin";
      document.body.appendChild(coin);
      const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
      const vx = (Math.random() - 0.5) * 900, vy = -500 - Math.random() * 600;
      const rot = Math.random() * 720;
      const t0 = performance.now();
      (function fly(now) {
        const t = (now - t0) / 1000;
        const x = x0 + vx * t, y = y0 + vy * t + 1400 * t * t;
        coin.style.transform = `translate(${x}px, ${y}px) rotateY(${rot * t * 3}deg)`;
        if (y < innerHeight + 40) requestAnimationFrame(fly); else coin.remove();
      })(t0);
    }
  }

  function isInView(el) {
    const r = el.getBoundingClientRect();
    return r.top < innerHeight && r.bottom > 0;
  }
})();
