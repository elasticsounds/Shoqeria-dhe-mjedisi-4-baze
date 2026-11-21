/* Shared behaviour for lesson screens (see book-design/lesson.css).
   Shows the lesson name in the reader bar on screens that have no entry of
   their own in the table of contents, and runs the two custom activities
   (self-assessment squares, the question game), which register with the
   reader's activity system so they get its Submit button.
   Loaded once; it keeps working when the reader swaps pages without a reload. */
(function () {
  if (window.BookLesson) return;
  var FALLBACKS = ['Indeksi', 'Contents', 'Table of Contents'];

  function syncReaderTitle() {
    var content = document.getElementById('content');
    var want = content && content.getAttribute('data-reader-title');
    var spans = document.querySelectorAll('button[data-dock-trigger] > span.truncate');
    for (var i = 0; i < spans.length; i++) {
      var span = spans[i];
      var current = span.textContent.trim();
      var ours = span.getAttribute('data-lx-title');
      if (want) {
        if (current === want) continue;
        if (FALLBACKS.indexOf(current) > -1 || (ours && current === ours)) {
          if (FALLBACKS.indexOf(current) > -1) span.setAttribute('data-lx-fallback', current);
          span.textContent = want;
          span.setAttribute('data-lx-title', want);
        }
      } else if (ours && current === ours) {
        span.textContent = span.getAttribute('data-lx-fallback') || FALLBACKS[0];
        span.removeAttribute('data-lx-title');
      }
    }
  }

  /* ---- custom activities: registered with the reader so they get its Submit button ---- */
  function register(section, handlers) {
    if (typeof window.adtRegisterCustomActivity === 'function') window.adtRegisterCustomActivity(section, handlers);
    else (window.__adtPendingCustomActivities = window.__adtPendingCustomActivities || []).push({ section: section, handlers: handlers });
  }
  function store(section) {
    var key = 'sdm4:' + section.getAttribute('data-section-id');
    return {
      get: function () { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; } },
      set: function (value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* not saved */ } }
    };
  }
  function string(root, name) {
    var el = root.querySelector('[data-lx-string="' + name + '"]');
    return el ? el.textContent.trim() : '';
  }

  function initRating(section) {
    var root = section.querySelector('[data-lx-rating]');
    if (!root) return;
    var saved = store(section), status = root.querySelector('[data-lx-status]');
    var groups = root.querySelectorAll('[data-lx-rate]');
    var state = saved.get() || {};
    function read() {
      var out = {};
      for (var i = 0; i < groups.length; i++) {
        var checked = groups[i].querySelector('input:checked');
        if (checked) out[groups[i].getAttribute('data-lx-rate')] = checked.value;
      }
      return out;
    }
    for (var i = 0; i < groups.length; i++) {
      var value = state[groups[i].getAttribute('data-lx-rate')];
      var input = value && groups[i].querySelector('input[value="' + value + '"]');
      if (input) input.checked = true;
    }
    root.addEventListener('change', function () { saved.set(read()); status.textContent = ''; });
    register(section, { validate: function () {
      var done = Object.keys(read()).length === groups.length;
      status.textContent = done ? '' : string(root, 'incomplete');
      if (!done) { var first = root.querySelector('[data-lx-rate]:not(:has(input:checked)) input'); if (first) first.focus(); }
      return done;
    } });
  }

  function initGame(section) {
    var root = section.querySelector('[data-lx-game]');
    if (!root) return;
    var saved = store(section), status = root.querySelector('[data-lx-status]');
    var items = root.querySelectorAll('[data-lx-q]'), card = root.querySelector('[data-lx-card]');
    var draw = root.querySelector('[data-lx-draw]'), question = root.querySelector('[data-lx-question]');
    var players = root.querySelectorAll('[data-lx-player]');
    var state = saved.get() || { scores: [0, 0], done: [], turn: 0, current: null };
    function name(n) { return players[n].querySelector('span').textContent.trim(); }
    function paint() {
      for (var n = 0; n < players.length; n++) {
        players[n].querySelector('output').textContent = state.scores[n];
        if (n === state.turn && state.done.length < items.length) players[n].setAttribute('aria-current', 'true');
        else players[n].removeAttribute('aria-current');
      }
      for (var i = 0; i < items.length; i++) {
        var q = Number(items[i].getAttribute('data-lx-q'));
        if (state.done.indexOf(q) > -1) items[i].setAttribute('data-lx-done', ''); else items[i].removeAttribute('data-lx-done');
        if (q === state.current) items[i].setAttribute('aria-current', 'true'); else items[i].removeAttribute('aria-current');
      }
      var finished = state.done.length >= items.length;
      card.hidden = state.current === null;
      draw.disabled = finished || state.current !== null;
      if (state.current !== null) {
        question.textContent = root.querySelector('[data-lx-q="' + state.current + '"]').textContent;
        status.textContent = string(root, 'turn') + ' ' + name(state.turn);
      } else if (finished) {
        var a = state.scores[0], b = state.scores[1];
        status.textContent = string(root, 'over') + ' ' + (a === b ? string(root, 'tie') : string(root, 'winner') + ' ' + name(a > b ? 0 : 1));
      } else {
        status.textContent = string(root, 'turn') + ' ' + name(state.turn);
      }
      saved.set(state);
    }
    function answer(points) {
      if (state.current === null) return;
      state.scores[state.turn] += points;
      state.done.push(state.current);
      state.current = null;
      state.turn = 1 - state.turn;
      paint();
      if (!draw.disabled) draw.focus();
    }
    draw.addEventListener('click', function () {
      var open = [];
      for (var i = 0; i < items.length; i++) {
        var q = Number(items[i].getAttribute('data-lx-q'));
        if (state.done.indexOf(q) < 0) open.push(q);
      }
      if (!open.length) return;
      state.current = open[Math.floor(Math.random() * open.length)];
      paint();
      root.querySelector('[data-lx-right]').focus();
    });
    root.querySelector('[data-lx-right]').addEventListener('click', function () { answer(2); });
    root.querySelector('[data-lx-wrong]').addEventListener('click', function () { answer(0); });
    paint();
    register(section, { validate: function () {
      var finished = state.done.length >= items.length;
      if (!finished) status.textContent = string(root, 'unfinished');
      return finished;
    } });
  }

  function initCustom() {
    var section = document.querySelector('#content section[data-section-type^="activity_custom"]');
    if (!section || section.getAttribute('data-lx-ready')) return;
    section.setAttribute('data-lx-ready', '1');
    initRating(section);
    initGame(section);
  }

  var queued = false;
  function run() {
    queued = false;
    initCustom();
    syncReaderTitle();
  }
  function schedule() {
    if (queued) return;
    queued = true;
    (window.requestAnimationFrame || setTimeout)(run);
  }

  window.BookLesson = { init: run };
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
