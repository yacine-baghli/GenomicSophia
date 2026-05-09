// ─── Theme Toggle ──────────────────────────────────────────────────────────
function toggleTheme(){
  const html=document.documentElement;
  const btn=document.getElementById('theme-btn');
  if(html.getAttribute('data-theme')==='dark'){
    html.setAttribute('data-theme','light');btn.textContent='🌙 Dark';
  }else{
    html.setAttribute('data-theme','dark');btn.textContent='☀️ Light';
  }
}

// ─── Tab Switching ─────────────────────────────────────────────────────────
function switchTab(id,el){
  document.querySelectorAll('.tab-body').forEach(t=>t.style.display='none');
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).style.display='block';
  el.classList.add('active');
}

// ─── VQS API Analyze ──────────────────────────────────────────────────────
async function runVQS(){
  const keys=document.getElementById('dataset-keys').value.trim().split('\n').filter(k=>k.trim());
  if(!keys.length){alert('Paste at least one dataset key.');return;}
  setStatus('spin','Connecting...');
  try{
    const r=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:document.getElementById('username').value,
        password:document.getElementById('password').value,
        dataset_keys:keys,llm_provider:document.getElementById('llm').value})});
    const d=await r.json();
    if(d.success){setStatus('on','Connected');renderCases(d.ranked_cases);}
    else{setStatus('off','Error');alert(d.error);}
  }catch(e){setStatus('off','Failed');alert(e.message);}
}

// ─── CSV Analyze ──────────────────────────────────────────────────────────
async function runCSV(){
  const file=document.getElementById('csv-file').files[0];
  if(!file){alert('Select a CSV file.');return;}
  setStatus('spin','Parsing...');
  const fd=new FormData();
  fd.append('csv_file',file);
  fd.append('llm_provider',document.getElementById('llm-csv').value);
  try{
    const r=await fetch('/api/csv',{method:'POST',body:fd});
    const d=await r.json();
    if(d.success){setStatus('on','CSV Loaded');renderCases(d.ranked_cases);}
    else{setStatus('off','Error');alert(d.error);}
  }catch(e){setStatus('off','Failed');alert(e.message);}
}

function setStatus(cls,txt){
  document.getElementById('conn-status').innerHTML=`<span class="dot ${cls}"></span>${txt}`;
}

// ─── Demo Data ────────────────────────────────────────────────────────────
function loadDemo(){
  setStatus('on','Demo Mode');
  renderCases([
    {case_id:"Sample A — NSCLC Panel",case_score:82,urgency:"critical",urgency_color:"#ef4444",urgency_label:"🔴 CRITICAL",
     total_variants:47,actionable_count:4,pathogenic_count:3,
     avg_actionability:72,avg_disease_urgency:68,avg_qa_confidence:85,avg_gnomad:82,avg_clinvar:70,
     top_genes:["EGFR","TP53","KRAS","ALK"],top_therapies:["Osimertinib","Sotorasib","Crizotinib"],
     flags:["ACMG: Pathogenic","ABCD: A","Tier 1 actionable (EGFR)"],
     scored_variants:[
       {gene:"EGFR",hgvs:"p.L858R",consequence:"Missense",acmg:"Pathogenic",abcd:"A",composite_score:95,actionability:90,disease_urgency:80,qa_confidence:92,gnomad_score:90,clinvar_score:90,clinvar:"Pathogenic",gnomad:"0.0001",therapies:["Osimertinib"],flags:["ACMG: Pathogenic","ABCD: A","Tier 1 actionable (EGFR)"]},
       {gene:"EGFR",hgvs:"p.T790M",consequence:"Missense",acmg:"Pathogenic",abcd:"A",composite_score:90,actionability:90,disease_urgency:80,qa_confidence:88,gnomad_score:95,clinvar_score:85,clinvar:"Pathogenic",gnomad:"<0.0001",therapies:["Osimertinib"],flags:["Resistance mutation","ABCD: A"]},
       {gene:"TP53",hgvs:"p.R273H",consequence:"Missense",acmg:"Pathogenic",abcd:"B",composite_score:65,actionability:30,disease_urgency:67,qa_confidence:80,gnomad_score:85,clinvar_score:80,clinvar:"Pathogenic",gnomad:"0.00003",therapies:[],flags:["Prognostic: Genomic instability"]},
       {gene:"KRAS",hgvs:"p.G12C",consequence:"Missense",acmg:"Likely Pathogenic",abcd:"B",composite_score:60,actionability:65,disease_urgency:52,qa_confidence:78,gnomad_score:75,clinvar_score:55,clinvar:"Likely_pathogenic",gnomad:"0.0002",therapies:["Sotorasib"],flags:["Tier 2 actionable (KRAS)"]},
       {gene:"STK11",hgvs:"p.Q37*",consequence:"Nonsense",acmg:"Likely Pathogenic",abcd:"C",composite_score:40,actionability:10,disease_urgency:58,qa_confidence:70,gnomad_score:80,clinvar_score:40,clinvar:"Uncertain",gnomad:"—",therapies:[],flags:["Rare variant"]}
     ],summary:{summary_bullets:["3 pathogenic variants in EGFR/TP53 — classic NSCLC driver profile.","EGFR L858R + T790M: Osimertinib is preferred first-line.","KRAS G12C: Sotorasib eligible if resistance develops.","TP53 R273H: Recommend liquid biopsy monitoring q3mo."],recommended_action:"Priority tumor board. Start Osimertinib.",estimated_review_time:"12 min"}},
    {case_id:"Sample B — Breast Cancer Panel",case_score:64,urgency:"high",urgency_color:"#f97316",urgency_label:"🟠 HIGH",
     total_variants:32,actionable_count:3,pathogenic_count:2,
     avg_actionability:58,avg_disease_urgency:55,avg_qa_confidence:82,avg_gnomad:78,avg_clinvar:62,
     top_genes:["PIK3CA","ESR1","BRCA2"],top_therapies:["Alpelisib","Olaparib","Elacestrant"],flags:[],
     scored_variants:[
       {gene:"BRCA2",hgvs:"p.S1982fs",consequence:"Frameshift",acmg:"Pathogenic",abcd:"A",composite_score:85,actionability:90,disease_urgency:80,qa_confidence:88,gnomad_score:85,clinvar_score:80,clinvar:"Pathogenic",gnomad:"0.00008",therapies:["Olaparib"],flags:["Tier 1 actionable (BRCA2)"]},
       {gene:"PIK3CA",hgvs:"p.H1047R",consequence:"Missense",acmg:"Pathogenic",abcd:"B",composite_score:70,actionability:65,disease_urgency:67,qa_confidence:82,gnomad_score:75,clinvar_score:70,clinvar:"Pathogenic",gnomad:"0.0001",therapies:["Alpelisib"],flags:["Tier 2 actionable (PIK3CA)"]},
       {gene:"ESR1",hgvs:"p.D538G",consequence:"Missense",acmg:"Likely Pathogenic",abcd:"B",composite_score:55,actionability:65,disease_urgency:52,qa_confidence:78,gnomad_score:80,clinvar_score:55,clinvar:"Likely_pathogenic",gnomad:"",therapies:["Elacestrant"],flags:[]}
     ],summary:{summary_bullets:["BRCA2 frameshift — PARP inhibitor eligible.","PIK3CA H1047R: Alpelisib + Fulvestrant indicated.","ESR1 D538G: AI resistance confirmed, switch to Elacestrant.","Recommend germline testing for HBOC syndrome."],recommended_action:"PARP inhibitor + endocrine switch.",estimated_review_time:"10 min"}},
    {case_id:"Sample C — Colorectal Panel",case_score:38,urgency:"moderate",urgency_color:"#eab308",urgency_label:"🟡 MODERATE",
     total_variants:28,actionable_count:1,pathogenic_count:1,
     avg_actionability:25,avg_disease_urgency:42,avg_qa_confidence:75,avg_gnomad:70,avg_clinvar:45,
     top_genes:["APC","KRAS","SMAD4"],top_therapies:[],flags:[],
     scored_variants:[
       {gene:"APC",hgvs:"p.R876*",consequence:"Nonsense",acmg:"Pathogenic",abcd:"B",composite_score:50,actionability:30,disease_urgency:67,qa_confidence:80,gnomad_score:90,clinvar_score:70,clinvar:"Pathogenic",gnomad:"0.00001",therapies:[],flags:["CRC driver"]},
       {gene:"KRAS",hgvs:"p.G12V",consequence:"Missense",acmg:"Likely Pathogenic",abcd:"B",composite_score:45,actionability:10,disease_urgency:52,qa_confidence:78,gnomad_score:75,clinvar_score:55,clinvar:"Likely_pathogenic",gnomad:"0.0003",therapies:[],flags:["No targeted therapy for G12V"]}
     ],summary:{summary_bullets:["APC truncation confirms WNT-driven CRC.","KRAS G12V: Anti-EGFR contraindicated.","No Tier I targets — FOLFOX + Bevacizumab recommended.","Check MSI/MMR for immunotherapy eligibility."],recommended_action:"Standard CRC protocol.",estimated_review_time:"8 min"}},
    {case_id:"Sample D — Thyroid Panel",case_score:18,urgency:"low",urgency_color:"#22c55e",urgency_label:"🟢 LOW",
     total_variants:12,actionable_count:0,pathogenic_count:0,
     avg_actionability:15,avg_disease_urgency:18,avg_qa_confidence:65,avg_gnomad:55,avg_clinvar:20,
     top_genes:["BRAF","TERT"],top_therapies:[],flags:[],
     scored_variants:[
       {gene:"BRAF",hgvs:"p.V600E",consequence:"Missense",acmg:"VUS",abcd:"C",composite_score:30,actionability:30,disease_urgency:18,qa_confidence:65,gnomad_score:55,clinvar_score:15,clinvar:"Uncertain",gnomad:"0.0005",therapies:[],flags:["Context-dependent"]}
     ],summary:{summary_bullets:["No pathogenic calls.","BRAF V600E classified VUS in thyroid context.","TERT promoter may indicate aggressiveness if paired with BRAF.","No therapeutic change indicated."],recommended_action:"Routine sign-off.",estimated_review_time:"5 min"}}
  ]);
}

// ─── Render ───────────────────────────────────────────────────────────────
function mColor(v){return v>=70?'var(--red)':v>=50?'var(--orange)':v>=30?'var(--yellow)':'var(--green)';}

function renderCases(cases){
  const g=document.getElementById('cases-grid');
  if(!cases||!cases.length){g.innerHTML='<div class="empty"><div class="icon">📭</div><p>No data.</p></div>';return;}
  g.innerHTML=cases.map((c,i)=>{
    const bc='badge-'+c.urgency;
    const s=c.summary||{};
    const bullets=s.summary_bullets||[];
    return `<div class="case-card" id="c${i}">
     <div class="case-hdr" onclick="document.getElementById('c${i}').classList.toggle('open')">
      <div class="rank" style="background:${c.urgency_color}18;color:${c.urgency_color};border:1px solid ${c.urgency_color}40">#${i+1}</div>
      <div class="case-info"><h3>${c.case_id}</h3>
       <div class="meta"><span>${c.total_variants} variants</span><span>${c.actionable_count} actionable</span><span>${c.pathogenic_count} pathogenic</span><span>~${s.estimated_review_time||'?'}</span></div>
      </div>
      <span class="badge ${bc}">${c.urgency.toUpperCase()} — ${c.case_score}</span>
      <div class="bar"><div class="bar-fill" style="width:${c.case_score}%;background:${c.urgency_color}"></div></div>
     </div>
     <div class="case-body">
      <div class="metrics">
       ${metricBox('Actionability',c.avg_actionability)}
       ${metricBox('Disease Urgency',c.avg_disease_urgency)}
       ${metricBox('QA Confidence',c.avg_qa_confidence)}
       ${metricBox('gnomAD Rarity',c.avg_gnomad)}
       ${metricBox('ClinVar Evidence',c.avg_clinvar)}
      </div>
      ${bullets.length?`<div class="summary"><h4>⚡ AI Summary</h4><ul>${bullets.map(b=>'<li>'+b+'</li>').join('')}</ul>
      ${s.recommended_action?`<div class="action"><strong>Action:</strong> ${s.recommended_action}</div>`:''}</div>`:''}
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.8rem">${(c.top_therapies||[]).map(t=>`<span class="tag tag-therapy">💊 ${t}</span>`).join('')||'<span style="font-size:.75rem;color:var(--text3)">No targeted therapies</span>'}</div>
      <div class="section-title">Variant Priority Ranking</div>
      <div style="overflow-x:auto"><table class="vtable">
       <thead><tr><th>#</th><th>Gene</th><th>HGVS</th><th>Conseq.</th><th>ACMG</th><th>ABCD</th><th>Act.</th><th>Urg.</th><th>QA</th><th>gnomAD</th><th>ClinVar</th><th>Score</th><th>Flags</th></tr></thead>
       <tbody>${(c.scored_variants||[]).map((v,vi)=>`<tr>
        <td><span class="tier-dot" style="background:${mColor(v.composite_score)}"></span>${vi+1}</td>
        <td><strong>${v.gene}</strong></td><td style="font-family:monospace;font-size:.72rem">${v.hgvs||''}</td>
        <td>${v.consequence||''}</td><td>${v.acmg||''}</td><td><strong>${v.abcd||''}</strong></td>
        <td style="color:${mColor(v.actionability)}">${v.actionability}</td>
        <td style="color:${mColor(v.disease_urgency)}">${v.disease_urgency}</td>
        <td style="color:${mColor(v.qa_confidence)}">${v.qa_confidence}</td>
        <td style="color:${mColor(v.gnomad_score)}">${v.gnomad_score}</td>
        <td style="color:${mColor(v.clinvar_score)}">${v.clinvar_score}</td>
        <td><strong>${v.composite_score}</strong></td>
        <td>${(v.flags||[]).map(f=>`<span class="tag tag-flag">${f}</span>`).join(' ')}</td>
       </tr>`).join('')}</tbody>
      </table></div>
     </div>
    </div>`;
  }).join('');
  setTimeout(()=>document.getElementById('c0')?.classList.add('open'),100);
}

function metricBox(label,val){
  const c=mColor(val||0);
  return `<div class="metric"><div class="label">${label}</div><div class="val" style="color:${c}">${val||0}</div><div class="mbar"><div class="mbar-fill" style="width:${val||0}%;background:${c}"></div></div></div>`;
}
