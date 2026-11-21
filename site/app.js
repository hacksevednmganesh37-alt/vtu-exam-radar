// Reads site/data/subjects.json and site/data/<CODE>.json (written by Radar Builder).
const app = document.getElementById("app");
const picker = document.getElementById("subject");
let chart;

const text = (el, value) => { el.textContent = value; return el; };
const make = (tag, cls, value) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (value !== undefined) el.textContent = value;
  return el;
};

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

async function start() {
  let subjects = [];
  try { subjects = await getJSON("data/subjects.json"); } catch { /* no subjects yet */ }
  if (!subjects.length) subjects = [{ code: "SAMPLE", name: "Sample subject (demo data)" }];

  for (const s of subjects) {
    const opt = make("option", "", `${s.code} — ${s.name}`);
    opt.value = s.code;
    picker.append(opt);
  }
  const wanted = new URLSearchParams(location.search).get("subject");
  if (wanted && subjects.some(s => s.code === wanted.toUpperCase())) picker.value = wanted.toUpperCase();

  picker.addEventListener("change", () => {
    history.replaceState(null, "", `?subject=${picker.value}`);
    load(picker.value);
  });
  load(picker.value);
}

async function load(code) {
  app.innerHTML = '<p class="loading">Loading…</p>';
  try {
    render(await getJSON(`data/${code}.json`));
  } catch (err) {
    app.innerHTML = "";
    app.append(make("p", "error", `Could not load ${code}: ${err.message}`));
  }
}

function render(r) {
  const view = document.getElementById("report-tpl").content.cloneNode(true);
  const $ = sel => view.querySelector(sel);

  $(".sample-banner").hidden = !r.sample;
  text($(".code"), r.code);
  text($(".subject"), r.subject_name);
  const when = r.generated_at ? new Date(r.generated_at).toLocaleString("en-IN") : "";
  text($(".meta"), `Papers: ${r.papers.join(" · ")}${when ? " · updated " + when : ""}`);

  const top = [...r.modules].sort((a, b) => b.share - a.share)[0];
  text($(".s-papers"), r.papers.length);
  text($(".s-repeats"), r.repeated_questions.filter(q => q.times > 1).length);
  text($(".s-top"), top ? `M${top.number}` : "–");

  // live notes
  const live = r.live || {};
  for (const n of live.notes || []) $(".live").append(make("li", "", n));
  if (!(live.notes || []).length) $(".live").append(make("li", "", "No live notes yet."));
  const srcs = $(".sources");
  (live.sources || []).forEach((s, i) => {
    if (i) srcs.append(" · ");
    const a = make("a", "", s.title || "source");
    a.href = s.url; a.target = "_blank"; a.rel = "noopener";
    srcs.append(a);
  });

  // repeated questions
  for (const q of r.repeated_questions) {
    const li = make("li");
    li.append(make("span", q.times >= 3 ? "badge hot" : "badge", `asked ${q.times}×`));
    li.append(make("span", "badge", `Module ${q.module}`));
    if (q.avg_marks) li.append(make("span", "badge", `~${q.avg_marks} marks`));
    li.append(make("div", "", q.question));
    li.append(make("span", "exams", q.exams.join(" · ")));
    $(".repeats").append(li);
  }

  // study plan
  for (const d of r.study_plan) {
    const box = make("div", "day");
    box.append(make("h4", "", `Day ${d.day}`));
    box.append(make("p", "", d.focus));
    const ul = make("ul");
    for (const t of d.tasks || []) ul.append(make("li", "", t));
    box.append(ul);
    $(".plan").append(box);
  }

  // web questions
  if ((r.web_questions || []).length) {
    $(".web-card").hidden = false;
    for (const q of r.web_questions) $(".web").append(make("li", "", `Module ${q.module}: ${q.text}`));
  }

  // agent log
  for (const m of r.agent_log || []) {
    const li = make("li");
    li.append(make("span", "who", `${m.from} → ${m.to}`));
    li.append(make("span", "", m.message));
    $(".log").append(li);
  }

  app.innerHTML = "";
  app.append(view);
  drawChart(r.modules);
}

function drawChart(modules) {
  if (chart) chart.destroy();
  const ctx = document.getElementById("modules-chart");
  if (!window.Chart || !ctx) return;
  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: modules.map(m => `M${m.number}${m.title ? " · " + m.title : ""}`),
      datasets: [{
        data: modules.map(m => Math.round(m.share * 100)),
        backgroundColor: "#f5b942",
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => `${c.raw}% of marks · ${modules[c.dataIndex].question_count} questions` } },
      },
      scales: {
        x: { ticks: { color: "#a3a1bd", callback: v => v + "%" }, grid: { color: "#2a2d4a" } },
        y: { ticks: { color: "#eceaf6" }, grid: { display: false } },
      },
    },
  });
}

start();
