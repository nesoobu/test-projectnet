// Слой платформы: всё, что зависит от Telegram, собрано здесь.
// При переносе в мобильное приложение (Capacitor и т.п.) достаточно переписать этот файл,
// game.js трогать не нужно.
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const inTelegram = !!(tg && tg.initData);
  const can = (version) => inTelegram && tg.isVersionAtLeast(version);

  function localGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function localSet(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* приватный режим */ } }

  window.Platform = {
    inTelegram,

    init(bgColor) {
      if (!inTelegram) return;
      tg.ready();
      tg.expand();
      if (can('7.7')) tg.disableVerticalSwipes(); // чтобы свайп не сворачивал игру
      if (can('6.1')) { tg.setHeaderColor(bgColor); tg.setBackgroundColor(bgColor); }
    },

    // kind: light | medium | heavy | success | warning | error
    haptic(kind) {
      if (can('6.1')) {
        const h = tg.HapticFeedback;
        if (kind === 'success' || kind === 'warning' || kind === 'error') h.notificationOccurred(kind);
        else h.impactOccurred(kind);
      } else if (navigator.vibrate) {
        navigator.vibrate(kind === 'error' ? [40, 40, 80] : kind === 'success' ? 30 : 10);
      }
    },

    // Хранилище: CloudStorage Telegram (синхронизируется между устройствами) + localStorage.
    getItem(key) {
      return new Promise((resolve) => {
        const local = localGet(key);
        if (!can('6.9')) return resolve(local);
        tg.CloudStorage.getItem(key, (err, val) => resolve(err || !val ? local : val));
      });
    },

    setItem(key, val) {
      val = String(val);
      localSet(key, val);
      if (can('6.9')) tg.CloudStorage.setItem(key, val, () => {});
    },

    share(text) {
      const url = (window.GAME_CONFIG && window.GAME_CONFIG.shareUrl) || location.href;
      if (inTelegram) {
        tg.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(url) +
          '&text=' + encodeURIComponent(text));
      } else if (navigator.share) {
        navigator.share({ text, url }).catch(() => {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(text + ' ' + url).then(() => alert('Скопировано!'), () => {});
      }
    },
  };
})();
