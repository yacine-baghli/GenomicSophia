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

// ─── API Key Panel ────────────────────────────────────────────────────────
function toggleApiKeyPanel(){
  const p=document.getElementById('api-key-panel');
  p.style.display=p.style.display==='none'?'block':'none';
}
async function saveApiKey(){
  const key=document.getElementById('api-key-input').value.trim();
  const provider=document.getElementById('key-provider').value;
  if(!key){alert('Paste an API key.');return;}
  try{
    const r=await fetch('/api/set_key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key,provider})});
    const d=await r.json();
    document.getElementById('key-status').textContent=d.success?'✅ '+d.message:'❌ '+d.error;
    document.getElementById('key-status').style.color=d.success?'var(--green)':'var(--red)';
    if(d.success) setTimeout(()=>{document.getElementById('api-key-panel').style.display='none';},1500);
  }catch(e){document.getElementById('key-status').textContent='❌ '+e.message;}
}

// ─── Literature Modal ─────────────────────────────────────────────────────
function openPapersModal(gene,hgvs,consequence){
  const modal=document.getElementById('papers-modal');
  document.getElementById('modal-title').textContent=`📚 ${gene} ${hgvs||''} — Literature Review`;
  document.getElementById('modal-body').innerHTML='<div class="modal-loading"><div class="spinner-lg"></div><p>Searching PubMed & generating AI summary...</p></div>';
  modal.style.display='flex';
  fetch('/api/variant_papers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gene,hgvs,consequence})})
    .then(r=>r.json()).then(d=>{
      if(!d.success){document.getElementById('modal-body').innerHTML=`<p style="color:var(--red)">${d.error}</p>`;return;}
      renderPapersModal(d);
    }).catch(e=>{document.getElementById('modal-body').innerHTML=`<p style="color:var(--red)">Error: ${e.message}</p>`;});
}
function closePapersModal(){document.getElementById('papers-modal').style.display='none';}

function renderPapersModal(d){
  const s=d.summary;
  const papers=d.papers||[];
  let html='';

  // LLM Summary section
  if(s && typeof s==='object' && s.review){
    html+=`<div class="lit-summary">
      <div class="lit-badge" style="background:${evidenceColor(s.evidence_level)}15;color:${evidenceColor(s.evidence_level)};border:1px solid ${evidenceColor(s.evidence_level)}30">${s.evidence_level||'N/A'} Evidence</div>
      <p class="lit-review">${s.review}</p>
      ${s.key_findings&&s.key_findings.length?`<ul class="lit-findings">${s.key_findings.map(f=>'<li>'+f+'</li>').join('')}</ul>`:''}
      ${s.clinical_relevance?`<div class="lit-relevance"><strong>Clinical Relevance:</strong> ${s.clinical_relevance}</div>`:''}
    </div>`;
  } else if(d.error_llm){
    html+=`<div class="lit-no-key"><span>⚙️</span> ${d.error_llm}</div>`;
  } else if(typeof s==='string'){
    html+=`<div class="lit-summary"><p class="lit-review">${s}</p></div>`;
  }

  // Papers list
  if(papers.length){
    html+=`<div class="lit-papers-title">Recent PubMed Papers (${papers.length})</div>`;
    html+=papers.map(p=>`<a href="${p.url}" target="_blank" class="lit-paper">
      <div class="lit-paper-title">${p.title}</div>
      <div class="lit-paper-meta">${p.authors} · ${p.journal} · ${p.date}</div>
    </a>`).join('');
  } else {
    html+='<p style="color:var(--text3);font-size:.82rem;margin-top:1rem">No papers found on PubMed for this variant.</p>';
  }

  // PubMed link
  const q=encodeURIComponent(`${d.gene} ${d.hgvs||''} variant`.trim());
  html+=`<a href="https://pubmed.ncbi.nlm.nih.gov/?term=${q}&sort=date" target="_blank" class="lit-pubmed-link">🔍 View all results on PubMed →</a>`;

  document.getElementById('modal-body').innerHTML=html;
}
function evidenceColor(level){
  const l=(level||'').toLowerCase();
  if(l.includes('strong')) return '#22c55e';
  if(l.includes('moderate')) return '#f97316';
  if(l.includes('limited')) return '#eab308';
  return '#8b5cf6';
}

// ─── Tab Switching ─────────────────────────────────────────────────────────

function switchTab(id,el){
  document.querySelectorAll('.tab-body').forEach(t=>t.style.display='none');
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).style.display='block';
  el.classList.add('active');
}

// ─── Refresh Sample File List ─────────────────────────────────────────────
async function refreshSamples(){
  try{
    const r=await fetch('/api/samples');
    const d=await r.json();
    const el=document.getElementById('sample-list');
    if(d.success && d.samples.length){
      el.innerHTML=d.samples.map(s=>
        `<span class="chip chip-local">
          <span class="chip-icon">📁</span>
          <strong>${s.name}</strong>
          <span class="chip-size">${(s.size/1024).toFixed(0)} KB</span>
          <button class="chip-remove" onclick="removeSample('${s.name}')" title="Remove">✕</button>
        </span>`
      ).join('');
    }else{
      el.innerHTML='<span class="chip chip-empty">No CSV files — add some below</span>';
    }
  }catch(e){
    document.getElementById('sample-list').innerHTML='<span style="color:var(--red)">Error loading files</span>';
  }
}

// ─── Upload Files to /samples ─────────────────────────────────────────────
async function uploadFiles(){
  const input=document.getElementById('csv-files');
  const files=input.files;
  if(!files.length){alert('Select CSV files to add.');return;}

  setStatus('spin','Uploading...');
  const fd=new FormData();
  for(let i=0;i<files.length;i++) fd.append('csv_files',files[i]);

  try{
    const r=await fetch('/api/upload',{method:'POST',body:fd});
    const d=await r.json();
    if(d.success){
      setStatus('on',d.message);
      input.value=''; // clear file input
      await refreshSamples();
    }else{
      setStatus('off',d.error);
    }
  }catch(e){
    setStatus('off','Upload failed: '+e.message);
  }
}

// ─── Remove a Sample ──────────────────────────────────────────────────────
async function removeSample(name){
  if(!confirm(`Remove ${name} from /samples?`)) return;
  try{
    const r=await fetch('/api/remove_sample',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name})});
    const d=await r.json();
    if(d.success){
      await refreshSamples();
      setStatus('on',d.message);
    }
  }catch(e){
    setStatus('off','Remove failed');
  }
}

// ─── Rank All Cases in /samples ───────────────────────────────────────────
async function rankAll(){
  setStatus('spin','Ranking all cases...');
  const llm=document.getElementById('llm-csv')?.value||'none';
  try{
    const r=await fetch('/api/rank',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({llm_provider:llm})});
    const d=await r.json();
    if(d.success){
      const n=d.ranked_cases.length;
      setStatus('on',`${n} case${n>1?'s':''} ranked`);
      renderCases(d.ranked_cases);
    }else{
      setStatus('off','Error');
      document.getElementById('cases-grid').innerHTML=
        `<div class="empty"><div class="icon">⚠️</div><p>${d.error}</p></div>`;
    }
  }catch(e){
    setStatus('off','Failed');
    document.getElementById('cases-grid').innerHTML=
      `<div class="empty"><div class="icon">❌</div><p>Failed: ${e.message}</p></div>`;
  }
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
     top_genes:["EGFR","TP53","KRAS","ALK"],top_therapies:["Osimertinib","Sotorasib","Crizotinib"],flags:[],
     scored_variants:[
       {gene:"EGFR",hgvs:"p.L858R",consequence:"Missense",acmg:"Pathogenic",abcd:"A",composite_score:95,actionability:90,disease_urgency:80,qa_confidence:92,gnomad_score:90,clinvar_score:90,clinvar:"Pathogenic",gnomad:"0.0001",therapies:["Osimertinib"],flags:["Tier 1 actionable (EGFR)","ABCD: A"]},
       {gene:"TP53",hgvs:"p.R273H",consequence:"Missense",acmg:"Pathogenic",abcd:"B",composite_score:65,actionability:30,disease_urgency:67,qa_confidence:80,gnomad_score:85,clinvar_score:80,clinvar:"Pathogenic",gnomad:"0.00003",therapies:[],flags:["Prognostic: Genomic instability"]},
       {gene:"KRAS",hgvs:"p.G12C",consequence:"Missense",acmg:"Likely Pathogenic",abcd:"B",composite_score:60,actionability:65,disease_urgency:52,qa_confidence:78,gnomad_score:75,clinvar_score:55,clinvar:"Likely_pathogenic",gnomad:"0.0002",therapies:["Sotorasib"],flags:["Tier 2 actionable (KRAS)"]}
     ],summary:{summary_bullets:["3 pathogenic variants in EGFR/TP53.","EGFR L858R: Osimertinib first-line.","KRAS G12C: Sotorasib eligible.","TP53 R273H: Monitor q3mo."],recommended_action:"Priority tumor board.",estimated_review_time:"12 min"}},
    {case_id:"Sample B — Breast Panel",case_score:64,urgency:"high",urgency_color:"#f97316",urgency_label:"🟠 HIGH",
     total_variants:32,actionable_count:3,pathogenic_count:2,
     avg_actionability:58,avg_disease_urgency:55,avg_qa_confidence:82,avg_gnomad:78,avg_clinvar:62,
     top_genes:["PIK3CA","ESR1","BRCA2"],top_therapies:["Alpelisib","Olaparib","Elacestrant"],flags:[],
     scored_variants:[
       {gene:"BRCA2",hgvs:"p.S1982fs",consequence:"Frameshift",acmg:"Pathogenic",abcd:"A",composite_score:85,actionability:90,disease_urgency:80,qa_confidence:88,gnomad_score:85,clinvar_score:80,clinvar:"Pathogenic",gnomad:"0.00008",therapies:["Olaparib"],flags:["Tier 1 actionable (BRCA2)"]}
     ],summary:{summary_bullets:["BRCA2 frameshift — PARP inhibitor eligible.","PIK3CA H1047R: Alpelisib indicated.","Recommend germline testing."],recommended_action:"PARP inhibitor + endocrine switch.",estimated_review_time:"10 min"}}
  ]);
}

// ─── Helpers ──────────────────────────────────────────────────────────────
const SOPHIA_URL='https://platform-vandv1.sophiagenetics.com/web/genomics/finder';
function pubmedUrl(gene,hgvs){
  const q=encodeURIComponent(`${gene} ${hgvs||''} variant therapy`.trim());
  return `https://pubmed.ncbi.nlm.nih.gov/?term=${q}&sort=date`;
}
function clinvarUrl(gene){
  return `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(gene)}%5Bgene%5D`;
}
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
      <a href="${SOPHIA_URL}" target="_blank" class="btn-link" onclick="event.stopPropagation()" title="Open in SOPHiA DDM™">🔗 SOPHiA DDM</a>
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
      <div class="section-title">Variant Priority Ranking <span style="font-size:.72rem;color:var(--text3);font-weight:400;margin-left:.5rem">Top ${Math.min(c.scored_variants?.length||0, 50)} of ${c.total_variants}</span></div>
      <div style="overflow-x:auto"><table class="vtable">
       <thead><tr><th>#</th><th>Gene</th><th>HGVS</th><th>Conseq.</th><th>ABCD</th><th>Act.</th><th>Urg.</th><th>QA</th><th>gnomAD</th><th>ClinVar</th><th>Score</th><th>Flags</th><th>Links</th></tr></thead>
       <tbody>${(c.scored_variants||[]).slice(0,50).map((v,vi)=>`<tr>
        <td><span class="tier-dot" style="background:${mColor(v.composite_score)}"></span>${vi+1}</td>
        <td><a href="${clinvarUrl(v.gene)}" target="_blank" class="gene-link" title="View ${v.gene} on ClinVar"><strong>${v.gene}</strong></a></td><td style="font-family:monospace;font-size:.72rem">${v.hgvs||''}</td>
        <td>${v.consequence||''}</td><td><strong>${v.abcd||''}</strong></td>
        <td style="color:${mColor(v.actionability)}">${v.actionability}</td>
        <td style="color:${mColor(v.disease_urgency)}">${v.disease_urgency}</td>
        <td style="color:${mColor(v.qa_confidence)}">${v.qa_confidence}</td>
        <td style="color:${mColor(v.gnomad_score)}">${v.gnomad_score}</td>
        <td style="color:${mColor(v.clinvar_score)}">${v.clinvar_score}</td>
        <td><strong>${v.composite_score}</strong></td>
        <td>${(v.flags||[]).map(f=>`<span class="tag tag-flag">${f}</span>`).join(' ')}</td>
        <td><button class="btn-papers" onclick="event.stopPropagation();openPapersModal('${v.gene}','${(v.hgvs||'').replace(/'/g,'')}','${(v.consequence||'').replace(/'/g,'')}')" title="Find papers about ${v.gene} ${v.hgvs||''}">📚</button></td>

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
