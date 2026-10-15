// Звуки синтезируются на лету (WebAudio) — никаких файлов.
(function () {
  const Z = window.Z = window.Z || {};
  let ctx = null, noiseBuf = null;

  function ac() {
    if (Sfx.muted) return null;
    try {
      if (!ctx) {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
        const d = noiseBuf.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      }
      if (ctx.state === 'suspended') ctx.resume();
      return ctx;
    } catch (e) { return null; }
  }

  function env(c, vol, dur) {
    const g = c.createGain();
    g.gain.setValueAtTime(vol, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + dur);
    g.connect(c.destination);
    return g;
  }

  function tone(freq, dur, type, vol, slideTo) {
    const c = ac(); if (!c) return;
    const o = c.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(freq, c.currentTime);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, c.currentTime + dur);
    o.connect(env(c, vol, dur));
    o.start();
    o.stop(c.currentTime + dur);
  }

  function hiss(dur, freq, vol) {
    const c = ac(); if (!c) return;
    const s = c.createBufferSource();
    s.buffer = noiseBuf;
    const f = c.createBiquadFilter();
    f.type = 'lowpass';
    f.frequency.value = freq;
    s.connect(f).connect(env(c, vol, dur));
    s.start(0, Math.random() * 0.5, dur);
  }

  const Sfx = Z.Sfx = {
    muted: false,
    swing() { hiss(0.12, 1800, 0.12); },
    hit() { tone(110, 0.14, 'square', 0.12, 50); hiss(0.08, 700, 0.25); },
    shot() { hiss(0.35, 3500, 0.6); tone(90, 0.18, 'square', 0.2, 40); },
    empty() { tone(1400, 0.04, 'square', 0.05); },
    hurt() { tone(260, 0.25, 'sawtooth', 0.1, 120); },
    groan() { tone(70 + Math.random() * 40, 0.9, 'sawtooth', 0.045, 55); },
    pick() { tone(660, 0.07, 'triangle', 0.12); setTimeout(() => tone(990, 0.08, 'triangle', 0.1), 60); },
    eat() { hiss(0.08, 1200, 0.15); setTimeout(() => hiss(0.08, 1000, 0.12), 120); },
    die() { tone(180, 1.2, 'sawtooth', 0.12, 40); },
  };
})();
