// VTU Exam Radar - student page. Talks to Radar Desk (/api/*).
const $ = id => document.getElementById(id);
const make = (tag, cls, text) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
};
let shown = 0;
let timer;

async function loadSubjects() {
  const res = await fetch("/api/subjects");
  const list = await res.json();
  for (const s of list) {
    const o = make("option", "", s.name === s.code ? s.code : `${s.name} (${s.code})`);
    o.value = s.code;
    $("code").append(o);
  }
  const d = new Date(); d.setDate(d.getDate() + 5);
  $("exam_date").value = d.toISOString().slice(0, 10);
  $("exam_date").min = new Date().toISOString().slice(0, 10);
}

$("hours").addEventListener("input", e => { $("hours-out").textContent = e.target.value; });

$("plan-form").addEventListener("submit", async e => {
  e.preventDefault();
  $("form-error").hidden = true;
  $("go").disabled = true;
  $("go").textContent = "Sending to the agents...";
  const body = {
    code: $("code").value,
    exam_date: $("exam_date").value,
    hours: parseFloat($("hours").value),
    weak_modules: [...document.querySelectorAll(".chips input:checked")].map(c => parseInt(c.value, 10)),
  };
  try {
    const res = await fetch("/api/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong");
    $("form-card").hidden = true;
    $("live-card").hidden = false;
    $("log").innerHTML = ""; shown = 0;
    $("pulse").classList.remove("done");
    poll(data.id);
  } catch (err) {
    $("form-error").textContent = err.message;
    $("form-error").hidden = false;
  } finally {
    $("go").disabled = false;
    $("go").textContent = "Make my plan";
  }
});

async function poll(id) {
  clearTimeout(timer);
  const res = await fetch(`/api/plan/${id}`, { cache: "no-store" });
  const r = await res.json();
  const events = r.events || [];
  for (; shown < events.length; shown++) {
    const m = events[shown];
    const li = make("li");
    li.append(make("span", "who", `${m.from} → ${m.to}`), make("span", "", m.message));
    $("log").append(li);
  }
  if (r.status === "done" && r.plan) {
    $("pulse").classList.add("done");
    render(r.plan, r);
    return;
  }
  if (r.status === "error") {
    $("log").append(make("li", "error", r.error || "Something went wrong."));
    $("pulse").classList.add("done");
    return;
  }
  timer = setTimeout(() => poll(id), 2000);
}

function render(p, req) {
  $("result").hidden = false;
  $("r-code").textContent = p.code;
  $("r-subject").textContent = p.subject_name;
  $("r-meta").textContent = `Exam on ${req.exam_date} · ${req.hours}h/day` +
    (req.weak_modules.length ? ` · weak: Module ${req.weak_modules.join(", ")}` : "");
  $("r-days").textContent = p.study_plan.length;
  $("r-repeats").textContent = p.repeated_questions.filter(q => q.times > 1).length;
  $("r-papers").textContent = p.papers.length;
  $("r-plan-hint").textContent = req.weak_modules.length
    ? "Your weak modules are scheduled early, while you are fresh. The last day is revision."
    : "Highest-value topics first; the last day is revision.";

  $("r-plan").innerHTML = "";
  for (const d of p.study_plan) {
    const box = make("div", "day");
    box.append(make("h4", "", `Day ${d.day}`), make("p", "", d.focus));
    const ul = make("ul");
    for (const t of d.tasks || []) ul.append(make("li", "", t));
    box.append(ul);
    $("r-plan").append(box);
  }

  $("r-repeats-list").innerHTML = "";
  for (const q of p.repeated_questions) {
    const det = make("details");
    const sum = make("summary");
    sum.append(make("span", q.times >= 3 ? "badge hot" : "badge", `asked ${q.times}×`));
    sum.append(make("span", req.weak_modules.includes(q.module) ? "badge weak" : "badge", `Module ${q.module}`));
    sum.append(document.createTextNode(q.question));
    det.append(sum);
    det.append(make("div", "answer", q.answer || "Model answer coming soon."));
    $("r-repeats-list").append(det);
  }

  $("r-live").innerHTML = ""; $("r-sources").innerHTML = "";
  for (const n of (p.live && p.live.notes) || []) $("r-live").append(make("li", "", n));
  ((p.live && p.live.sources) || []).forEach((s, i) => {
    if (i) $("r-sources").append(" · ");
    const a = make("a", "", s.title || "source");
    a.href = s.url; a.target = "_blank"; a.rel = "noopener";
    $("r-sources").append(a);
  });
  $("result").scrollIntoView({ behavior: "smooth" });
}

$("again").addEventListener("click", () => {
  $("result").hidden = true; $("live-card").hidden = true; $("form-card").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
});

loadSubjects();
