<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atlas Report Copilot</title>
<style>
  :root { --bg:#f4f6fb; --card:#ffffff; --ink:#18212f; --muted:#6b7686; --line:#e3e8f0; --brand:#2f5bea; --brand2:#5b7cff; --warn:#b54708; --ok:#067647; --shadow:0 1px 2px rgba(16,24,40,.06), 0 4px 14px rgba(16,24,40,.05); }
  @media (prefers-color-scheme: dark) { :root { --bg:#0e131b; --card:#171e29; --ink:#e8ecf3; --muted:#9aa5b5; --line:#263041; --brand:#6e93ff; --brand2:#8fb0ff; --warn:#f79009; --ok:#47cd89; --shadow:0 1px 2px rgba(0,0,0,.4), 0 4px 14px rgba(0,0,0,.25); } }
  * { box-sizing:border-box; }
  html, body { overflow-x:hidden; }
  body { margin:0; background:radial-gradient(1200px 500px at 50% -200px, rgba(91,124,255,.14), transparent), var(--bg); color:var(--ink); font:15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:860px; margin:0 auto; padding:18px 16px 0; display:flex; flex-direction:column; min-height:100vh; }
  .top { display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
  .brand { display:flex; align-items:center; gap:10px; }
  .logo { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; color:#fff; font-weight:700; background:linear-gradient(135deg, var(--brand), var(--brand2)); box-shadow:var(--shadow); }
  h1 { font-size:18px; margin:0; line-height:1.2; }
  .sub { color:var(--muted); font-size:13px; }
  a { color:var(--brand); text-decoration:none; font-weight:500; }
  a:hover { text-decoration:underline; }
  .bar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:14px; padding:8px 10px; background:var(--card); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); }
  .bar label { color:var(--muted); font-size:13px; }
  select, input, button { font:inherit; padding:8px 12px; border:1px solid var(--line); border-radius:10px; background:var(--card); color:var(--ink); }
  input:focus, select:focus { outline:2px solid var(--brand); outline-offset:1px; }
  button { cursor:pointer; background:linear-gradient(135deg, var(--brand), var(--brand2)); color:#fff; border:0; font-weight:600; }
  button:hover { filter:brightness(1.06); }
  button:disabled { opacity:.55; cursor:default; }
  button.ghost { background:var(--card); color:var(--ink); border:1px solid var(--line); font-weight:500; }
  #log { flex:1; display:flex; flex-direction:column; gap:12px; padding-bottom:14px; }
  .msg { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:12px 16px; white-space:pre-wrap; overflow-wrap:anywhere; box-shadow:var(--shadow); }
  .user { align-self:flex-end; background:linear-gradient(135deg, var(--brand), var(--brand2)); color:#fff; border:0; max-width:78%; border-bottom-right-radius:5px; }
  .msg.bot { white-space:normal; max-width:94%; border-bottom-left-radius:5px; }
  .msg.bot p { margin:0 0 8px; }
  .msg.bot ul { margin:4px 0 10px; padding-left:20px; }
  .msg.bot li { margin:4px 0; }
  .msg.bot li .sub { color:var(--muted); font-size:13px; margin-top:2px; }
  .msg.bot p.code { font:13px/1.5 ui-monospace, monospace; background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:8px 12px; overflow-x:auto; white-space:pre-wrap; }
  .msg.bot strong { color:var(--brand); }
  .thinking { color:var(--muted); font-style:italic; }
  .thinking::after { content:""; display:inline-block; width:1.2em; animation:dots 1.2s steps(4, end) infinite; overflow:hidden; vertical-align:bottom; }
  @keyframes dots { 0% { content:""; } 25% { content:"."; } 50% { content:".."; } 75% { content:"..."; } 100% { content:"..."; } }
  .meta { font-size:12.5px; color:var(--muted); margin-top:10px; white-space:normal; }
  .tag { display:inline-block; padding:2px 10px; border-radius:99px; border:1px solid var(--line); margin:0 6px 4px 0; background:var(--bg); }
  .tag.esc { color:var(--warn); border-color:var(--warn); }
  .tag.ok { color:var(--ok); border-color:var(--ok); }
  details { margin-top:8px; }
  summary { cursor:pointer; color:var(--brand); font-size:13px; }
  details .meta { border-left:3px solid var(--brand); background:var(--bg); border-radius:0 10px 10px 0; padding:6px 10px; margin-top:6px; }
  .starters { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 12px; }
  .starters button { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:99px; font-size:13px; font-weight:500; padding:7px 14px; box-shadow:var(--shadow); }
  .starters button:hover { border-color:var(--brand); color:var(--brand); }
  #form { display:flex; gap:8px; position:sticky; bottom:0; background:linear-gradient(to top, var(--bg) 70%, transparent); padding:10px 0 16px; }
  #form input { flex:1; padding:12px 16px; border-radius:14px; box-shadow:var(--shadow); }
  #form button { padding:0 22px; border-radius:14px; }
</style>
</head>
<body>
<main>
  <div class="top"><div class="brand"><div class="logo">A</div><div><h1>Atlas Report Copilot</h1><div class="sub">Answers from your market research reports, with sources</div></div></div></div>
  <form class="bar" method="post" action="<?php echo html_escape(site_url('chat/switch_client')); ?>">
    <input type="hidden" name="<?php echo html_escape($csrfName); ?>" value="<?php echo html_escape($csrfHash); ?>">
    <label for="client">Signed in as</label>
    <select id="client" name="client_id" onchange="this.form.submit()">
      <?php foreach ($clients as $id => $name): ?>
        <option value="<?php echo html_escape($id); ?>"<?php echo $id === $current ? ' selected' : ''; ?>><?php echo html_escape($name.' ('.$id.')'); ?></option>
      <?php endforeach; ?>
    </select>
    <noscript><button type="submit">Switch</button></noscript>
  </form>
  <div id="log" aria-live="polite"></div>
  <div class="starters" id="starters"></div>
  <form class="ask" id="form">
    <input id="text" maxlength="<?php echo (int) $maxMessage; ?>" placeholder="Ask about your market research reports" autocomplete="off" required>
    <button id="send">Send</button>
  </form>
</main>
<script>
const CSRF = { name: <?php echo json_encode($csrfName); ?>, hash: <?php echo json_encode($csrfHash); ?> };
const SEND_URL = <?php echo json_encode(site_url('chat/send')); ?>;
const FEEDBACK_URL = <?php echo json_encode(site_url('chat/feedback')); ?>;
const log = document.getElementById("log");

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function post(url, fields) {
  const body = new URLSearchParams({ ...fields, [CSRF.name]: CSRF.hash });
  return fetch(url, { method: "POST", body, credentials: "same-origin" });
}

function scrollDown() { window.scrollTo(0, document.body.scrollHeight); }

function decorate(parent, text) {
  const re = /(USD [\d.,]+ B|\b\d[\d.,]*%)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    parent.append(el("strong", "", m[0]));
    last = m.index + m[0].length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

function renderAnswer(text) {
  const wrap = el("div", "answer");
  let list = null, item = null;
  text.split("\n").forEach((line) => {
    if (/^\s*-\s+/.test(line)) {
      if (!list) { list = el("ul"); wrap.append(list); }
      item = el("li");
      decorate(item, line.replace(/^\s*-\s+/, ""));
      list.append(item);
    } else if (/^\s{2,}\S/.test(line) && item) {
      const sub = el("div", "sub");
      decorate(sub, line.trim());
      item.append(sub);
    } else if (line.trim()) {
      list = null; item = null;
      const p = el("p", line.startsWith("Query used:") ? "code" : "");
      decorate(p, line.trim());
      wrap.append(p);
    } else { list = null; item = null; }
  });
  return wrap;
}

function showThinking() {
  const box = el("div", "msg bot thinking", "Thinking...");
  log.append(box);
  scrollDown();
  return box;
}

const STARTERS = [
  "What was the global smart water meter market size in 2024?",
  "What will the APAC smart water meter market be worth in 2030?",
  "Which report should I trust?",
  "Which sector has the most reports in your library?",
];
STARTERS.forEach((q) => {
  const b = el("button", "", q);
  b.type = "button";
  b.onclick = () => {
    document.getElementById("text").value = q;
    document.getElementById("form").dispatchEvent(new Event("submit", { cancelable: true }));
  };
  document.getElementById("starters").append(b);
});

function addBot(data) {
  const box = el("div", "msg bot");
  box.append(renderAnswer(data.answer));
  const meta = el("div", "meta");
  meta.append(el("span", "tag", "confidence " + Number(data.confidence).toFixed(2)), el("span", "tag", data.intent));
  const source = data.cached ? "cached answer" : data.llm_used ? "written by LLM (" + data.tokens_in + " in, " + data.tokens_out + " out tokens)" : "rule-based, no LLM used";
  meta.append(el("span", data.llm_used ? "tag ok" : "tag", source));
  if (data.escalated) meta.append(el("span", "tag esc", "escalated #" + data.escalation_id));
  (data.flags || []).forEach(f => meta.append(el("span", "tag esc", f)));
  if ((data.derived_values || []).length) meta.append(el("span", "tag", "derived estimate"));
  if ((data.conflicts || []).length) meta.append(el("span", "tag esc", "sources disagree"));
  box.append(meta);
  if ((data.citations || []).length) {
    const d = el("details");
    d.append(el("summary", "", data.citations.length + " citation(s)"));
    data.citations.forEach(c => d.append(el("div", "meta", (c.report_id || "SQL") + (c.page ? " p." + c.page : "") + " - " + c.snippet)));
    box.append(d);
  }
  const fb = el("div", "meta");
  [["up", "Helpful"], ["down", "Not helpful"]].forEach(([rating, label]) => {
    const b = el("button", "ghost", label);
    b.type = "button";
    b.onclick = async () => {
      try {
        const r = await post(FEEDBACK_URL, { message_id: data.message_id, rating });
        fb.textContent = r.ok ? "Thanks for the feedback" : "Could not save feedback";
      } catch (e) { fb.textContent = "Could not save feedback"; }
    };
    fb.append(b, " ");
  });
  box.append(fb);
  log.append(box);
  scrollDown();
}

document.getElementById("form").onsubmit = async (event) => {
  event.preventDefault();
  const input = document.getElementById("text");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  document.getElementById("starters").hidden = true;
  log.append(el("div", "msg user", message));
  scrollDown();
  const pending = showThinking();
  const send = document.getElementById("send");
  send.disabled = true;
  try {
    const resp = await post(SEND_URL, { message });
    let body = {};
    try { body = await resp.json(); } catch (e) {}
    if (resp.ok && body.data) addBot(body.data);
    else log.append(el("div", "msg bot", body.message || "Your session expired or the request was rejected. Please reload the page."));
  } catch (err) {
    log.append(el("div", "msg bot", "The service is unreachable right now. Please try again shortly."));
  } finally {
    pending.remove();
    send.disabled = false;
    scrollDown();
  }
};
</script>
</body>
</html>
