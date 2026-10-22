"""Single-file offline HTML replay for the arena (inline CSS/JS, no CDN)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATE = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Red vs Blue Arena · dual-loop-eval</title>
<style>
:root{--red:#ff3b5c;--blue:#2ee6ff;--bg:#07080f;--panel:#11131f;--dim:#7b8199;--gold:#ffd54a}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#1a1030 0,#07080f 60%);color:#e8eaf6;font-family:ui-sans-serif,system-ui,"PingFang SC",sans-serif;min-height:100vh}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
h1{text-align:center;font-size:42px;letter-spacing:4px;margin:8px 0 0;font-weight:900}
h1 .r{color:var(--red);text-shadow:0 0 18px var(--red)}h1 .b{color:var(--blue);text-shadow:0 0 18px var(--blue)}
.sub{text-align:center;color:var(--dim);margin-bottom:18px}
.tabs{display:flex;gap:8px;justify-content:center;margin:12px 0}
.tab{padding:8px 16px;border:1px solid #333a55;border-radius:999px;cursor:pointer;background:var(--panel);color:#ccd}
.tab.on{border-color:var(--gold);color:var(--gold);box-shadow:0 0 12px #ffd54a55}
.hud{display:grid;grid-template-columns:1fr auto 1fr;gap:16px;align-items:center;margin:16px 0}
.side{background:var(--panel);border-radius:14px;padding:14px}
.side.red{border:1px solid var(--red);box-shadow:0 0 20px #ff3b5c33}.side.blue{border:1px solid var(--blue);box-shadow:0 0 20px #2ee6ff33}
.name{font-weight:800;font-size:18px;display:flex;justify-content:space-between}
.bar{height:18px;background:#222638;border-radius:9px;overflow:hidden;margin-top:8px}
.fill{height:100%;transition:width .6s cubic-bezier(.2,.8,.2,1)}
.red .fill{background:linear-gradient(90deg,#8a0020,var(--red))}.blue .fill{background:linear-gradient(90deg,#005a80,var(--blue))}
.vs{font-size:34px;font-weight:900;color:var(--gold);text-shadow:0 0 14px var(--gold);text-align:center}
.rd{font-size:13px;color:var(--dim);text-align:center}
.ctrl{display:flex;gap:8px;justify-content:center;margin:10px 0}
button{background:#1b1f33;color:#fff;border:1px solid #3a4170;border-radius:8px;padding:8px 14px;cursor:pointer;font-weight:700}
button:hover{border-color:var(--gold)}
.stage{display:grid;grid-template-columns:1fr 1fr;gap:16px;min-height:230px}
.card{background:var(--panel);border-radius:14px;padding:16px;position:relative;animation:pop .45s ease}
.card.atk{border-left:4px solid var(--red)}.card.def{border-left:4px solid var(--blue)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;margin-right:6px;background:#2a2f4a;color:#cfd3ff}
.tag.s{background:#3a1020;color:#ff9db0}
.msg{margin-top:10px;font-size:14px;line-height:1.5}
.verdict{margin:16px auto;max-width:820px;background:#151827;border-radius:16px;padding:14px 18px;border:1px solid #333a55;animation:pop .45s ease}
.verdict.hit{border-color:var(--red);box-shadow:0 0 24px #ff3b5c44}.verdict.block{border-color:var(--blue);box-shadow:0 0 24px #2ee6ff44}
.vt{font-weight:900;font-size:20px}.hit .vt{color:var(--red)}.block .vt{color:var(--blue)}
.chip{display:inline-block;margin:6px 6px 0 0;padding:3px 10px;border-radius:6px;font-size:12px;font-family:ui-monospace,monospace;background:#0d2230;color:#8ef0ff;border:1px solid #1d4d66}
.chip.rule{background:#2b1a05;color:#ffd58a;border-color:#6b4a10}.chip.fix{background:#0f2a17;color:#8dffb0;border-color:#1f6b3a}
.combo{position:absolute;top:10px;right:12px;color:var(--gold);font-weight:900;font-size:22px;text-shadow:0 0 10px var(--gold)}
.dmg{position:absolute;right:16px;bottom:10px;font-size:26px;font-weight:900;color:var(--red);animation:float 1s ease forwards}
.timeline{display:flex;gap:4px;justify-content:center;margin:14px 0}
.dot{width:22px;height:22px;border-radius:5px;background:#222638;font-size:10px;display:flex;align-items:center;justify-content:center;cursor:pointer}
.dot.h{background:var(--red)}.dot.k{background:var(--blue);color:#000}.dot.cur{outline:2px solid var(--gold)}
section{margin-top:28px}h2{font-size:20px;border-bottom:1px solid #2a2f4a;padding-bottom:6px}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;border-bottom:1px solid #1f2338;text-align:left}
.big{font-size:34px;font-weight:900}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.stat{background:var(--panel);border-radius:12px;padding:14px;text-align:center}
.up{color:#5dff9a}.note{color:var(--dim);font-size:12px;margin-top:20px;text-align:center}
.win{text-align:center;font-size:28px;font-weight:900;margin:8px 0;letter-spacing:2px}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
@keyframes pop{from{transform:scale(.94);opacity:0}to{transform:none;opacity:1}}
@keyframes float{from{opacity:1;transform:none}to{opacity:0;transform:translateY(-30px)}}
</style></head><body><div class="wrap">
<h1><span class="r">RED</span> vs <span class="b">BLUE</span> ARENA</h1>
<div class="sub">红蓝对抗竞技场 · Red escalates attacks · AttributionJudge referees · Blue patches & rematches</div>
<div class="tabs" id="tabs"></div>
<div class="hud">
 <div class="side red"><div class="name"><span>🔴 RED · Attacker</span><span id="rhp"></span></div><div class="bar"><div class="fill" id="rbar"></div></div></div>
 <div><div class="vs">VS</div><div class="rd" id="rd"></div></div>
 <div class="side blue"><div class="name"><span>🔵 BLUE · Demo Agent</span><span id="bhp"></span></div><div class="bar"><div class="fill" id="bbar"></div></div></div>
</div>
<div class="ctrl"><button id="prev">⏮ Step</button><button id="play">▶ Play</button><button id="next">Step ⏭</button><button id="reset">↺ Reset</button></div>
<div class="timeline" id="tl"></div>
<div id="win" class="win"></div>
<div class="stage" id="stage"></div>
<div id="verdict"></div>
<section><h2>🩹 Patch Notes · 补丁说明（Referee fix → Blue playbook）</h2><div id="notes"></div></section>
<section><h2>📊 Before / After Patch</h2><div class="grid3" id="cmp"></div></section>
<section><h2>🏆 Scoreboard</h2><table id="board"></table></section>
<div class="note">Offline heuristic demo · seed=<span id="seed"></span> · mock judge, no LLM calls unless configured. Generated by dual-loop-eval arena.</div>
</div>
<script>
const D=__DATA__;let m=0,i=-1,timer=null;const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function tabs(){$('tabs').innerHTML=D.matches.map((x,k)=>`<div class="tab ${k==m?'on':''}" onclick="sel(${k})">${esc(x.label)}</div>`).join('')}
function sel(k){m=k;stop();i=-1;tabs();render()}
function render(){const M=D.matches[m],R=M.rounds,r=R[i];const rh=r?r.red_hp:100,bh=r?r.blue_hp:100;
$('rbar').style.width=rh+'%';$('bbar').style.width=bh+'%';$('rhp').textContent=rh+' HP';$('bhp').textContent=bh+' HP';
$('rd').textContent=r?`ROUND ${r.round}/${R.length}`:'READY';
$('tl').innerHTML=R.map((x,k)=>`<div class="dot ${x.passed?'k':'h'} ${k==i?'cur':''}" onclick="go(${k})">${x.round}</div>`).join('');
$('win').innerHTML=(i==R.length-1)?(M.winner=='blue'?'<span style="color:var(--blue)">🔵 BLUE WINS</span>':'<span style="color:var(--red)">🔴 RED WINS</span>'):'';
if(!r){$('stage').innerHTML='<div class="card atk"><b>Red is loading attacks…</b><div class="msg">Press ▶ Play</div></div><div class="card def"><b>Blue on guard</b><div class="msg">'+(M.rules.length?('Patched rules: '+M.rules.map(esc).join(', ')):'No patches yet')+'</div></div>';$('verdict').innerHTML='';return}
$('stage').innerHTML=`<div class="card atk">${r.combo>1?`<div class="combo">COMBO ×${r.combo}</div>`:''}<span class="tag s">${esc(r.strategy)}</span><span class="tag">${esc(r.category)}</span><div class="msg">⚔️ ${esc(r.attack)}</div>${r.damage_to_blue?`<div class="dmg">-${r.damage_to_blue}</div>`:''}</div>
<div class="card def"><span class="tag">${esc(r.scenario_id)}</span><div class="msg">🛡️ ${esc(r.response)}</div>${r.damage_to_red?`<div class="dmg" style="color:var(--blue)">-${r.damage_to_red} RED</div>`:''}</div>`;
$('verdict').innerHTML=`<div class="verdict ${r.passed?'block':'hit'}"><div class="vt">⚖️ Referee: ${r.passed?'BLOCKED 🛡️':'HIT 💥'} <span style="font-size:14px;color:var(--dim)">score ${r.score}</span></div><div class="msg">${esc(r.reasoning)}</div>
${r.passed?'':`<span class="chip">locus: ${esc(r.error_locus)}</span><span class="chip rule">rule: ${esc(r.attributed_rule)}</span><span class="chip fix">fix: ${esc(r.fix_suggestion)}</span>`}</div>`}
function go(k){i=k;render()}
function step(d){const n=D.matches[m].rounds.length;i=Math.max(-1,Math.min(n-1,i+d));render();if(i>=n-1)stop()}
function stop(){clearInterval(timer);timer=null;$('play').textContent='▶ Play'}
$('play').onclick=()=>{if(timer){stop();return}if(i>=D.matches[m].rounds.length-1)i=-1;$('play').textContent='⏸ Pause';timer=setInterval(()=>step(1),1400);step(1)};
$('next').onclick=()=>{stop();step(1)};$('prev').onclick=()=>{stop();step(-1)};$('reset').onclick=()=>{stop();i=-1;render()};
document.addEventListener('keydown',e=>{if(e.key=='ArrowRight')$('next').click();if(e.key=='ArrowLeft')$('prev').click();if(e.key==' '){e.preventDefault();$('play').click()}});
$('seed').textContent=D.seed;
$('notes').innerHTML=D.patch_notes.length?D.patch_notes.map(p=>`<div class="verdict block" style="margin:8px 0"><span class="chip">${esc(p.error_locus)}</span><span class="chip rule">${esc(p.rule)}</span><div class="msg">✅ ${esc(p.fix_suggestion)} <span style="color:var(--dim)">(first hit in round ${esc(p.first_seen_round)})</span></div></div>`).join(''):'<div class="msg">No patches.</div>';
const A=D.matches[0],B=D.matches[1];
if(B){const pct=x=>Math.round(x*100)+'%';$('cmp').innerHTML=`<div class="stat"><div>Blue block rate</div><div class="big">${pct(A.blue_win_rate)} → <span class="up">${pct(B.blue_win_rate)}</span></div></div>
<div class="stat"><div>Blue final HP</div><div class="big">${A.final_hp.blue} → <span class="up">${B.final_hp.blue}</span></div></div>
<div class="stat"><div>Winner</div><div class="big">${A.winner.toUpperCase()} → <span class="up">${B.winner.toUpperCase()}</span></div></div>`}
$('board').innerHTML='<tr><th>Match</th><th>Winner</th><th>Blue block rate</th><th>Final HP (R/B)</th><th>Max combo</th><th>MVP attack</th></tr>'+D.matches.map(x=>`<tr><td>${esc(x.label)}</td><td>${x.winner=='blue'?'🔵':'🔴'} ${x.winner}</td><td>${Math.round(x.blue_win_rate*100)}%</td><td>${x.final_hp.red} / ${x.final_hp.blue}</td><td>${x.max_combo}</td><td>${x.mvp?`R${x.mvp.round} · ${esc(x.mvp.strategy)} · -${x.mvp.damage}<br><span style="color:var(--dim)">${esc(x.mvp.attack)}</span>`:'—'}</td></tr>`).join('');
const h=location.hash.match(/m(\d)r(\d+)/);if(h){m=+h[1];i=+h[2]-1}
tabs();render();
</script></body></html>"""


def write_replay_html(result: dict[str, Any], path: str | Path) -> Path:
    data = {k: v for k, v in result.items() if not k.startswith("_")}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    return p
