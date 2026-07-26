const D=window.DASHBOARD_DATA;
const eur=v=>new Intl.NumberFormat("en-DE",{style:"currency",currency:"EUR",notation:Math.abs(v)>=1e6?"compact":"standard",maximumFractionDigits:1}).format(v);
const pct=v=>`${(v*100).toFixed(v<.01?2:1)}%`;
const esc=s=>String(s).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
document.getElementById("freshness").textContent=`Data as of ${D.summary.as_of} · ${D.summary.data_label}`;
document.getElementById("kpis").innerHTML=[
 [eur(D.summary.annualized_spend_eur),"Annualized managed spend"],
 [eur(D.summary.ppv_eur),"Purchase-price variance"],
 [`${D.summary.on_time_rate_pct}%`,"On-time delivery rate"],
 [`${D.summary.defect_rate_pct}%`,"Quantity-weighted defect rate"],
 [D.summary.anomalies,"PO exceptions for review"]
].map(x=>`<div class="kpi"><strong>${x[0]}</strong><span>${x[1]}</span></div>`).join("");

function lineChart(){
 const rows=D.monthly,w=620,h=285,l=58,r=16,t=15,b=38,iw=w-l-r,ih=h-t-b,max=Math.max(...rows.flatMap(x=>[x.spend_eur,x.standard_eur]))*1.08;
 const px=i=>l+i/(rows.length-1)*iw,py=v=>t+ih*(1-v/max);
 let s=`<svg viewBox="0 0 ${w} ${h}" class="chart" role="img" aria-label="Monthly actual and standard procurement spend">`;
 [0,.25,.5,.75,1].forEach(q=>{const y=t+ih*(1-q);s+=`<line x1="${l}" y1="${y}" x2="${w-r}" y2="${y}" class="gridline"/><text x="${l-7}" y="${y+4}" text-anchor="end" class="label">${eur(max*q)}</text>`});
 s+=`<polyline points="${rows.map((x,i)=>`${px(i)},${py(x.spend_eur)}`).join(" ")}" class="line-a"/><polyline points="${rows.map((x,i)=>`${px(i)},${py(x.standard_eur)}`).join(" ")}" class="line-b"/>`;
 [0,Math.floor(rows.length/2),rows.length-1].forEach(i=>s+=`<text x="${px(i)}" y="${h-13}" text-anchor="${i===0?"start":i===rows.length-1?"end":"middle"}" class="label">${rows[i].month}</text>`);
 return s+`</svg><div style="font-size:12px;color:#66736f"><span style="color:#2f715d">●</span> Actual spend &nbsp; <span style="color:#d18b34">●</span> Standard cost</div>`;
}
function riskChart(){
 const rows=D.suppliers.slice(0,9),w=480,h=285,l=118,r=36,t=8,b=22,ih=h-t-b,bh=ih/rows.length*.65;
 let s=`<svg viewBox="0 0 ${w} ${h}" class="chart" role="img" aria-label="Highest supplier risk scores">`;
 rows.forEach((x,i)=>{const y=t+i*ih/rows.length,klass=x.risk_band==="Escalate"?"escalate":x.risk_band==="Review"?"review":"";s+=`<text x="${l-8}" y="${y+bh*.8}" text-anchor="end" class="label">${esc(x.supplier_name)}</text><rect x="${l}" y="${y}" width="${x.risk_score/100*(w-l-r)}" height="${bh}" rx="4" class="bar ${klass}"><title>${x.risk_band}: ${x.risk_score}</title></rect><text x="${l+x.risk_score/100*(w-l-r)+6}" y="${y+bh*.8}" class="label">${x.risk_score}</text>`});
 return s+`</svg>`;
}
function exposures(){
 const max=Math.max(...D.components.map(x=>x.spend_eur));
 document.getElementById("components").innerHTML=D.components.slice(0,8).map(x=>`<div class="exposure-row"><b>${esc(x.component)}</b><div class="track"><div class="fill" style="width:${x.spend_eur/max*100}%"></div></div><span>${eur(x.spend_eur)}</span></div>`).join("");
}
document.getElementById("trend").innerHTML=lineChart();
document.getElementById("risk").innerHTML=riskChart();
exposures();
document.getElementById("exceptions").innerHTML=D.exceptions.slice(0,18).map(x=>`<tr><td>${x.purchase_order_id}</td><td>${esc(x.supplier_name)}</td><td>${esc(x.component)}</td><td>${eur(x.actual_spend_eur)}</td><td>${x.price_variance_pct.toFixed(1)}%</td><td>${x.delivery_delay_days}d</td><td>${pct(x.defect_rate)}</td><td><span class="reason">${x.anomaly_reason}</span></td></tr>`).join("");
const commodity=document.getElementById("commodity"),energy=document.getElementById("energy");
function scenario(){
 const cs=Number(commodity.value)/100,es=Number(energy.value)/100;
 const periodMonths=D.monthly.length;
 const impact=D.components.reduce((sum,x)=>sum+x.spend_eur*(12/periodMonths)*(x.commodity_exposure*cs+x.energy_exposure*es),0);
 document.getElementById("commodityLabel").textContent=`${cs>=0?"+":""}${Math.round(cs*100)}%`;
 document.getElementById("energyLabel").textContent=`${es>=0?"+":""}${Math.round(es*100)}%`;
 document.getElementById("impact").textContent=`${impact>=0?"+":""}${eur(impact)} / yr`;
}
commodity.addEventListener("input",scenario);energy.addEventListener("input",scenario);scenario();
