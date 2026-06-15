/* PI Tracker — shared utilities.
 * Idempotent: wrapped in an IIFE with a load guard and exported via window.*
 * (not top-level `function` declarations), so evaluating this file more than
 * once — e.g. via bfcache, a browser extension, or a duplicate include — can
 * never throw "Identifier has already been declared".
 */
(function () {
  "use strict";
  if (window.piTrackerUtilsLoaded) return;
  window.piTrackerUtilsLoaded = true;

  window.piCsrf = function () {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
  };

  /* Parse a JSON response; on a non-JSON error body (e.g. a 500 HTML page)
   * resolve to {ok:false} instead of throwing, so callers' `data.ok` checks
   * keep working and the error is never silently swallowed. */
  function parseJsonResponse(r) {
    return r.json().catch(function () {
      return { ok: false, error: "HTTP " + r.status };
    });
  }

  /* FormData POST — für Django-Views die request.POST nutzen */
  window.piPost = function (url, data) {
    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", window.piCsrf());
    for (const [k, v] of Object.entries(data || {})) fd.append(k, v);
    return fetch(url, { method: "POST", body: fd }).then(parseJsonResponse);
  };

  /* JSON POST — für Views die json.loads(request.body) nutzen */
  window.piPostJson = function (url, data) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.piCsrf() },
      body: JSON.stringify(data || {}),
    }).then(parseJsonResponse);
  };

  /* Wire up a "Sync" header button: spinner → POST → "Queued" → reset.
   * opts: { id?, url, busy, done, title?, wait?, reload? }. The resting label is
   * captured from the button's current HTML, so each page keeps its own wording. */
  window.bindSyncButton = function (opts) {
    const btn = document.getElementById(opts.id || "btn-sync");
    if (!btn) return;
    const idle = btn.innerHTML;
    const wait = opts.wait || 5000;
    btn.addEventListener("click", function () {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-sync fa-spin"></i> ' + opts.busy;
      window.piPost(opts.url, {}).then(function (r) {
        if (r && r.ok === false) {
          btn.disabled = false;
          btn.innerHTML = idle;
          return;
        }
        btn.innerHTML = '<i class="fas fa-check"></i> ' + opts.done;
        if (opts.title) btn.title = opts.title;
        setTimeout(function () {
          btn.disabled = false;
          btn.innerHTML = idle;
          if (opts.title) btn.title = "";
          if (opts.reload) location.reload();
        }, wait);
      });
    });
  };

  window.fmtIsk = function (v) {
    if (!isFinite(v)) return "—";
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B ISK";
    if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M ISK";
    if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K ISK";
    return v.toFixed(0) + " ISK";
  };
})();
