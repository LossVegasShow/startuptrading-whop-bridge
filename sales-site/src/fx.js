(function () {
  // Visual layer for the sales page (design_fx). Decorative only: nothing here
  // touches checkout, attribution or tracking. Everything degrades to a complete
  // static page without JavaScript or with reduced motion.
  var root = document.querySelector('.sut.sut-fx');
  if (!root) return;
  root.classList.add('sut-js');
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var small = !!(window.matchMedia && window.matchMedia('(max-width: 760px)').matches);

  // ── Scroll reveal ────────────────────────────────────────────────────────
  // Common blocks on every page fade in as they scroll into view. Only blocks that
  // start below the fold are animated, so nothing visible on load ever flickers.
  var AUTO = '.sut-section .sut-head, .sut-tool, .sut-calc-card, .sut-calc-cta, .sut-frame, .sut-next > li, ' +
             '.sut-related li, .sut-faq, .sut-steps, .sut-list, .sut-sub, .sut-help > div, .sut-calc-table-wrap, .sut-calc-how';
  var fold = window.innerHeight || 800, autos = root.querySelectorAll(AUTO);
  for (var au = 0; au < autos.length; au++) {
    if (!autos[au].hasAttribute('data-reveal') && autos[au].getBoundingClientRect().top > fold) autos[au].setAttribute('data-reveal', '');
  }
  var reveals = root.querySelectorAll('[data-reveal]');
  if (reduce || !('IntersectionObserver' in window)) {
    for (var r = 0; r < reveals.length; r++) reveals[r].classList.add('is-in');
  } else {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); ro.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
    for (var q = 0; q < reveals.length; q++) ro.observe(reveals[q]);
  }

  // Demo videos (when real captures are configured): play only while visible.
  var vids = root.querySelectorAll('video[data-autoplay]');
  if (vids.length && 'IntersectionObserver' in window && !reduce) {
    var vo = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var v = e.target;
        if (e.isIntersecting) { if (v.preload === 'none') v.preload = 'auto'; var p = v.play(); if (p && p.catch) p.catch(function () {}); }
        else v.pause();
      });
    }, { threshold: 0.35 });
    for (var vi = 0; vi < vids.length; vi++) vo.observe(vids[vi]);
  }

  // ── Interactive ATR sizing demo ──────────────────────────────────────────
  var demo = root.querySelector('[data-atr-demo]');
  if (demo) {
    var k = function (n) { return demo.querySelector('[data-k="' + n + '"]'); };
    var o = function (n) { return demo.querySelector('[data-o="' + n + '"]'); };
    var money = function (v) { return '$' + Math.round(v).toLocaleString('en-US'); };
    var update = function () {
      var risk = Number(k('risk').value), pv = Number(k('pv').value), atr = Number(k('atr').value);
      var stop = 1.5 * atr, per = stop * pv, n = Math.floor(risk / per + 1e-9);
      o('atr').textContent = atr.toFixed(2);
      o('stop').textContent = stop.toFixed(2) + ' pts';
      o('per').textContent = money(per);
      o('n').textContent = String(n);
      o('used').textContent = money(n * per);
      var blocks = '';
      for (var b = 0; b < Math.min(n, 24); b++) blocks += '<i></i>';
      if (n > 24) blocks += '<em>+' + (n - 24) + '</em>';
      o('blocks').innerHTML = blocks;
      o('note').textContent = n === 0
        ? 'One contract would risk ' + money(per) + ', more than your ' + money(risk) + ' budget. Skip the trade or size down to a micro.'
        : 'Rounded down, so a loss never costs more than ' + money(risk) + '. Example only, not a recommendation.';
      demo.classList.toggle('is-zero', n === 0);
      var pct = (atr - Number(k('atr').min)) / (Number(k('atr').max) - Number(k('atr').min)) * 100;
      k('atr').style.setProperty('--fill', pct + '%');
    };
    demo.addEventListener('input', update);
    demo.addEventListener('change', update);
    update();
  }

  // ── Market chart engine (hero backdrop + tool illustration) ──────────────
  // Generated, not real market data: a random walk with changing volatility,
  // so ATR genuinely widens and narrows and the band "breathes".
  function rng(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var tick = function (v) { return Math.round(v * 4) / 4; };

  function Market(seed, start) {
    this.r = rng(seed); this.vol = 1; this.c = [];
    var p = start;
    for (var i = 0; i < 140; i++) { this.c.push(this.bar(p)); p = this.c[this.c.length - 1].c; }
    this.calc();
  }
  Market.prototype.bar = function (p) {
    var r = this.r;
    this.vol = Math.max(0.45, Math.min(2.4, this.vol + (r() - 0.5) * 0.22));
    var o = p, c = tick(o + (r() - 0.5) * 7 * this.vol + (r() - 0.47) * 1.2);
    return { o: o, c: c, h: tick(Math.max(o, c) + r() * 3 * this.vol), l: tick(Math.min(o, c) - r() * 3 * this.vol),
             v: (0.4 + r()) * this.vol, ticks: 0, len: 5 + Math.floor(r() * 5) };
  };
  Market.prototype.calc = function () {
    var c = this.c, atr = null, ema = null, a = 2 / 21;
    for (var i = 0; i < c.length; i++) {
      var b = c[i], pc = i ? c[i - 1].c : b.o;
      var tr = Math.max(b.h - b.l, Math.abs(b.h - pc), Math.abs(b.l - pc));
      atr = atr === null ? tr : (atr * 13 + tr) / 14;
      ema = ema === null ? b.c : ema + a * (b.c - ema);
      b.atr = atr; b.ema = ema;
    }
  };
  // One update of the forming candle; returns true when a new candle opened.
  Market.prototype.step = function () {
    var b = this.c[this.c.length - 1], r = this.r;
    b.c = tick(b.c + (r() - 0.5) * 2.4 * this.vol);
    b.h = Math.max(b.h, b.c); b.l = Math.min(b.l, b.c); b.v += r() * 0.15 * this.vol;
    var opened = false;
    if (++b.ticks >= b.len) {
      var nb = this.bar(b.c); nb.h = Math.max(nb.o, nb.c); nb.l = Math.min(nb.o, nb.c); nb.c = nb.o; nb.v = 0.1;
      this.c.push(nb); if (this.c.length > 220) this.c.shift(); opened = true;
    }
    this.calc();
    return opened;
  };

  var COL = { up: '61,220,151', dn: '255,107,107', acc: '250,123,57', txt: '179,188,201', mut: '123,134,152' };
  var rgba = function (c, a) { return 'rgba(' + c + ',' + a + ')'; };

  function Chart(canvas, opts) {
    this.cv = canvas; this.ctx = canvas.getContext('2d'); this.o = opts;
    this.m = new Market(opts.seed, opts.start); this.shift = 0; this.mn = null; this.mx = null;
    this.visible = true; this.last = 0; this.lastTick = 0;
    this.resize();
  }
  Chart.prototype.resize = function () {
    var dpr = Math.min(window.devicePixelRatio || 1, small ? 1.5 : 2);
    var w = this.cv.clientWidth, h = this.cv.clientHeight;
    if (!w || !h) return;
    this.d = dpr; this.cv.width = Math.round(w * dpr); this.cv.height = Math.round(h * dpr);
    this.draw();
  };
  Chart.prototype.draw = function () {
    var x = this.ctx, o = this.o, d = this.d || 1, W = this.cv.width, H = this.cv.height;
    if (!W || !H) return;
    x.clearRect(0, 0, W, H);
    var cw = o.cw * d, axis = o.axis ? 58 * d : 0, plotR = W - axis - o.gap * cw;
    var n = Math.min(this.m.c.length, Math.ceil(plotR / cw) + 2), vis = this.m.c.slice(-n);
    var lo = Infinity, hi = -Infinity;
    for (var i = 0; i < vis.length; i++) {
      var b = vis[i]; lo = Math.min(lo, b.l, b.ema - 2 * b.atr); hi = Math.max(hi, b.h, b.ema + 2 * b.atr);
    }
    var pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
    if (this.mn === null) { this.mn = lo; this.mx = hi; }
    this.mn += (lo - this.mn) * 0.06; this.mx += (hi - this.mx) * 0.06;
    var mn = this.mn, mx = this.mx, top = H * o.top, bot = H * o.bottom;
    var Y = function (v) { return top + (1 - (v - mn) / (mx - mn)) * (bot - top); };
    var X = function (idx) { return plotR - (vis.length - 1 - idx + 0.5 - this.shift) * cw; }.bind(this);

    // Horizontal grid and price axis
    x.font = (10.5 * d) + 'px "Geist Mono", ui-monospace, monospace'; x.textBaseline = 'middle';
    var stepP = Math.pow(10, Math.floor(Math.log10((mx - mn) / 4))); if ((mx - mn) / stepP > 8) stepP *= 2.5;
    for (var g = Math.ceil(mn / stepP) * stepP; g < mx; g += stepP) {
      var gy = Math.round(Y(g)) + 0.5;
      x.fillStyle = rgba('255,255,255', 0.035); x.fillRect(0, gy, W - axis, d);
      if (axis) { x.fillStyle = rgba(COL.mut, 0.55); x.fillText(g.toFixed(2), W - axis + 10 * d, gy); }
    }

    // Volume profile (right edge of the plot)
    if (o.profile) {
      var rows = 30, prof = [], max = 0, pw = (W - axis) * 0.13;
      for (var pr = 0; pr < rows; pr++) prof.push(0);
      for (var vi = 0; vi < vis.length; vi++) {
        var bb = vis[vi], idx = Math.floor((bb.c - mn) / (mx - mn) * rows);
        if (idx >= 0 && idx < rows) { prof[idx] += bb.v; max = Math.max(max, prof[idx]); }
      }
      var rh = (bot - top) / rows, poc = prof.indexOf(max);
      for (var p2 = 0; p2 < rows; p2++) {
        if (!prof[p2]) continue;
        var bw = prof[p2] / max * pw, by = bot - (p2 + 1) * rh;
        x.fillStyle = p2 === poc ? rgba(COL.acc, 0.22) : rgba('255,255,255', 0.045);
        x.fillRect(W - axis - bw, by + rh * 0.15, bw, rh * 0.7);
      }
    }

    // ATR band (EMA 20 ± 2 × ATR 14)
    var up = [], dn = [];
    for (var j = 0; j < vis.length; j++) {
      var cx = X(j); up.push([cx, Y(vis[j].ema + 2 * vis[j].atr)]); dn.push([cx, Y(vis[j].ema - 2 * vis[j].atr)]);
    }
    x.beginPath();
    up.forEach(function (pt, i2) { i2 ? x.lineTo(pt[0], pt[1]) : x.moveTo(pt[0], pt[1]); });
    for (var k2 = dn.length - 1; k2 >= 0; k2--) x.lineTo(dn[k2][0], dn[k2][1]);
    x.closePath();
    var grad = x.createLinearGradient(0, top, 0, bot);
    grad.addColorStop(0, rgba(COL.acc, 0.09)); grad.addColorStop(0.5, rgba(COL.acc, 0.035)); grad.addColorStop(1, rgba(COL.acc, 0.09));
    x.fillStyle = grad; x.fill();
    x.lineWidth = 1 * d; x.strokeStyle = rgba(COL.acc, 0.32);
    [up, dn].forEach(function (line) {
      x.beginPath(); line.forEach(function (pt, i3) { i3 ? x.lineTo(pt[0], pt[1]) : x.moveTo(pt[0], pt[1]); }); x.stroke();
    });

    // Candles
    var body = Math.max(2 * d, cw * 0.56);
    for (var c = 0; c < vis.length; c++) {
      var k3 = vis[c], kx = X(c), isUp = k3.c >= k3.o, col = isUp ? COL.up : COL.dn;
      var a = o.candleAlpha * (c === vis.length - 1 ? 1.4 : 1);
      x.fillStyle = rgba(col, a); x.fillRect(Math.round(kx) - d * 0.5, Y(k3.h), d, Math.max(d, Y(k3.l) - Y(k3.h)));
      var y0 = Y(Math.max(k3.o, k3.c)), y1 = Y(Math.min(k3.o, k3.c));
      x.fillRect(Math.round(kx - body / 2), y0, Math.round(body), Math.max(d, y1 - y0));
    }

    // EMA line with a soft glow
    x.save(); x.shadowColor = rgba(COL.acc, 0.7); x.shadowBlur = 10 * d;
    x.beginPath();
    for (var e = 0; e < vis.length; e++) { var ey = Y(vis[e].ema), ex = X(e); e ? x.lineTo(ex, ey) : x.moveTo(ex, ey); }
    x.lineWidth = 1.6 * d; x.strokeStyle = rgba(COL.acc, 0.85); x.stroke(); x.restore();

    var lastB = vis[vis.length - 1], ly = Y(lastB.c), lup = lastB.c >= lastB.o;
    // Order brackets (tool illustration): entry at the last close, stop 1.5 × ATR.
    if (o.bracket) {
      var atr = lastB.atr, stopD = Math.max(0.25, tick(1.5 * atr)), entry = lastB.c;
      var stop = entry - stopD, target = entry + 2 * stopD, n2 = Math.floor(o.risk / (stopD * o.pv));
      var x0 = X(vis.length - 1) - cw * 0.5, x1 = W - axis;
      x.fillStyle = rgba(COL.dn, 0.07); x.fillRect(x0, Y(entry), x1 - x0, Y(stop) - Y(entry));
      x.fillStyle = rgba(COL.up, 0.06); x.fillRect(x0, Y(target), x1 - x0, Y(entry) - Y(target));
      [[target, COL.up, 'TARGET  2R'], [entry, COL.txt, 'ENTRY  ' + n2 + ' × ' + o.market], [stop, COL.dn, 'STOP  1.5 × ATR']].forEach(function (row) {
        var yy = Math.round(Y(row[0])) + 0.5;
        x.setLineDash([4 * d, 4 * d]); x.strokeStyle = rgba(row[1], 0.75); x.lineWidth = d;
        x.beginPath(); x.moveTo(x0, yy); x.lineTo(x1, yy); x.stroke(); x.setLineDash([]);
        x.fillStyle = rgba(row[1], 0.95); x.fillText(row[2], x0 + 8 * d, yy + (row[0] === stop ? 10 : -9) * d);
      });
      x.fillStyle = rgba(COL.mut, 0.9);
      x.fillText('RISK $' + o.risk + '   ATR(14) ' + atr.toFixed(2) + '   STOP ' + stopD.toFixed(2) + ' pts', 14 * d, H - 14 * d);
      if (o.panel) {
        // The planner's size panel (top left of the plot): same arithmetic as the script.
        var micro = Math.floor(o.risk / (stopD * o.pv / 10)), pwid = 196 * d, ph = 118 * d, px = 14 * d, py = 14 * d;
        x.fillStyle = 'rgba(11,14,20,.88)'; x.strokeStyle = rgba(COL.acc, 0.45); x.lineWidth = d;
        x.beginPath(); if (x.roundRect) x.roundRect(px, py, pwid, ph, 8 * d); else x.rect(px, py, pwid, ph); x.fill(); x.stroke();
        var rowsP = [['RISK PLANNER', o.market + ' · fixed $', COL.mut, COL.mut],
                     ['MAX SIZE', n2 + ' ' + o.market, COL.mut, n2 ? COL.acc : COL.dn],
                     ['MICRO', micro + ' ' + o.micro, COL.mut, COL.txt],
                     ['RISK BUDGET', '$' + o.risk, COL.mut, COL.txt],
                     ['STOP RISK', '$' + (n2 * stopD * o.pv).toFixed(0), COL.mut, COL.txt]];
        rowsP.forEach(function (rw, ri) {
          var yy = py + (ri * 21 + 20) * d;
          x.fillStyle = rgba(rw[2], 0.95); x.fillText(rw[0], px + 12 * d, yy);
          x.fillStyle = rgba(rw[3], 1); x.textAlign = 'right'; x.fillText(rw[1], px + pwid - 12 * d, yy); x.textAlign = 'left';
        });
      }
    }

    // Last-price line and tag
    x.setLineDash([2 * d, 3 * d]); x.strokeStyle = rgba(lup ? COL.up : COL.dn, 0.45); x.lineWidth = d;
    x.beginPath(); x.moveTo(X(vis.length - 1), Math.round(ly) + 0.5); x.lineTo(W - axis, Math.round(ly) + 0.5); x.stroke(); x.setLineDash([]);
    if (axis) {
      x.fillStyle = rgba(lup ? COL.up : COL.dn, 0.9);
      x.fillRect(W - axis + 2 * d, ly - 9 * d, axis - 4 * d, 18 * d);
      x.fillStyle = '#07090d'; x.fillText(lastB.c.toFixed(2), W - axis + 9 * d, ly);
    }
  };
  Chart.prototype.frame = function (now) {
    if (!this.visible || document.hidden) return;
    if (now - this.lastTick > this.o.tickMs) {
      this.lastTick = now;
      if (this.m.step()) this.shift = 1;
    }
    this.shift = Math.max(0, this.shift - 0.06);
    if (now - this.last >= 1000 / this.o.fps) { this.last = now; this.draw(); }
  };

  var charts = [];
  function mount(el, opts) {
    if (!el || !el.getContext) return;
    var ch = new Chart(el, opts); charts.push(ch);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) { ch.visible = es[0].isIntersecting; }, { threshold: 0 }).observe(el);
    }
    if ('ResizeObserver' in window) new ResizeObserver(function () { ch.resize(); }).observe(el);
    else window.addEventListener('resize', function () { ch.resize(); });
  }

  function start() {
    mount(root.querySelector('.sut-hero-fx'), {
      seed: 20260, start: 5284, cw: small ? 11 : 13, gap: small ? 1 : 4, axis: !small, profile: !small,
      top: small ? 0.08 : 0.12, bottom: small ? 0.92 : 0.86, candleAlpha: small ? 0.3 : 0.42, fps: small ? 20 : 30, tickMs: 650
    });
    var tool = root.querySelectorAll('canvas[data-fx-chart="bracket"]');
    for (var t = 0; t < tool.length; t++) {
      var ds = tool[t].dataset, panel = ds.panel === 'true';
      mount(tool[t], { seed: 2067 + t, start: 5310, cw: small ? 6 : 8, gap: small ? 14 : 17, axis: true, profile: false, bracket: true,
        risk: Number(ds.risk || 180), pv: Number(ds.pv || 5), market: ds.market || 'MES', micro: ds.micro || 'MES', panel: panel,
        top: panel ? 0.34 : 0.2, bottom: 0.9, candleAlpha: 0.6, fps: 24, tickMs: 700 });
    }
    root.classList.add('sut-fx-on');
    if (reduce) return;                     // one still frame, no animation
    var loop = function (now) { for (var i = 0; i < charts.length; i++) charts[i].frame(now); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
  // After the page (and Jack's portrait) has loaded, so the effect never delays it.
  var go = function () { (window.requestIdleCallback || function (f) { setTimeout(f, 60); })(start, { timeout: 800 }); };
  if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
})();
