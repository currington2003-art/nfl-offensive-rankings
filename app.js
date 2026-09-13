const labels={QB:"Quarterbacks",RB:"Running Backs",WR:"Wide Receivers",TE:"Tight Ends"};
let pos="QB";

const $=id=>document.getElementById(id);
function fmt(n){return Number(n||0).toLocaleString(undefined,{maximumFractionDigits:1})}

async function load(){
  const view=$("view").value;
  $("updated").textContent="Loading…";
  try{
    const r=await fetch(`/api/rankings?position=${pos}&view=${view}`);
    if(!r.ok) throw new Error("API unavailable");
    const data=await r.json();
    render(data);
  }catch(e){
    $("updated").textContent="API not connected";
    $("rankings").innerHTML=`<div class="empty">
      <b>Connect the backend to show live rankings.</b>
      <p>Run <code>python api.py</code> and open the app through the API server.</p>
    </div>`;
  }
}
function render(data){
  $("updated").textContent="Live data";
  $("week").textContent=data.week || "Season";
  $("title").textContent=`Top 10 ${labels[pos]}`;
  $("description").textContent=
    data.view==="ppr"?"PPR fantasy production.":"Performance score based on position-specific production and efficiency.";
  $("rankings").innerHTML=data.players.map((p,i)=>{
    let stat=pos==="QB"
      ? `${fmt(p.pass_yards)} pass YDS • ${fmt(p.pass_tds)} pass TD • ${fmt(p.interceptions)} INT`
      : pos==="RB"
      ? `${fmt(p.rush_yards)} rush YDS • ${fmt(p.rush_tds)} rush TD • ${fmt(p.rec_yards)} rec YDS`
      : `${fmt(p.receptions)} REC • ${fmt(p.rec_yards)} YDS • ${fmt(p.rec_tds)} TD`;
    const score=data.view==="ppr"?p.ppr:p.performance_score;
    return `<article class="player">
      <div class="rank">#${i+1}</div>
      <div><div class="name">${p.player_name}</div><div class="team">${p.team||""}</div></div>
      <div class="stat">${stat}</div>
      <div class="score">${fmt(score)}</div>
    </article>`
  }).join("");
}
document.querySelectorAll(".controls button").forEach(b=>b.onclick=()=>{pos=b.dataset.position;document.querySelectorAll(".controls button").forEach(x=>x.classList.toggle("active",x===b));load()});
$("view").onchange=load;
$("refresh").onclick=load;
load();
