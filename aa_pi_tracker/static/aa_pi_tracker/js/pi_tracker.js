/* PI Tracker — shared utilities */

function piCsrf() {
  return document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
}

/* FormData POST — für Django-Views die request.POST nutzen */
function fetchPost(url, data) {
  const fd = new FormData();
  fd.append("csrfmiddlewaretoken", piCsrf());
  for (const [k, v] of Object.entries(data || {})) fd.append(k, v);
  return fetch(url, { method: "POST", body: fd }).then(r => r.json());
}

/* JSON POST — für Views die json.loads(request.body) nutzen */
function fetchPostJson(url, data) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": piCsrf() },
    body: JSON.stringify(data || {}),
  }).then(r => r.json());
}

function fmtIsk(v) {
  if (!isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B ISK";
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M ISK";
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K ISK";
  return v.toFixed(0) + " ISK";
}
