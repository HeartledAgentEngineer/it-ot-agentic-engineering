import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update Mix Tour DD Logic
mix_dd_js = """function _populateMixTourDD(data, listEl) {
  const pills   = document.getElementById('mix-tour-dd-pills');
  let applyBtn  = document.getElementById('mix-tour-apply');
  if (!applyBtn) {
    applyBtn = document.createElement('button');
    applyBtn.id = 'mix-tour-apply';
    applyBtn.textContent = 'Anwenden';
    applyBtn.style.cssText = 'display:none;margin-top:8px;width:100%;padding:6px;background:#24b24e;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:11px;';
    document.getElementById('mix-tour-dd').appendChild(applyBtn);
  }
  applyBtn.style.display = 'none';
  const current = listEl.dataset.tourName || '';
  
  if (data.error === 'rate_limited') {
    pills.innerHTML = '<div style="color:#f9c74f;font-size:11px;">Rate-Limit aktiv</div>';
    return;
  }

  const opts = [];
  opts.push({ value: '__festival__', label: '🎪 Festival-Set', cls: 'festival' });
  if (data.active_tour) {
    const t = data.active_tour;
    opts.push({ value: t.name, label: `🎸 ${t.name} · ${t.shows} Sets`, cls: 'active' });
  }
  (data.past_tours || []).slice(0, 3).forEach(t => {
    const yr = (t.from || '').slice(0, 4);
    opts.push({ value: t.name, label: `${t.name} · ${t.shows} Sets${yr ? ' · ' + yr : ''}`, cls: '' });
  });
  opts.push({ value: '__concert__', label: '🎵 Konzert (geschätzt)', cls: 'concert' });
  opts.push({ value: '__best_of__', label: '⭐ Best-of', cls: 'best-of' });

  let selectedTours = new Set();
  if (current && !current.startsWith('__')) {
      current.split('|').forEach(t => selectedTours.add(t));
  } else if (current) {
      selectedTours.add(current);
  }

  pills.innerHTML = opts.map(o => {
    const isSelected = selectedTours.has(o.value);
    const sel = isSelected ? ' style="border-width:2px;border-color:#1db954;" class="tour-pill selected"' : ' class="tour-pill"';
    const v = (o.value || '').replace(/"/g, '&quot;');
    const l = (o.label || '').replace(/"/g, '&quot;');
    return `<div${sel} data-tv="${v}" data-tl="${l}">${o.label}</div>`;
  }).join('');

  pills.onclick = e => {
    const pill = e.target.closest('[data-tv]');
    if (!pill) return;
    const v = pill.dataset.tv;
    
    if (v.startsWith('__')) {
      selectMixTour(v, pill.dataset.tl);
    } else {
      pill.classList.toggle('selected');
      if (pill.classList.contains('selected')) {
        pill.style.borderWidth = '2px'; pill.style.borderColor = '#1db954';
        selectedTours.add(v);
      } else {
        pill.style.borderWidth = '1px'; pill.style.borderColor = 'rgba(255,255,255,0.15)';
        selectedTours.delete(v);
      }
      Array.from(pills.children).forEach(c => {
         if (c.dataset.tv && c.dataset.tv.startsWith('__')) {
            c.classList.remove('selected');
            c.style.borderWidth = '1px'; c.style.borderColor = 'rgba(255,255,255,0.15)';
            selectedTours.delete(c.dataset.tv);
         }
      });
      if (selectedTours.size > 0) {
        applyBtn.style.display = 'block';
        applyBtn.onclick = () => {
          selectMixTour(Array.from(selectedTours).join('|'), "Multi-Tour");
        };
      } else {
        applyBtn.style.display = 'none';
      }
    }
  };
}"""

html = re.sub(r'function _populateMixTourDD\(data, listEl\) \{.*?\n\}', mix_dd_js, html, flags=re.DOTALL)

# 2. Update Abend tab logic
html = html.replace("""<select id="abend-tour-select" style="display:none;background:#111;border:1px solid #333;border-radius:6px;color:#888;font-size:10px;padding:3px 6px;cursor:pointer;max-width:160px;" onchange="abendOnTourSelectChange()">
            </select>""", """<button id="abend-tour-select-btn" style="display:none;background:#111;border:1px solid #333;border-radius:6px;color:#888;font-size:10px;padding:3px 6px;cursor:pointer;" onclick="openAbendTourDD(event, this)">Tour wählen ▾</button>""")

abend_js = """function _abendFillTourDropdown(selectedValue) {
  const btn = document.getElementById('abend-tour-select-btn');
  if (!btn || !_abendTourOptions.length) return;
  btn.style.display = 'inline-block';
  if (selectedValue && selectedValue !== '__best_of__') {
      btn.textContent = 'Multi-Tour ▾';
  } else if (selectedValue === '__best_of__') {
      btn.textContent = '⭐ Best-of ▾';
  }
}

function openAbendTourDD(event, btn) {
  const dd = document.getElementById('mix-tour-dd');
  const pills = document.getElementById('mix-tour-dd-pills');
  
  const rect = btn.getBoundingClientRect();
  dd.style.top = (rect.bottom + 6) + 'px';
  dd.style.left = Math.max(4, rect.left - 40) + 'px';
  dd.style.display = 'block';

  document.removeEventListener('click', _mixTourOutsideClick);
  setTimeout(() => document.addEventListener('click', _mixTourOutsideClick), 50);

  let applyBtn = document.getElementById('mix-tour-apply');
  if (!applyBtn) {
    applyBtn = document.createElement('button');
    applyBtn.id = 'mix-tour-apply';
    applyBtn.textContent = 'Anwenden';
    applyBtn.style.cssText = 'display:none;margin-top:8px;width:100%;padding:6px;background:#24b24e;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:11px;';
    dd.appendChild(applyBtn);
  }
  applyBtn.style.display = 'none';

  let selectedTours = new Set();
  const current = _abendSelectedTour || '';
  if (current && !current.startsWith('__')) {
      current.split('|').forEach(t => selectedTours.add(t));
  } else if (current) {
      selectedTours.add(current);
  }

  const opts = _abendTourOptions.filter(o => o.value !== '__festival__' && o.value !== '__concert__');
  
  pills.innerHTML = opts.map(o => {
    const isSelected = selectedTours.has(o.value);
    const sel = isSelected ? ' style="border-width:2px;border-color:#1db954;" class="tour-pill selected"' : ' class="tour-pill"';
    const v = (o.value || '').replace(/"/g, '&quot;');
    const l = (o.label || '').replace(/"/g, '&quot;');
    return `<div${sel} data-tv="${v}" data-tl="${l}">${o.label}</div>`;
  }).join('');

  pills.onclick = e => {
    const pill = e.target.closest('[data-tv]');
    if (!pill) return;
    const v = pill.dataset.tv;
    
    if (v.startsWith('__')) {
      _abendSelectedTour = v;
      btn.textContent = pill.dataset.tl + ' ▾';
      dd.style.display = 'none';
      abendOnTourSelectChange();
    } else {
      pill.classList.toggle('selected');
      if (pill.classList.contains('selected')) {
        pill.style.borderWidth = '2px'; pill.style.borderColor = '#1db954';
        selectedTours.add(v);
      } else {
        pill.style.borderWidth = '1px'; pill.style.borderColor = 'rgba(255,255,255,0.15)';
        selectedTours.delete(v);
      }
      
      Array.from(pills.children).forEach(c => {
         if (c.dataset.tv && c.dataset.tv.startsWith('__')) {
            c.classList.remove('selected');
            c.style.borderWidth = '1px'; c.style.borderColor = 'rgba(255,255,255,0.15)';
            selectedTours.delete(c.dataset.tv);
         }
      });

      if (selectedTours.size > 0) {
        applyBtn.style.display = 'block';
        applyBtn.onclick = () => {
          _abendSelectedTour = Array.from(selectedTours).join('|');
          btn.textContent = 'Multi-Tour ▾';
          dd.style.display = 'none';
          abendOnTourSelectChange();
        };
      } else {
        applyBtn.style.display = 'none';
      }
    }
  };
}"""

html = re.sub(r'function _abendFillTourDropdown\(selectedValue\) \{.*?\n\}', abend_js, html, flags=re.DOTALL)

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Updated index.html")
