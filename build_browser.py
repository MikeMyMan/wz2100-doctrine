#!/usr/bin/env python3
"""Emit a self-contained tech tree browser from the generated data."""
import json, os

M = json.load(open("/home/claude/wz-doctrine/out/meta.json"))
KV = json.load(open("/home/claude/wz-doctrine/out/killvalue.json"))
VAN = json.load(open(os.environ.get("WZ_ROOT", "/tmp/wz2100") + "/data/mp/stats/research.json"))

topics, meta, cfg = M["topics"], M["meta"], M["config"]
fams, inv, sigs = M["families"], M["inventory"], M["signatures"]

van_pts = sum(v["researchPoints"] for v in VAN.values())
van_pure = sum(1 for v in VAN.values()
               if "results" in v and not (v.get("resultComponents") or v.get("resultStructures")))
van_pure_pts = sum(v["researchPoints"] for v in VAN.values()
                   if "results" in v and not (v.get("resultComponents") or v.get("resultStructures")))

payload = {
    "topics": topics, "meta": meta, "config": cfg,
    "families": fams, "inventory": inv, "signatures": sigs,
    "vanilla": {"topics": len(VAN), "points": van_pts,
                "pureUpgrades": van_pure, "pureUpgradePoints": van_pure_pts},
    # relative gain per tier: vanilla additive-on-base decay vs the ratchet's constant
    "ladders": {
        "vanilla": [round(25 / (100 + 25 * (n - 1)) * 100, 1) for n in range(1, 10)],
        "doctrine": [25.0] * 4,
    },
    "killvalue": KV,
    "crosslinks": None,  # filled below
    "surplus": M.get("surplus", []),
    "axes": [
        {"key": "Damage",   "label": "Warhead",       "params": "Damage · RadiusDamage"},
        {"key": "Range",    "label": "Fire Control",  "params": "MaxRange · ShortRange"},
        {"key": "Reload",   "label": "Loading Drill", "params": "FirePause · ReloadTime"},
        {"key": "Accuracy", "label": "Gunnery",       "params": "HitChance · ShortHitChance"},
    ],
}

import re
_famof = {t: meta[t].get("family") for t in meta if meta[t].get("kind") == "weapon"}
_cross = []
for tid, m in meta.items():
    if m.get("kind") != "weapon":
        continue
    dst = m.get("family")
    for d in topics[tid].get("requiredResearch", []):
        src = None
        mm = re.match(r"^R-Wpn-([A-Za-z]+)-(?:Damage|Range|Reload|Accuracy)\d+$", d)
        if mm and mm.group(1) in fams:
            src = mm.group(1)                 # gated on another family's ratchet
        elif d in _famof:
            src = _famof[d]                   # gated on another family's GUN
        if src and dst and src != dst:
            _cross.append([src, tid])
payload["crosslinks"] = _cross

HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DOCTRINE — Warzone 2100 tech tree</title>
<style>
:root{
  color-scheme:light;
  --surface-0:#f6f5f2; --surface-1:#fcfcfb; --surface-2:#eeede9;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#76746e;
  --rule:#dedcd6; --rule-strong:#c4c1b8;
  --t1:#86b6ef; --t2:#5598e7; --t3:#2a78d6; --t4:#184f95;
  --t1-ink:#0b0b0b; --t2-ink:#ffffff; --t3-ink:#ffffff; --t4-ink:#ffffff;
  --k-spine:#1baf7a; --k-infrastructure:#eda100; --k-signature:#e87ba4;
  --k-penetration:#4a3aa7; --k-credential:#76746e; --k-chassis:#4a3aa7;
  --k-ratchet:#2a78d6;
  --gate:#eeede9; --gate-ink:#52514e;
}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){
  color-scheme:dark;
  --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#242422;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#96948a;
  --rule:#33332f; --rule-strong:#4a4a45;
  --t1:#9ec5f4; --t2:#6da7ec; --t3:#3987e5; --t4:#184f95;
  --t1-ink:#0b0b0b; --t2-ink:#0b0b0b; --t3-ink:#ffffff; --t4-ink:#ffffff;
  --k-spine:#199e70; --k-infrastructure:#c98500; --k-signature:#d55181;
  --k-penetration:#9085e9; --k-credential:#96948a; --k-chassis:#9085e9;
  --k-ratchet:#3987e5;
  --gate:#242422; --gate-ink:#c3c2b7;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#242422;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#96948a;
  --rule:#33332f; --rule-strong:#4a4a45;
  --t1:#9ec5f4; --t2:#6da7ec; --t3:#3987e5; --t4:#184f95;
  --t1-ink:#0b0b0b; --t2-ink:#0b0b0b; --t3-ink:#ffffff; --t4-ink:#ffffff;
  --k-spine:#199e70; --k-infrastructure:#c98500; --k-signature:#d55181;
  --k-penetration:#9085e9; --k-credential:#96948a; --k-chassis:#9085e9;
  --k-ratchet:#3987e5;
  --gate:#242422; --gate-ink:#c3c2b7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface-0);color:var(--text-primary);
 font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:30px 22px 80px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:22px;flex-wrap:wrap}
h1{font-size:27px;margin:0 0 4px;letter-spacing:-.022em;font-weight:650}
.sub{color:var(--text-secondary);max-width:64ch;margin:0}
h2{font-size:19px;margin:46px 0 4px;letter-spacing:-.01em;font-weight:640}
h2+.lede{color:var(--text-secondary);margin:0 0 18px;max-width:76ch;font-size:14px}
button{font:inherit;cursor:pointer}
.toggle{background:var(--surface-1);border:1px solid var(--rule-strong);color:var(--text-secondary);
 border-radius:7px;padding:6px 11px;font-size:13px}
.toggle:hover{border-color:var(--text-muted);color:var(--text-primary)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(166px,1fr));gap:12px;margin:26px 0 6px}
.tile{background:var(--surface-1);border:1px solid var(--rule);border-radius:11px;padding:15px 16px}
.tile .n{font-size:28px;font-weight:660;letter-spacing:-.025em;line-height:1.1;font-variant-numeric:tabular-nums}
.tile .l{font-size:12.5px;color:var(--text-secondary);margin-top:3px}
.tile .d{font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.4}
.panel{background:var(--surface-1);border:1px solid var(--rule);border-radius:12px;padding:20px}
.legend{display:flex;gap:15px;flex-wrap:wrap;font-size:12.5px;color:var(--text-secondary);
 margin-bottom:12px;align-items:center}
.legend i{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:-1px}
.filters{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:0 0 16px}
.pill{background:var(--surface-1);border:1px solid var(--rule-strong);color:var(--text-secondary);
 border-radius:999px;padding:5px 13px;font-size:13px}
.pill[aria-pressed=true]{background:var(--text-primary);color:var(--surface-1);
 border-color:var(--text-primary);font-weight:560}
/* ── the ratchet grid ── */
.gridwrap{overflow-x:auto}
.grid{display:grid;grid-template-columns:150px repeat(7,minmax(0,1fr));gap:8px;min-width:880px;align-items:stretch}
.ghead{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);
 font-weight:620;padding:0 0 4px;align-self:end}
.axlab{display:flex;flex-direction:column;justify-content:center;padding-right:8px}
.axlab .a{font-size:13.5px;font-weight:620;line-height:1.25}
.axlab .p{font-size:11px;color:var(--text-muted);font-family:ui-monospace,Menlo,monospace;margin-top:3px}
.cell{border-radius:9px;padding:10px 11px;background:var(--c);color:var(--ink);min-height:74px;
 display:flex;flex-direction:column;justify-content:space-between}
.cell .nm{font-size:12.5px;font-weight:600;line-height:1.3}
.cell .v{font-size:11.5px;opacity:.88;margin-top:5px;font-variant-numeric:tabular-nums}
.gate{background:var(--gate);border:1px dashed var(--rule-strong);border-radius:9px;
 display:flex;align-items:center;justify-content:center;padding:6px 3px}
.gate span{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10.5px;letter-spacing:.08em;
 text-transform:uppercase;color:var(--gate-ink);font-weight:620;text-align:center;line-height:1.3}
.gaterow{grid-column:1/-1;font-size:12px;color:var(--text-secondary);margin:2px 0 0;
 border-left:2px solid var(--rule-strong);padding-left:11px}
/* ── chain ── */
.chain{display:flex;flex-wrap:wrap;gap:24px 0;padding-bottom:6px}
.step{flex:0 0 auto;width:172px;background:var(--surface-1);border:1px solid var(--rule);
 border-left:3px solid var(--k-spine);border-radius:9px;padding:11px 12px;position:relative}
.step:not(:first-child){margin-left:24px}
.step:not(:first-child)::before{content:"";position:absolute;left:-24px;top:50%;width:24px;height:2px;background:var(--rule-strong)}
.step:not(:first-child)::after{content:"";position:absolute;left:-9px;top:50%;width:0;height:0;transform:translateY(-50%);
 border-left:6px solid var(--rule-strong);border-top:4.5px solid transparent;border-bottom:4.5px solid transparent}
.step.wrapstart{margin-left:0}
.step.wrapstart::before,.step.wrapstart::after{display:none}
.step .nm{font-size:13px;font-weight:600;line-height:1.3}
.step .cost{font-size:11.5px;color:var(--text-muted);margin-top:4px;font-variant-numeric:tabular-nums}
.step .nt{font-size:11.5px;color:var(--text-secondary);margin-top:7px;line-height:1.4}
.step.key{border-left-color:var(--k-ratchet);box-shadow:0 0 0 1px var(--k-ratchet) inset}
/* ── generic node lists ── */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.node{background:var(--surface-1);border:1px solid var(--rule);border-left:3px solid var(--c);
 border-radius:8px;padding:10px 12px}
.node .nm{font-size:13px;font-weight:570;line-height:1.3}
.node .mt{font-size:11.5px;color:var(--text-muted);margin-top:4px;font-variant-numeric:tabular-nums}
.node .nt{font-size:11.5px;color:var(--text-secondary);margin-top:6px;line-height:1.4}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule)}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);font-weight:620}
td.num{text-align:right;font-variant-numeric:tabular-nums}
#tableView[hidden]{display:none}
.lnode rect{stroke:var(--rule-strong);stroke-width:1}
.lnode text{font:12px ui-sans-serif,system-ui,sans-serif}
.chartwrap{position:relative}
svg{display:block;width:100%;height:auto;overflow:visible}
.tip{position:absolute;pointer-events:none;background:var(--surface-1);border:1px solid var(--rule-strong);
 border-radius:8px;padding:8px 11px;font-size:12.5px;box-shadow:0 4px 16px rgba(0,0,0,.13);
 opacity:0;transition:opacity .1s;white-space:nowrap;z-index:5}
.note{font-size:12.5px;color:var(--text-secondary);margin-top:12px;line-height:1.5;
 border-left:2px solid var(--rule-strong);padding-left:12px}
code{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--surface-2);padding:1px 5px;border-radius:4px}
</style></head><body>
<div class="wrap">
<header>
 <div><h1>DOCTRINE</h1>
 <p class="sub">A generated tech tree for Warzone&nbsp;2100. Combat <em>unlocks</em> a topic;
 power <em>researches</em> it. Neither alone advances you.</p></div>
 <button class="toggle" id="themeBtn" type="button">Dark mode</button>
</header>

<div class="tiles" id="tiles"></div>

<h2>The ratchet</h2>
<p class="lede">Every weapon family has four axes and four tiers. Fighting reveals one random
eligible cell at a time. A tier only becomes eligible once <strong>every axis of the tier below it
has been researched</strong> — not merely unlocked. The dashed bars are those gates: you cannot cross
one until all four cells to its left are paid for.</p>
<div class="filters" id="famPills"></div>
<div class="panel gridwrap"><div class="grid" id="ratchet"></div></div>

<h2>Weapon lineage</h2>
<p class="lede">The guns themselves, and what each one costs you. Vanilla already encodes this
succession and it is the best part of the existing tree — it just gated it on lab time. Under
DOCTRINE the same prerequisites mean <em>you must have fought with this family</em>, because that
is what unlocks a tier. You don't get the Heavy Machinegun from a lab; you get it because your MG
crews reported what they needed.</p>
<div class="panel">
 <div class="legend" id="linLegend"></div>
 <div class="gridwrap"><div id="lineage"></div></div>
 <p class="note" id="linNote"></p>
</div>

<h2>How the families feed each other</h2>
<p class="lede">Weapon lines are not islands — the vanilla tree already crosses them, and those
crossings are the most interesting edges in the whole graph. Machineguns open the cannon line.
Cannons plus flamers make the Plasma Cannon. Rockets become anti-air. Each arrow is a real
prerequisite in the generated data.</p>
<div class="panel"><div class="gridwrap"><div id="cross"></div></div></div>

<h2>What a kill is worth</h2>
<p class="lede">Knowledge is weighted by what you actually killed, <em>relative to your own army</em>.
Kill something far beneath you and you learn nothing — that is the anti-farming rule. Kill something
above your weight and you learn disproportionately. Because the reference is your own 75th-percentile
unit cost, it self-scales: the Viper that was a fair fight at minute five is worth zero by minute forty,
with nothing to retune.</p>
<div class="panel chartwrap">
 <div id="kvChart"></div><div class="tip" id="kvTip"></div>
 <div class="filters" style="margin:18px 0 12px" id="kvPills"></div>
 <table id="kvTable"></table>
 <p class="note">Value metric is <code>droid.cost</code> — <code>calcDroidPower</code>, the summed
 component build cost. A Dragon/Gauss/Tracks costs 602; a scavenger trike costs 38. That ratio
 <em>is</em> the tech gap, so no separate "tech level" needs inventing.</p>
</div>

<h2>The fix, in one picture</h2>
<p class="lede">The engine applies upgrades <em>additively on the base value</em>, so a constant
<code>value</code> means a shrinking relative gain — vanilla's ninth cannon step delivers a third of
the first step's effect while costing twelve times as much. DOCTRINE solves for values that hold the
relative gain constant, so every tier feels like the one before it.</p>
<div class="panel chartwrap">
 <div class="legend" id="ladderLegend"></div>
 <div id="ladderChart"></div><div class="tip" id="ladderTip"></div>
 <p class="note">Vanilla runs nine tiers to reach +225% damage. DOCTRINE runs four to reach +144%,
 then spends the rest of the progression on range, rate of fire and accuracy — axes vanilla either
 barely touches or never touches at all.</p>
</div>

<h2>The spine — the technologies that lead to this</h2>
<p class="lede">The critical path. Everything depends on it, so it is early, cheap and the obvious
first thing you do. Vanilla gives the Command Turret two topics out of 390; here it gets eight and
becomes the backbone.</p>
<div class="chain" id="spine"></div>

<h2>Beyond the ratchet</h2>
<p class="lede">Signature topics apply to <em>one specific weapon</em> and stay invisible until you
master it. Penetration raises the guaranteed-damage floor for one family, so rock-paper-scissors
gets <em>sharper</em> as the game goes on. Infrastructure is gated on breadth — competence across
several families, not depth in one.</p>
<div class="filters" id="kindPills"></div>
<div class="cards" id="others"></div>

<h2>Every topic</h2>
<p class="lede">All <span id="tcount"></span> generated topics. Validated acyclic, zero dangling
prerequisites, every class/parameter pair checked against the engine's
<code>getUpgradesObject()</code>.</p>
<div class="filters"><button class="toggle" id="tableBtn" type="button" aria-expanded="false">Show table</button></div>
<div class="panel" id="tableView" hidden><table id="topicTable"></table></div>
</div>

<script>
const DATA = __PAYLOAD__;
const T = DATA.topics, MT = DATA.meta, V = DATA.vanilla, AXES = DATA.axes;
const KLABEL = {ratchet:"Ratchet",signature:"Signature (one weapon)",penetration:"Penetration",
 spine:"Command spine",infrastructure:"Infrastructure",credential:"Credential",chassis:"Chassis handling"};
const fmt = n => n.toLocaleString("en-US");
const kc = k => `var(--k-${k})`;

/* ── tiles ─────────────────────────────────────────────────────────────── */
const nT = Object.keys(T).length;
document.getElementById("tiles").innerHTML = [
 [fmt(nT), "topics generated", `Vanilla ships ${fmt(V.topics)} — all visible from minute one.`],
 ["4 × 4", "axes × tiers per family", "Damage, Range, Reload, Accuracy. Breadth-first by construction."],
 [`${Math.round(100*V.pureUpgradePoints/V.points)}%`, "of vanilla research buys nothing",
  `${V.pureUpgrades} of ${V.topics} topics unlock no object at all.`],
 ["9 / 18", "weapon knobs used", "Vanilla uses 7. Range and penetration are untouched there."],
].map(([n,l,d])=>`<div class="tile"><div class="n">${n}</div><div class="l">${l}</div><div class="d">${d}</div></div>`).join("");
document.getElementById("tcount").textContent = fmt(nT);

/* ── ratchet grid ──────────────────────────────────────────────────────── */
const FAMS = Object.keys(DATA.families).filter(f=>(DATA.inventory[f]||[]).length);
let cur = FAMS.includes("Cannon") ? "Cannon" : FAMS[0];
document.getElementById("famPills").innerHTML = FAMS.map(f=>
 `<button class="pill" type="button" data-f="${f}" aria-pressed="${f===cur}">${DATA.families[f].label}</button>`).join("");
document.getElementById("famPills").addEventListener("click",e=>{
 const b=e.target.closest("[data-f]"); if(!b) return;
 cur=b.dataset.f;
 document.querySelectorAll("#famPills .pill").forEach(p=>p.setAttribute("aria-pressed",p.dataset.f===cur));
 renderGrid();
});
const ROMAN=["I","II","III","IV"];
function renderGrid(){
 const g=document.getElementById("ratchet");
 let h=`<div class="ghead">Axis</div>`;
 for(let t=1;t<=4;t++){
   h+=`<div class="ghead">Tier ${ROMAN[t-1]}</div>`;
   if(t<4) h+=`<div class="ghead" style="text-align:center">gate</div>`;
 }
 AXES.forEach(ax=>{
   h+=`<div class="axlab"><div class="a">${ax.label}</div><div class="p">${ax.params}</div></div>`;
   for(let t=1;t<=4;t++){
     const id=`R-Wpn-${cur}-${ax.key}${String(t).padStart(2,"0")}`;
     const tp=T[id];
     if(tp){
       const raw=(tp.results&&tp.results[0]&&tp.results[0].value)||0;
       // FirePause/ReloadTime are stored negative (a reduction). Show the player-facing
       // gain instead — "+10% rate of fire" reads as progress; "-10%" reads as a nerf.
       const disp=Math.abs(raw), unit=ax.key==="Reload"?"% rate of fire":"%";
       h+=`<div class="cell" style="--c:var(--t${t});--ink:var(--t${t}-ink)">
            <div class="nm">${tp.name}</div>
            <div class="v">+${disp}${unit} · ${fmt(tp.researchPoints)} pts${MT[id].knowledge?" · "+fmt(MT[id].knowledge)+" know":""}</div>
           </div>`;
     } else h+=`<div></div>`;
     if(t<4){
       const cid=`R-Cred-${cur}-Tier${t+1}`;
       h+=`<div class="gate"><span>${T[cid]?"all tier "+ROMAN[t-1]+" researched":"—"}</span></div>`;
     }
   }
 });
 g.innerHTML=h;
 const sigNames=(DATA.signatures[cur]||[]).map(x=>x[1]);
 const inv=(DATA.inventory[cur]||[]).map(x=>x[1]).filter(n=>!n.startsWith("*"));
 const lead=sigNames.length?sigNames:inv;
 document.getElementById("ratchet").insertAdjacentHTML("beforeend",
  `<p class="gaterow">Applies to all <strong>${DATA.families[cur].subclass}</strong> weapons —
   ${inv.length} of them — including ${lead.slice(0,4).join(", ")}${inv.length>4?", and the cyborg, VTOL and AA variants":""}.
   Upgrades are filtered by <code>ImpactClass</code>, so one topic improves the whole family.</p>`);
}
renderGrid();

/* ── ladder chart ──────────────────────────────────────────────────────── */
(function(){
 const van=DATA.ladders.vanilla, doc=DATA.ladders.doctrine;
 const W=760,H=290,P={t:16,r:26,b:44,l:46}, iw=W-P.l-P.r, ih=H-P.t-P.b;
 const maxT=Math.max(van.length,doc.length), maxY=28;
 const x=i=>P.l+(iw*i)/(maxT-1), y=v=>P.t+ih-(ih*v)/maxY;
 const series=[{k:"Vanilla (additive on base)",c:"var(--k-infrastructure)",d:van},
               {k:"DOCTRINE (constant relative)",c:"var(--k-ratchet)",d:doc}];
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Relative gain per upgrade tier. Vanilla decays from 25 percent to 8.3 percent across nine tiers; DOCTRINE holds 25 percent across four.">`;
 for(let gg=0;gg<=25;gg+=5){
  s+=`<line x1="${P.l}" x2="${W-P.r}" y1="${y(gg)}" y2="${y(gg)}" stroke="var(--rule)" stroke-width="1"/>`;
  s+=`<text x="${P.l-9}" y="${y(gg)+4}" text-anchor="end" font-size="11.5" fill="var(--text-muted)">${gg}%</text>`;}
 for(let i=0;i<maxT;i++)
  s+=`<text x="${x(i)}" y="${H-P.b+19}" text-anchor="middle" font-size="11.5" fill="var(--text-muted)">${i+1}</text>`;
 s+=`<text x="${P.l+iw/2}" y="${H-6}" text-anchor="middle" font-size="12" fill="var(--text-secondary)">upgrade tier</text>`;
 series.forEach(se=>{
  s+=`<path d="${se.d.map((v,i)=>(i?"L":"M")+x(i)+" "+y(v)).join(" ")}" fill="none" stroke="${se.c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  se.d.forEach((v,i)=>{s+=`<circle cx="${x(i)}" cy="${y(v)}" r="4.5" fill="${se.c}" stroke="var(--surface-1)" stroke-width="2"/>`;});});
 series.forEach(se=>{const li=se.d.length-1;
  s+=`<text x="${x(0)+9}" y="${y(se.d[0])-10}" font-size="12" font-weight="600" fill="var(--text-primary)">${se.d[0]}%</text>`;
  s+=`<text x="${x(li)+9}" y="${y(se.d[li])+4}" font-size="12" font-weight="600" fill="var(--text-primary)">${se.d[li]}%</text>`;});
 s+=`<line id="ch" x1="0" x2="0" y1="${P.t}" y2="${P.t+ih}" stroke="var(--rule-strong)" stroke-width="1" opacity="0"/>`;
 s+=`<rect x="${P.l}" y="${P.t}" width="${iw}" height="${ih}" fill="transparent" id="hit"/></svg>`;
 document.getElementById("ladderChart").innerHTML=s;
 document.getElementById("ladderLegend").innerHTML=series.map(se=>`<span><i style="background:${se.c}"></i>${se.k}</span>`).join("");
 const svg=document.querySelector("#ladderChart svg"),tip=document.getElementById("ladderTip"),
       ch=svg.querySelector("#ch"),hit=svg.querySelector("#hit"),wrap=svg.closest(".chartwrap");
 hit.addEventListener("pointermove",e=>{
  const r=svg.getBoundingClientRect(), sx=(e.clientX-r.left)*(W/r.width);
  let i=Math.round(((sx-P.l)/iw)*(maxT-1)); i=Math.max(0,Math.min(maxT-1,i));
  ch.setAttribute("x1",x(i));ch.setAttribute("x2",x(i));ch.setAttribute("opacity","1");
  tip.innerHTML=`<div style="font-weight:620;margin-bottom:4px">Tier ${i+1}</div>`+series.map(se=>
   se.d[i]===undefined?"":`<div><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${se.c};margin-right:6px"></i>${se.k.split(" (")[0]} <b>${se.d[i]}%</b></div>`).join("");
  const wr=wrap.getBoundingClientRect();
  tip.style.left=Math.min(wr.width-200,(e.clientX-wr.left)+14)+"px";
  tip.style.top=((e.clientY-wr.top)-12)+"px";tip.style.opacity="1";});
 hit.addEventListener("pointerleave",()=>{tip.style.opacity="0";ch.setAttribute("opacity","0")});
})();

/* ── kill value curve ───────────────────────────────────────────────────── */
(function(){
 const KV=DATA.killvalue, C=KV.curve, S=KV.samples;
 const W=760,H=270,P={t:16,r:30,b:44,l:46}, iw=W-P.l-P.r, ih=H-P.t-P.b;
 const maxX=3.0, maxY=2.6;
 const x=r=>P.l+iw*Math.min(r,maxX)/maxX, y=w=>P.t+ih-ih*w/maxY;
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Kill value weighting. Targets below 0.4 times your own unit cost are worth zero; the weight ramps to 1.0 at parity and caps at 2.5 for targets 2.5 times your cost or more.">`;
 // zero band
 s+=`<rect x="${x(0)}" y="${P.t}" width="${x(C.zero_below)-x(0)}" height="${ih}" fill="var(--rule)" opacity=".55"/>`;
 s+=`<text x="${(x(0)+x(C.zero_below))/2}" y="${P.t+ih/2}" text-anchor="middle" font-size="11.5" fill="var(--text-muted)" font-weight="620">WORTH NOTHING</text>`;
 for(let g=0;g<=2.5;g+=0.5){
  s+=`<line x1="${P.l}" x2="${W-P.r}" y1="${y(g)}" y2="${y(g)}" stroke="var(--rule)" stroke-width="1"/>`;
  s+=`<text x="${P.l-9}" y="${y(g)+4}" text-anchor="end" font-size="11.5" fill="var(--text-muted)">${g.toFixed(1)}×</text>`;}
 for(let r=0;r<=3;r+=0.5)
  s+=`<text x="${x(r)}" y="${H-P.b+19}" text-anchor="middle" font-size="11.5" fill="var(--text-muted)">${r.toFixed(1)}</text>`;
 s+=`<text x="${P.l+iw/2}" y="${H-6}" text-anchor="middle" font-size="12" fill="var(--text-secondary)">target cost ÷ your own p75 unit cost</text>`;
 // parity marker
 s+=`<line x1="${x(1)}" x2="${x(1)}" y1="${P.t}" y2="${P.t+ih}" stroke="var(--rule-strong)" stroke-width="1" stroke-dasharray="3 3"/>`;
 s+=`<text x="${x(1)+6}" y="${P.t+12}" font-size="11" fill="var(--text-muted)">parity</text>`;
 s+=`<path d="${S.map((p,i)=>(i?"L":"M")+x(p.r)+" "+y(p.w)).join(" ")}" fill="none" stroke="var(--k-ratchet)" stroke-width="2" stroke-linejoin="round"/>`;
 [[C.zero_below,0],[1,1],[C.cap_at,C.cap_weight]].forEach(([r,w],i)=>{
  s+=`<circle cx="${x(r)}" cy="${y(w)}" r="4.5" fill="var(--k-ratchet)" stroke="var(--surface-1)" stroke-width="2"/>`;
  s+=`<text x="${x(r)+(i===2?-10:9)}" y="${y(w)-9}" font-size="12" font-weight="600" text-anchor="${i===2?"end":"start"}" fill="var(--text-primary)">${w.toFixed(1)}×</text>`;});
 s+=`<rect x="${P.l}" y="${P.t}" width="${iw}" height="${ih}" fill="transparent" id="kvhit"/></svg>`;
 document.getElementById("kvChart").innerHTML=s;
 const svg=document.querySelector("#kvChart svg"),tip=document.getElementById("kvTip"),
       hit=svg.querySelector("#kvhit"),wrap=svg.closest(".chartwrap");
 hit.addEventListener("pointermove",e=>{
  const rc=svg.getBoundingClientRect(), r=Math.max(0,Math.min(maxX,((e.clientX-rc.left)*(W/rc.width)-P.l)/iw*maxX));
  const w=S.reduce((a,b)=>Math.abs(b.r-r)<Math.abs(a.r-r)?b:a).w;
  tip.innerHTML=`<div style="font-weight:620">${r.toFixed(2)}× your unit cost</div><div>worth <b>${w.toFixed(2)}×</b> knowledge</div>`;
  const wr=wrap.getBoundingClientRect();
  tip.style.left=Math.min(wr.width-190,(e.clientX-wr.left)+14)+"px";
  tip.style.top=((e.clientY-wr.top)-12)+"px";tip.style.opacity="1";});
 hit.addEventListener("pointerleave",()=>{tip.style.opacity="0"});
 // reference-point table
 const keys=Object.keys(KV.table); let curK=keys[1]||keys[0];
 document.getElementById("kvPills").innerHTML=keys.map(k=>
  `<button class="pill" type="button" data-kv="${k}" aria-pressed="${k===curK}">${k}</button>`).join("");
 function drawT(){
  const t=KV.table[curK];
  document.getElementById("kvTable").innerHTML=
   `<thead><tr><th>target killed</th><th class="num">cost</th><th class="num">ratio</th><th class="num">knowledge</th></tr></thead><tbody>`+
   t.rows.map(r=>`<tr><td>${r.name}</td><td class="num">${r.cost}</td><td class="num">${r.ratio.toFixed(2)}×</td>
     <td class="num" style="font-weight:620;color:${r.weight===0?"var(--text-muted)":"var(--text-primary)"}">${r.weight===0?"nothing":r.weight.toFixed(2)+"×"}</td></tr>`).join("")+
   `</tbody>`;}
 document.getElementById("kvPills").addEventListener("click",e=>{
  const b=e.target.closest("[data-kv]"); if(!b)return; curK=b.dataset.kv;
  document.querySelectorAll("#kvPills .pill").forEach(p=>p.setAttribute("aria-pressed",p.dataset.kv===curK));
  drawT();});
 drawT();
})();

/* ── spine ─────────────────────────────────────────────────────────────── */
document.getElementById("spine").innerHTML=
 ["R-Struc-CommandRelay","R-Comp-CommandTurret01","R-Sys-Debrief01","R-Comp-CommandTurret02",
  "R-Sys-Debrief02","R-Sys-DataCore","R-Comp-CommandTurret03","R-Sys-Telemetry"]
 .filter(id=>T[id]).map(id=>{const t=T[id],m=MT[id];
  return `<div class="step${id==="R-Sys-Debrief01"?" key":""}"><div class="nm">${t.name}</div>
   <div class="cost">${fmt(t.researchPoints)} pts · ${t.researchPower} pw</div>
   <div class="nt">${m.note||""}</div></div>`;}).join("");
(function markWraps(){
  const st=[...document.querySelectorAll("#spine .step")];
  const tag=()=>{let top=null; st.forEach(e=>{const t=e.offsetTop;
    if(top===null||t>top+4){top=t; e.classList.add("wrapstart");} else e.classList.remove("wrapstart");});};
  tag(); window.addEventListener("resize",tag);
})();

/* ── other kinds ───────────────────────────────────────────────────────── */
const OK=["signature","penetration","infrastructure","chassis"];
let curK="penetration";
document.getElementById("kindPills").innerHTML=OK.map(k=>
 `<button class="pill" type="button" data-k="${k}" aria-pressed="${k===curK}">${KLABEL[k]}</button>`).join("");
document.getElementById("kindPills").addEventListener("click",e=>{
 const b=e.target.closest("[data-k]"); if(!b)return; curK=b.dataset.k;
 document.querySelectorAll("#kindPills .pill").forEach(p=>p.setAttribute("aria-pressed",p.dataset.k===curK));
 renderOthers();});
function renderOthers(){
 const ids=Object.keys(T).filter(id=>MT[id].kind===curK).sort();
 document.getElementById("others").innerHTML=ids.map(id=>{const t=T[id],m=MT[id];
  return `<div class="node" style="--c:${kc(curK)}"><div class="nm">${t.name}</div>
   <div class="mt">${fmt(t.researchPoints)} pts · ${t.researchPower} pw</div>
   <div class="nt">${m.note||""}</div></div>`;}).join("");}
renderOthers();

/* ── weapon lineage ─────────────────────────────────────────────────────── */
const WEAP = Object.keys(T).filter(id=>MT[id].kind==="weapon");
const FAMOF = {}; WEAP.forEach(id=>FAMOF[id]=MT[id].family);
const AXKEY = {Damage:"Warhead",Range:"Fire Control",Reload:"Loading Drill",Accuracy:"Gunnery"};
function gateLabel(dep){
  const m=/^R-Wpn-([A-Za-z]+)-(Damage|Range|Reload|Accuracy)(\d+)$/.exec(dep);
  if(!m) return null;
  return {fam:m[1], txt:`${AXKEY[m[2]]} ${["I","II","III","IV"][+m[3]-1]}`};
}
function renderLineage(){
  const ids=WEAP.filter(id=>FAMOF[id]===cur);
  if(!ids.length){document.getElementById("lineage").innerHTML=
    `<p style="color:var(--text-muted);font-size:13px">No distinct guns in this family — it is upgraded only.</p>`;
    document.getElementById("linNote").textContent="";return;}
  const set=new Set(ids);
  const wdeps={}, gates={}, foreign={};
  ids.forEach(id=>{
    wdeps[id]=[]; gates[id]=[]; foreign[id]=[];
    (T[id].requiredResearch||[]).forEach(d=>{
      if(set.has(d)) wdeps[id].push(d);
      else if(MT[d]&&MT[d].kind==="weapon") foreign[id].push(d);
      else {const g=gateLabel(d); if(g) gates[id].push(g);}
    });
  });
  // Depth must count the ratchet gate, not just gun-to-gun succession. A gun whose
  // only prerequisite is "Warhead II" is NOT available at the same time as the
  // starting gun — it is two battlefield-earned tiers away.
  const tierOf=d=>{const m=/^R-Wpn-[A-Za-z]+-(?:Damage|Range|Reload|Accuracy)(\d+)$/.exec(d);
                   return m?+m[1]:0;};
  const depth={}; const dep=id=>{ if(depth[id]!==undefined) return depth[id];
    depth[id]=0; // guard cycles
    const viaGun=wdeps[id].length?1+Math.max(...wdeps[id].map(dep)):0;
    const viaGate=Math.max(0,...(T[id].requiredResearch||[]).map(tierOf));
    return depth[id]=Math.max(viaGun,viaGate);};
  ids.forEach(dep);
  const cols={}; ids.forEach(id=>{(cols[depth[id]]=cols[depth[id]]||[]).push(id);});
  Object.values(cols).forEach(c=>c.sort((a,b)=>T[a].researchPoints-T[b].researchPoints));
  const nC=Object.keys(cols).length, maxR=Math.max(...Object.values(cols).map(c=>c.length));
  const CW=210, CH=86, GX=54, GY=16, PAD=8;
  const W=PAD*2+nC*CW+(nC-1)*GX, H=PAD*2+maxR*CH+(maxR-1)*GY+22;
  const pos={};
  Object.keys(cols).map(Number).sort((a,b)=>a-b).forEach(d=>{
    cols[d].forEach((id,i)=>{pos[id]={x:PAD+d*(CW+GX), y:PAD+22+i*(CH+GY)};});});
  let s=`<svg viewBox="0 0 ${W} ${H}" style="min-width:${Math.min(W,1100)}px" role="img" aria-label="Weapon succession for the ${DATA.families[cur].label} family. Each box is a gun; arrows are prerequisites; tags show which ratchet tier must be researched first.">`;
  Object.keys(cols).map(Number).sort((a,b)=>a-b).forEach(d=>{
    s+=`<text x="${PAD+d*(CW+GX)}" y="12" font-size="11" letter-spacing="1" fill="var(--text-muted)" font-weight="620">${d===0?"START":"TIER "+["I","II","III","IV","V","VI"][d-1]}</text>`;});
  // edges
  ids.forEach(id=>{ wdeps[id].concat(foreign[id]).forEach(d=>{
    if(!pos[d]) return;
    const a={x:pos[d].x+CW,y:pos[d].y+CH/2}, b={x:pos[id].x,y:pos[id].y+CH/2};
    const mx=(a.x+b.x)/2;
    s+=`<path d="M${a.x} ${a.y} C${mx} ${a.y} ${mx} ${b.y} ${b.x-7} ${b.y}" fill="none" stroke="var(--rule-strong)" stroke-width="1.5"/>`;
    s+=`<path d="M${b.x-7} ${b.y-4} L${b.x} ${b.y} L${b.x-7} ${b.y+4}" fill="var(--rule-strong)"/>`;});});
  // nodes
  ids.forEach(id=>{
    const t=T[id], p=pos[id], guns=(MT[id].guns||[]).length;
    const gt=gates[id].map(g=>g.fam===cur?g.txt:`${DATA.families[g.fam]?DATA.families[g.fam].label:g.fam} ${g.txt}`);
    const ext=foreign[id].filter(d=>FAMOF[d]!==cur).map(d=>T[d].name);
    s+=`<g class="lnode"><rect x="${p.x}" y="${p.y}" width="${CW}" height="${CH}" rx="9" fill="var(--surface-1)"/>`;
    s+=`<rect x="${p.x}" y="${p.y}" width="3.5" height="${CH}" rx="2" fill="var(--t${Math.min(4,depth[id]+1)})"/>`;
    s+=`<text x="${p.x+13}" y="${p.y+20}" font-weight="620" fill="var(--text-primary)">${t.name.length>24?t.name.slice(0,23)+"…":t.name}</text>`;
    s+=`<text x="${p.x+13}" y="${p.y+37}" font-size="11" fill="var(--text-muted)">${fmt(t.researchPoints)} pts · ${t.researchPower} pw</text>`;
    if(gt.length) s+=`<text x="${p.x+13}" y="${p.y+55}" font-size="11" fill="var(--k-ratchet)" font-weight="600">needs ${gt.join(" + ").slice(0,30)}</text>`;
    if(ext.length) s+=`<text x="${p.x+13}" y="${p.y+72}" font-size="11" fill="var(--k-signature)">via ${ext.join(", ").slice(0,28)}</text>`;
    s+=`</g>`;});
  s+=`</svg>`;
  document.getElementById("lineage").innerHTML=s;
  document.getElementById("linLegend").innerHTML=
   `<span><i style="background:var(--k-ratchet)"></i>battlefield-earned tier required</span>`+
   `<span><i style="background:var(--k-signature)"></i>prerequisite from another family</span>`+
   `<span><i style="background:var(--rule-strong)"></i>succeeds directly</span>`;
  document.getElementById("linNote").textContent=
   `${ids.length} guns in the ${DATA.families[cur].label} line. Every "needs" tag is a ratchet tier — `+
   `it cannot be bought, only unlocked by fighting with this family and then paid for.`;
}
const _rg=renderGrid; renderGrid=function(){_rg(); renderLineage();};
renderLineage();

/* ── cross-family map ───────────────────────────────────────────────────── */
(function(){
  const edges={};
  (DATA.crosslinks||[]).forEach(([src,tid])=>{
    const dst=MT[tid]&&MT[tid].family; if(!dst||dst===src) return;
    const k=src+">"+dst; (edges[k]=edges[k]||{src,dst,via:[]}).via.push(T[tid].name);});
  const list=Object.values(edges);
  if(!list.length){document.getElementById("cross").innerHTML="";return;}
  const fams=FAMS, R=30, CX=440, CY=225, RAD=168;
  const ang=i=>(-Math.PI/2)+(2*Math.PI*i)/fams.length;
  const P={}; fams.forEach((f,i)=>{P[f]={x:CX+RAD*Math.cos(ang(i)),y:CY+RAD*Math.sin(ang(i))};});
  let s=`<svg viewBox="0 0 ${CX*2} ${CY*2}" style="min-width:700px" role="img" aria-label="Cross-family prerequisite map: which weapon families unlock guns in other families.">`;
  list.forEach(e=>{const a=P[e.src],b=P[e.dst]; if(!a||!b) return;
    const dx=b.x-a.x, dy=b.y-a.y, L=Math.hypot(dx,dy)||1;
    const ax=a.x+dx/L*R, ay=a.y+dy/L*R, bx=b.x-dx/L*(R+9), by=b.y-dy/L*(R+9);
    s+=`<path d="M${ax} ${ay} Q${(ax+bx)/2+dy*0.13} ${(ay+by)/2-dx*0.13} ${bx} ${by}" fill="none" stroke="var(--k-signature)" stroke-width="1.6" opacity=".75"/>`;
    const px=bx-dx/L*3, py=by-dy/L*3, nx=-dy/L*4.5, ny=dx/L*4.5;
    s+=`<path d="M${px+nx} ${py+ny} L${bx+dx/L*8} ${by+dy/L*8} L${px-nx} ${py-ny}" fill="var(--k-signature)" opacity=".9"/>`;});
  fams.forEach(f=>{const p=P[f];
    s+=`<circle cx="${p.x}" cy="${p.y}" r="${R}" fill="var(--surface-1)" stroke="var(--rule-strong)"/>`;
    s+=`<text x="${p.x}" y="${p.y+4}" text-anchor="middle" font-size="11" font-weight="620" fill="var(--text-primary)">${DATA.families[f].label.slice(0,11)}</text>`;});
  s+=`</svg>`;
  document.getElementById("cross").innerHTML=s+
   `<div style="margin-top:14px;font-size:12.5px;color:var(--text-secondary);line-height:1.7">`+
   list.map(e=>`<div><strong>${DATA.families[e.src].label}</strong> → <strong>${DATA.families[e.dst].label}</strong><span style="color:var(--text-muted)"> — ${[...new Set(e.via)].join(", ")}</span></div>`).join("")+`</div>`;
})();

/* ── table ─────────────────────────────────────────────────────────────── */
document.getElementById("topicTable").innerHTML=
 `<thead><tr><th>Topic</th><th>Kind</th><th class="num">Points</th><th class="num">Power</th><th>Requires</th></tr></thead><tbody>`+
 Object.keys(T).sort().map(id=>{const t=T[id],m=MT[id];
  return `<tr><td><strong>${t.name}</strong><br><span style="color:var(--text-muted);font-size:11.5px">${id}</span></td>
   <td><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${m.kind==="ratchet"?"var(--t3)":kc(m.kind)};margin-right:6px"></i>${KLABEL[m.kind]||m.kind}</td>
   <td class="num">${fmt(t.researchPoints)}</td><td class="num">${t.researchPower}</td>
   <td style="font-size:11.5px;color:var(--text-secondary)">${(t.requiredResearch||["—"]).join("<br>")}</td></tr>`;}).join("")+`</tbody>`;
const tb=document.getElementById("tableBtn"),tv=document.getElementById("tableView");
tb.addEventListener("click",()=>{const s=tv.hidden;tv.hidden=!s;
 tb.setAttribute("aria-expanded",String(s));tb.textContent=s?"Hide table":"Show table";});

/* ── theme ─────────────────────────────────────────────────────────────── */
const tbtn=document.getElementById("themeBtn");
tbtn.addEventListener("click",()=>{
 const dark=document.documentElement.getAttribute("data-theme")==="dark";
 document.documentElement.setAttribute("data-theme",dark?"light":"dark");
 tbtn.textContent=dark?"Dark mode":"Light mode";});
</script></body></html>"""

out = HTML.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
open("/home/claude/wz-doctrine/techtree.html", "w").write(out)
print(f"techtree.html — {len(out):,} bytes, {len(topics)} topics embedded")
