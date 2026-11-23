(function () {
  const files = document.getElementById('epub-files');
  if (files) files.addEventListener('change', () => {
    document.getElementById('files-label').textContent = Array.from(files.files).map(x=>x.name).join(', ') || 'Chưa chọn EPUB';
  });
  if(files){
    const drop = files.closest('.drop-zone');
    drop.addEventListener('dragover', e=>{e.preventDefault();drop.classList.add('drag-over');});
    drop.addEventListener('dragleave',()=>drop.classList.remove('drag-over'));
    drop.addEventListener('drop', e=>{e.preventDefault();drop.classList.remove('drag-over');if(e.dataTransfer.files.length){files.files=e.dataTransfer.files;files.dispatchEvent(new Event('change'));}});
  }
  const bookFilter = document.getElementById('filter-books');
  if(bookFilter) bookFilter.addEventListener('input',()=>{
    const q=bookFilter.value.trim().toLocaleLowerCase('vi');
    document.querySelectorAll('.book-card').forEach(el=>{el.hidden=!(el.dataset.filter || '').includes(q);});
  });
  const query = document.getElementById('query');
  if (!query) return;
  const results = document.getElementById('search-results'), stats = document.getElementById('search-stats');
  const prev = document.getElementById('prev-page'), next = document.getElementById('next-page');
  const pageLabel = document.getElementById('page-number');
  const params = new URLSearchParams(location.search);
  query.value = params.get('q') || '';
  if(['all','source','distilled'].includes(params.get('scope'))) document.getElementById('search-scope').value=params.get('scope');
  let page = 1, timer = null, controller = null, requestId = 0;
  const escape = x => String(x == null ? '' : x).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function displaySnippet(text) {
    return escape(text).replaceAll('⟦','<mark>').replaceAll('⟧','</mark>');
  }
  async function update() {
    const q = query.value.trim();
    const mode = document.querySelector('[name="mode"]:checked').value;
    const scope = document.getElementById('search-scope').value;
    if (!q) { results.innerHTML='<div class="empty">Nhập từ khóa hoặc cụm từ để tìm.</div>';stats.textContent='';prev.hidden=next.hidden=true;pageLabel.textContent='';return; }
    if (controller) controller.abort();controller = new AbortController();const id = ++requestId;
    const u = new URLSearchParams({q,mode,scope,page:String(page),per_page:'20'});
    if (params.has('book_id')) u.set('book_id',params.get('book_id'));
    history.replaceState(null,'','/search?'+u.toString());
    stats.textContent='Đang tìm…';
    try {
      const response = await fetch('/api/search?'+u.toString(),{signal:controller.signal});
      if (!response.ok) throw new Error('HTTP '+response.status);
      const data = await response.json();if(id!==requestId)return;
      stats.textContent=`${data.total} kết quả · Trang ${data.page}`;
      if (!data.items.length) results.innerHTML='<div class="empty">Không tìm thấy kết quả trong nội dung đã lập chỉ mục.</div>';
      else results.innerHTML=data.items.map(x=>`<div class="result"><h3><a href="${escape(x.detail_url)}">${escape(x.unit_title)}</a></h3><p class="meta"><b>${x.kind === 'distilled' ? 'AI · code audit' : 'EPUB gốc'}</b> · <a href="/books/${encodeURIComponent(x.book_id)}">${escape(x.book_title)}</a> · ${escape(x.language || 'N/A')} · ${escape(x.source_href)}</p><p class="snippet">${displaySnippet(x.snippet)}</p></div>`).join('');
      prev.hidden=page<=1;next.hidden=page*20>=data.total;pageLabel.textContent=data.total?`Trang ${page}`:'';
    } catch(e) { if(e.name!=='AbortError') stats.textContent='Lỗi tìm kiếm: '+e.message; }
  }
  function schedule(){page=1;clearTimeout(timer);timer=setTimeout(update,200);}
  query.addEventListener('input',schedule);
  document.querySelectorAll('[name="mode"]').forEach(x=>x.addEventListener('change',schedule));
  document.getElementById('search-scope').addEventListener('change',schedule);
  prev.addEventListener('click',()=>{if(page>1){page--;update();}});
  next.addEventListener('click',()=>{page++;update();});
  if(query.value) update();
})();

// The dashboard's JSON endpoint is polled without starting new AI requests.
(function () {
  const statusEl = document.getElementById('run-live-state');
  if (!statusEl) return;
  const runId = statusEl.dataset.runId;
  async function refresh() {
    try {
      const res = await fetch('/api/processing/runs/'+encodeURIComponent(runId),{cache:'no-store'});
      if (!res.ok) return;
      const run = await res.json();
      statusEl.textContent = run.state+(run.stop_reason ? ' ('+run.stop_reason+')' : '');
      const summary = document.getElementById('run-live-summary');
      const done=run.summary.completed, pending=run.summary.pending;
      summary.textContent = `Đạt code audit: ${done}/${run.jobs.length} · Đang chạy: ${run.summary.processing} · Chờ: ${pending} · Retry: ${run.summary.retry_waiting} · Cần kiểm tra: ${run.summary.needs_review} · Lỗi: ${run.summary.failed} · Chi phí ghi nhận: $${run.spent_usd.toFixed(5)}`;
      for (const job of run.jobs) {
        const el = document.getElementById('job-'+job.id);
        if(el) el.textContent=job.status;
      }
    } catch (_) { /* keep initial server-rendered values available */ }
  }
  refresh();
  const interval = setInterval(refresh, 2000);
  window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
})();
