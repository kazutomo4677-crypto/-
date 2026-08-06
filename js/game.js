/* ============================================
   祭彩浪漫 -MATSURI SAI ROMAN-
   アドベンチャーエンジン
   ============================================ */

(function () {
  'use strict';

  const SAVE_KEY = 'saisai_roman_save_v1';
  const CFG_KEY = 'saisai_roman_cfg_v1';
  const CLEAR_KEY = 'saisai_roman_clear_v1';
  const AFF_MAX = 16;
  const DEFAULT_NAME = '千代';

  /* ---------- DOM ---------- */
  const $ = (id) => document.getElementById(id);
  const el = {
    title: $('title-screen'),
    game: $('game-screen'),
    bg: $('bg-layer'),
    sprite: $('sprite'),
    spriteWrap: $('sprite-wrap'),
    box: $('message-box'),
    name: $('speaker-name'),
    text: $('message-text'),
    marker: $('next-marker'),
    choices: $('choice-layer'),
    chapter: $('chapter-card'),
    chapterMain: $('chapter-main'),
    chapterSub: $('chapter-sub'),
    nameModal: $('name-modal'),
    nameInput: $('name-input'),
    nameOk: $('name-ok'),
    log: $('log-modal'),
    logBody: $('log-body'),
    saveModal: $('save-modal'),
    saveBody: $('save-body'),
    saveTitle: $('save-modal-title'),
    cfgModal: $('config-modal'),
    speed: $('cfg-speed'),
    speedVal: $('cfg-speed-val'),
    autoSpeed: $('cfg-auto'),
    autoVal: $('cfg-auto-val'),
    affBar: $('aff-bar'),
    affWrap: $('aff-meter'),
    ending: $('ending-screen'),
    endTitle: $('ending-title'),
    endText: $('ending-text'),
    endAff: $('ending-aff'),
    fx: $('fx-layer'),
    btnAuto: $('btn-auto'),
    btnSkip: $('btn-skip'),
    clearMark: $('clear-mark')
  };

  /* ---------- ラベル索引 ---------- */
  const labels = {};
  SCENARIO.forEach((c, i) => { if (c.t === 'label') labels[c.v] = i; });

  /* ---------- 設定 ---------- */
  let cfg = { speed: 30, auto: 50 };
  try {
    const s = localStorage.getItem(CFG_KEY);
    if (s) cfg = Object.assign(cfg, JSON.parse(s));
  } catch (e) { /* 設定が壊れていても既定値で続行 */ }

  function saveCfg() {
    try { localStorage.setItem(CFG_KEY, JSON.stringify(cfg)); } catch (e) {}
  }
  // speed 0〜100 → 1文字あたり 60ms〜0ms
  const charDelay = () => Math.round((100 - cfg.speed) * 0.6);
  const autoDelay = () => 2600 - cfg.auto * 20;

  /* ---------- 状態 ---------- */
  let st = null;
  function freshState() {
    return {
      i: 0,            // 次に実行する命令
      cur: 0,          // いま表示中の命令
      aff: 0,
      name: DEFAULT_NAME,
      flags: {},
      chapter: '序章',
      bg: 'shop',
      sp: null,
      spExpr: 'normal',
      log: []
    };
  }

  /* ---------- 表示制御 ---------- */
  let typing = null;      // タイプライターのタイマー
  let fullText = '';      // 現在行の全文
  let waiting = false;    // クリック待ち
  let auto = false;
  let skip = false;
  let autoTimer = null;

  function subst(s) {
    return String(s).replace(/\{\{name\}\}/g, st.name);
  }

  function setBg(v) {
    st.bg = v;
    el.bg.className = 'bg-layer bg-' + v;
  }

  function setSprite(v, e) {
    if (!v) {
      st.sp = null;
      el.spriteWrap.classList.remove('is-on');
      return;
    }
    const changed = st.sp !== v;
    st.sp = v;
    st.spExpr = e || 'normal';
    el.sprite.src = 'assets/char/' + v + '_base.jpg';
    el.sprite.alt = '東雲 燿';
    el.spriteWrap.className = 'sprite-wrap is-on expr-' + st.spExpr;
    if (changed) {
      el.spriteWrap.classList.add('is-enter');
      setTimeout(() => el.spriteWrap.classList.remove('is-enter'), 600);
    }
  }

  function fx(kind) {
    const d = document.createElement('div');
    d.className = 'fx fx-' + kind;
    el.fx.appendChild(d);
    if (kind === 'shake') {
      el.game.classList.add('shaking');
      setTimeout(() => el.game.classList.remove('shaking'), 500);
    }
    setTimeout(() => d.remove(), 1600);
  }

  function updateAff() {
    const pct = Math.max(0, Math.min(100, (st.aff / AFF_MAX) * 100));
    el.affBar.style.width = pct + '%';
    el.affWrap.dataset.level = st.aff >= 12 ? 'high' : st.aff >= 6 ? 'mid' : 'low';
  }

  /* ---------- タイプライター ---------- */
  function say(speaker, text, cls) {
    clearTimeout(typing);
    fullText = subst(text);
    el.box.className = 'message-box ' + (cls || '');
    if (speaker) {
      el.name.textContent = subst(speaker);
      el.name.classList.remove('is-hidden');
    } else {
      el.name.classList.add('is-hidden');
    }
    st.log.push({ n: speaker ? subst(speaker) : '', v: fullText });
    if (st.log.length > 200) st.log.shift();

    el.marker.classList.remove('is-on');
    el.text.textContent = '';
    waiting = true;

    const delay = skip ? 0 : charDelay();
    if (delay === 0) { el.text.textContent = fullText; onLineDone(); return; }

    let n = 0;
    (function step() {
      n++;
      el.text.textContent = fullText.slice(0, n);
      if (n < fullText.length) typing = setTimeout(step, delay);
      else onLineDone();
    })();
  }

  function onLineDone() {
    typing = null;
    el.marker.classList.add('is-on');
    if (skip) { autoTimer = setTimeout(advance, 30); return; }
    if (auto) autoTimer = setTimeout(advance, autoDelay() + fullText.length * 22);
  }

  function finishTyping() {
    if (!typing) return false;
    clearTimeout(typing);
    typing = null;
    el.text.textContent = fullText;
    onLineDone();
    return true;
  }

  /* ---------- 進行 ---------- */
  function advance() {
    clearTimeout(autoTimer);
    if (!waiting) return;
    waiting = false;
    run();
  }

  function onScreenClick() {
    if (el.choices.classList.contains('is-on')) return;
    if (anyModalOpen()) return;
    if (finishTyping()) { if (auto || skip) return; return; }
    advance();
  }

  function run() {
    while (st.i < SCENARIO.length) {
      const c = SCENARIO[st.i];
      st.cur = st.i;
      st.i++;

      switch (c.t) {
        case 'label':
          break;
        case 'goto':
          st.i = labels[c.v];
          break;
        case 'bg':
          setBg(c.v);
          break;
        case 'sp':
          setSprite(c.v, c.e);
          break;
        case 'aff':
          st.aff += c.v; updateAff();
          break;
        case 'flag':
          st.flags[c.k] = c.v;
          break;
        case 'fx':
          if (!skip) fx(c.v);
          break;
        case 'branch': {
          let target;
          if (c.map) target = c.map[st.flags[c.flag]] || Object.values(c.map)[0];
          else target = st.aff >= c.th ? c.hi : c.lo;
          st.i = labels[target];
          break;
        }
        case 'chapter':
          showChapter(c); return;
        case 'name':
          askName(); return;
        case 'choice':
          showChoices(c.v); return;
        case 'say':
          autoSave();
          say(c.n === '__me__' ? st.name : c.n, c.v, 'is-say');
          return;
        case 'mono':
          autoSave();
          say(null, c.v, 'is-mono');
          return;
        case 'nar':
          autoSave();
          say(null, c.v, 'is-nar');
          return;
        case 'end':
          showEnding(c); return;
        default:
          break;
      }
    }
  }

  /* ---------- 章タイトル ---------- */
  function showChapter(c) {
    st.chapter = c.v;
    el.chapterMain.textContent = c.v;
    el.chapterSub.textContent = c.sub || '';
    el.chapter.classList.add('is-on');
    waiting = true;
    const close = () => {
      el.chapter.classList.remove('is-on');
      el.chapter.removeEventListener('click', close);
      advance();
    };
    el.chapter.addEventListener('click', close);
    setTimeout(() => { if (el.chapter.classList.contains('is-on')) close(); }, skip ? 300 : 3000);
  }

  /* ---------- 名前入力 ---------- */
  function askName() {
    el.nameModal.classList.add('is-on');
    el.nameInput.value = st.name === DEFAULT_NAME ? '' : st.name;
    setTimeout(() => el.nameInput.focus(), 60);
    waiting = true;
  }

  function confirmName() {
    const v = el.nameInput.value.trim();
    st.name = v ? v.slice(0, 8) : DEFAULT_NAME;
    el.nameModal.classList.remove('is-on');
    advance();
  }

  /* ---------- 選択肢 ---------- */
  function showChoices(list) {
    skip = false; auto = false; syncModeBtns();
    el.choices.innerHTML = '';
    el.choices.classList.add('is-on');
    list.forEach((o) => {
      const b = document.createElement('button');
      b.className = 'choice-btn';
      b.textContent = subst(o.text);
      b.addEventListener('click', () => {
        el.choices.classList.remove('is-on');
        el.choices.innerHTML = '';
        if (o.aff) { st.aff += o.aff; updateAff(); }
        if (o.flag) st.flags[o.flag[0]] = o.flag[1];
        st.log.push({ n: '選択', v: '▶ ' + subst(o.text) });
        if (o.goto) st.i = labels[o.goto];
        waiting = true;
        advance();
      });
      el.choices.appendChild(b);
    });
    waiting = false;
  }

  /* ---------- エンディング ---------- */
  function showEnding(c) {
    skip = false; auto = false; syncModeBtns();
    el.endTitle.textContent = c.title;
    el.endText.textContent = subst(c.text);
    el.endAff.textContent = '親密度  ' + st.aff + ' / ' + AFF_MAX;
    el.ending.classList.add('is-on');
    try {
      const cleared = JSON.parse(localStorage.getItem(CLEAR_KEY) || '{}');
      cleared[c.v] = true;
      localStorage.setItem(CLEAR_KEY, JSON.stringify(cleared));
    } catch (e) {}
    waiting = false;
  }

  /* ---------- セーブ / ロード ---------- */
  function readSaves() {
    try { return JSON.parse(localStorage.getItem(SAVE_KEY) || '{}'); }
    catch (e) { return {}; }
  }
  function writeSaves(o) {
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(o)); return true; }
    catch (e) { return false; }
  }

  function snapshot() {
    return {
      i: st.cur, aff: st.aff, name: st.name,
      flags: Object.assign({}, st.flags),
      chapter: st.chapter, bg: st.bg, sp: st.sp, spExpr: st.spExpr,
      log: st.log.slice(-60),
      at: new Date().toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
      preview: (SCENARIO[st.cur] && SCENARIO[st.cur].v ? subst(String(SCENARIO[st.cur].v)) : '').slice(0, 34)
    };
  }

  function autoSave() {
    const o = readSaves();
    o.auto = snapshot();
    writeSaves(o);
  }

  function doSave(slot) {
    const o = readSaves();
    o['s' + slot] = snapshot();
    if (writeSaves(o)) { closeModal(el.saveModal); toast('第' + slot + '欄に記しました'); }
    else toast('保存に失敗しました');
  }

  function doLoad(slot) {
    const o = readSaves();
    const d = o[slot === 'auto' ? 'auto' : 's' + slot];
    if (!d) return;
    st = freshState();
    st.i = d.i; st.cur = d.i; st.aff = d.aff; st.name = d.name;
    st.flags = d.flags || {}; st.chapter = d.chapter; st.log = d.log || [];
    closeModal(el.saveModal);
    el.title.classList.remove('is-on');
    el.ending.classList.remove('is-on');
    el.game.classList.add('is-on');
    setBg(d.bg || 'shop');
    if (d.sp) setSprite(d.sp, d.spExpr); else setSprite(null);
    updateAff();
    skip = false; auto = false; syncModeBtns();
    waiting = true;
    advance();
  }

  function openSaveModal(mode) {
    const saves = readSaves();
    el.saveTitle.textContent = mode === 'save' ? '記す（セーブ）' : '読む（ロード）';
    el.saveBody.innerHTML = '';
    const slots = mode === 'save' ? [1, 2, 3] : ['auto', 1, 2, 3];
    slots.forEach((s) => {
      const key = s === 'auto' ? 'auto' : 's' + s;
      const d = saves[key];
      const b = document.createElement('button');
      b.className = 'slot' + (d ? '' : ' is-empty');
      b.innerHTML =
        '<span class="slot-no">' + (s === 'auto' ? '自動' : '第' + s + '欄') + '</span>' +
        (d
          ? '<span class="slot-main"><span class="slot-ch">' + d.chapter + '　／　親密度 ' + d.aff + '</span>' +
            '<span class="slot-prev">' + escapeHtml(d.preview) + '…</span></span>' +
            '<span class="slot-at">' + d.at + '</span>'
          : '<span class="slot-main"><span class="slot-prev">—— 空 ——</span></span>');
      if (mode === 'load' && !d) b.disabled = true;
      b.addEventListener('click', () => mode === 'save' ? doSave(s) : doLoad(s));
      el.saveBody.appendChild(b);
    });
    openModal(el.saveModal);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  /* ---------- バックログ ---------- */
  function openLog() {
    el.logBody.innerHTML = '';
    st.log.slice().reverse().forEach((l) => {
      const d = document.createElement('div');
      d.className = 'log-line' + (l.n === '選択' ? ' is-choice' : '');
      d.innerHTML = (l.n && l.n !== '選択' ? '<span class="log-name">' + escapeHtml(l.n) + '</span>' : '') +
        '<span class="log-text">' + escapeHtml(l.v) + '</span>';
      el.logBody.appendChild(d);
    });
    openModal(el.log);
  }

  /* ---------- モーダル ---------- */
  function openModal(m) { auto = false; skip = false; syncModeBtns(); clearTimeout(autoTimer); m.classList.add('is-on'); }
  function closeModal(m) { m.classList.remove('is-on'); }
  function anyModalOpen() {
    return [el.log, el.saveModal, el.cfgModal, el.nameModal, el.ending, el.chapter]
      .some((m) => m.classList.contains('is-on'));
  }

  function toast(msg) {
    const d = document.createElement('div');
    d.className = 'toast';
    d.textContent = msg;
    document.body.appendChild(d);
    setTimeout(() => d.classList.add('is-on'), 10);
    setTimeout(() => { d.classList.remove('is-on'); setTimeout(() => d.remove(), 400); }, 1800);
  }

  function syncModeBtns() {
    el.btnAuto.classList.toggle('is-active', auto);
    el.btnSkip.classList.toggle('is-active', skip);
  }

  /* ---------- 開始 ---------- */
  function startGame() {
    st = freshState();
    el.title.classList.remove('is-on');
    el.ending.classList.remove('is-on');
    el.game.classList.add('is-on');
    setBg('shop');
    setSprite(null);
    updateAff();
    skip = false; auto = false; syncModeBtns();
    waiting = true;
    advance();
  }

  function backToTitle() {
    clearTimeout(typing); clearTimeout(autoTimer);
    auto = false; skip = false; syncModeBtns();
    [el.log, el.saveModal, el.cfgModal, el.nameModal].forEach(closeModal);
    el.ending.classList.remove('is-on');
    el.game.classList.remove('is-on');
    el.title.classList.add('is-on');
    refreshTitle();
  }

  function refreshTitle() {
    let cleared = {};
    try { cleared = JSON.parse(localStorage.getItem(CLEAR_KEY) || '{}'); } catch (e) {}
    const got = Object.keys(cleared).length;
    el.clearMark.textContent = got ? '到達した結末　' + got + ' / 2　（' + Object.keys(cleared).sort().join('・') + '）' : '';
    const saves = readSaves();
    $('btn-continue').disabled = !saves.auto;
  }

  /* ---------- イベント配線 ---------- */
  $('btn-start').addEventListener('click', startGame);
  $('btn-continue').addEventListener('click', () => doLoad('auto'));
  $('btn-title-load').addEventListener('click', () => openSaveModal('load'));
  $('btn-title-config').addEventListener('click', () => { syncCfgUI(); openModal(el.cfgModal); });

  $('click-area').addEventListener('click', onScreenClick);

  el.btnAuto.addEventListener('click', () => {
    auto = !auto; skip = false; syncModeBtns();
    clearTimeout(autoTimer);
    if (auto && !typing && waiting) autoTimer = setTimeout(advance, 400);
  });
  el.btnSkip.addEventListener('click', () => {
    skip = !skip; auto = false; syncModeBtns();
    clearTimeout(autoTimer);
    if (skip) { if (!finishTyping() && waiting) advance(); }
  });
  $('btn-log').addEventListener('click', openLog);
  $('btn-save').addEventListener('click', () => openSaveModal('save'));
  $('btn-load').addEventListener('click', () => openSaveModal('load'));
  $('btn-config').addEventListener('click', () => { syncCfgUI(); openModal(el.cfgModal); });
  $('btn-quit').addEventListener('click', () => {
    if (confirm('題名画面に戻ります。自動記録より再開できます。')) backToTitle();
  });

  el.nameOk.addEventListener('click', confirmName);
  el.nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmName(); });
  document.querySelectorAll('[data-name-preset]').forEach((b) => {
    b.addEventListener('click', () => { el.nameInput.value = b.dataset.namePreset; });
  });

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.addEventListener('click', () => closeModal($(b.dataset.close)));
  });

  el.speed.addEventListener('input', () => {
    cfg.speed = +el.speed.value; el.speedVal.textContent = cfg.speed; saveCfg();
  });
  el.autoSpeed.addEventListener('input', () => {
    cfg.auto = +el.autoSpeed.value; el.autoVal.textContent = cfg.auto; saveCfg();
  });
  function syncCfgUI() {
    el.speed.value = cfg.speed; el.speedVal.textContent = cfg.speed;
    el.autoSpeed.value = cfg.auto; el.autoVal.textContent = cfg.auto;
  }

  $('btn-ending-title').addEventListener('click', backToTitle);
  $('btn-ending-retry').addEventListener('click', startGame);

  document.addEventListener('keydown', (e) => {
    if (!el.game.classList.contains('is-on')) return;
    if (el.nameModal.classList.contains('is-on')) return;
    if (e.key === 'Escape') {
      [el.log, el.saveModal, el.cfgModal].forEach(closeModal);
      return;
    }
    if (anyModalOpen()) return;
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); onScreenClick(); }
    if (e.key === 'Control') { skip = true; syncModeBtns(); if (!finishTyping() && waiting) advance(); }
  });
  document.addEventListener('keyup', (e) => {
    if (e.key === 'Control' && skip) { skip = false; syncModeBtns(); }
  });

  /* ---------- 初期化 ---------- */
  syncCfgUI();
  refreshTitle();
  el.title.classList.add('is-on');
})();
