/* แดชบอร์ดกรองได้บนหน้าภาพรวมข้อมูล (9 ต.ค. 2569)
   ข้อมูลมาจากเซิร์ฟเวอร์ใน <script id="exploreData"> = ตัวเลขนับรวม 12 กลุ่ม (เพศ × การมีรถ × ประเภทที่สนใจ)
   ไม่มีข้อมูลรายบุคคล · ห้ามพิมพ์ตัวเลขข้อมูลลงในไฟล์นี้ */
(function () {
  var root = document.getElementById('explore');
  var raw = document.getElementById('exploreData');
  if (!root || !raw) return;
  var D;
  try { D = JSON.parse(raw.textContent); } catch (e) { return; }

  var FUELS = D.dims.fuel;                               // ICE, Hybrid, EV
  var FTH = { ICE: 'สันดาป (ICE)', Hybrid: 'ไฮบริด (HEV)', EV: 'ไฟฟ้า (EV)' };
  var BUY_TH = { 'ซื้อ': 'มีแนวโน้มจะซื้อ', 'ไม่ซื้อ': 'ยังไม่มีแนวโน้มจะซื้อ' };
  var $ = function (id) { return document.getElementById(id); };
  var selG = $('fGender'), selC = $('fCar'), selF = $('fFuel');
  var css = getComputedStyle(document.documentElement);
  var v = function (n) { return css.getPropertyValue(n).trim(); };
  var COLOR = { ICE: v('--ice'), Hybrid: v('--hev'), EV: v('--ev') };
  var haveChart = typeof Chart !== 'undefined';
  var charts = {};

  function pick() {
    return D.groups.filter(function (g) {
      return (!selG.value || g.gender === selG.value) && (!selC.value || g.car === selC.value) && (!selF.value || g.fuel === selF.value);
    });
  }
  function sum(arr, f) { return arr.reduce(function (a, g) { return a + f(g); }, 0); }
  function pct(a, b) { return b ? (a * 100 / b).toFixed(1) + '%' : '—'; }
  function perFuel(groups, f) { return groups.filter(function (g) { return g.fuel === f; }); }
  // axis = age | income | budget | buy → [fuel][label] = จำนวนคน
  function matrix(groups, axis) {
    return FUELS.map(function (f) {
      var gs = perFuel(groups, f), n = D.labels[axis].length, out = [];
      for (var i = 0; i < n; i++) out.push(sum(gs, function (g) { return g[axis][i]; }));
      return out;
    });
  }

  // ป้ายแกนสั้นลงให้พอดีมือถือ (ตารางสำหรับผู้อ่านหน้าจอยังใช้ป้ายเต็ม)
  function short(l) { return String(l).replace(' บาท', ''); }

  function fillTable(id, caption, rowLabels, mat) {
    var t = $(id); if (!t) return;
    var h = '<caption>' + caption + '</caption><thead><tr><th scope="col">กลุ่ม</th>' +
      FUELS.map(function (f) { return '<th scope="col">' + FTH[f] + '</th>'; }).join('') + '</tr></thead><tbody>';
    rowLabels.forEach(function (lab, i) {
      h += '<tr><th scope="row">' + lab + '</th>' + FUELS.map(function (f, j) { return '<td>' + mat[j][i] + ' คน</td>'; }).join('') + '</tr>';
    });
    t.innerHTML = h + '</tbody>';
  }

  function stacked(key, el, labels, mat, asPercent, horizontal) {
    var totals = labels.map(function (_, i) { return mat.reduce(function (a, row) { return a + row[i]; }, 0); });
    var ds = FUELS.map(function (f, j) {
      return { label: FTH[f], backgroundColor: COLOR[f], borderWidth: 0, maxBarThickness: 30,
        data: labels.map(function (_, i) { return asPercent ? (totals[i] ? mat[j][i] * 100 / totals[i] : 0) : mat[j][i]; }),
        counts: mat[j] };
    });
    var valAxis = { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,.12)' }, ticks: { precision: 0 } };
    var catAxis = { stacked: true, grid: { display: false } };
    if (asPercent) valAxis.max = 100;
    var cfg = {
      type: 'bar',
      data: { labels: labels, datasets: ds },
      options: { indexAxis: horizontal ? 'y' : 'x', responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
        scales: horizontal ? { x: valAxis, y: catAxis } : { x: catAxis, y: valAxis },
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
          tooltip: { callbacks: { label: function (c) {
            var n = c.dataset.counts[c.dataIndex];
            return c.dataset.label + ': ' + n + ' คน' + (asPercent ? ' (' + c.parsed[horizontal ? 'x' : 'y'].toFixed(1) + '%)' : ''); } } } } }
    };
    if (charts[key]) { charts[key].data = cfg.data; charts[key].update(); }
    else if (haveChart && $(el)) charts[key] = new Chart($(el), cfg);
  }

  function render() {
    var gs = pick(), n = sum(gs, function (g) { return g.n; });
    var car = sum(gs, function (g) { return g.car === 'มี' ? g.n : 0; });
    var buyIdx = D.labels.buy.indexOf('ซื้อ');
    var buy = sum(gs, function (g) { return g.buy[buyIdx]; });
    var byFuel = {}; FUELS.forEach(function (f) { byFuel[f] = sum(perFuel(gs, f), function (g) { return g.n; }); });
    $('kN').textContent = n.toLocaleString('th-TH');
    $('kCar').textContent = pct(car, n);
    $('kBuy').textContent = pct(buy, n);
    FUELS.forEach(function (f) { $('k' + f).textContent = pct(byFuel[f], n); });
    var names = [];
    if (selG.value) names.push('เพศ' + selG.value);
    if (selC.value) names.push(selC.value === 'มี' ? 'มีรถอยู่แล้ว' : 'ยังไม่มีรถ');
    if (selF.value) names.push('สนใจรถ' + FTH[selF.value]);
    $('exStatus').textContent = (names.length ? 'กลุ่มที่เลือก: ' + names.join(' · ') : 'กลุ่มที่เลือก: ผู้ตอบทั้งหมด') + ' — ' + n.toLocaleString('th-TH') + ' คน';

    // โดนัท
    var dl = FUELS.map(function (f) { return FTH[f]; }), dd = FUELS.map(function (f) { return byFuel[f]; });
    $('exDonutTable').querySelector('tbody').innerHTML = FUELS.map(function (f) { return '<tr><th scope="row">' + FTH[f] + '</th><td>' + byFuel[f] + ' คน</td></tr>'; }).join('');
    var dcfg = { type: 'doughnut', data: { labels: dl, datasets: [{ data: dd, backgroundColor: FUELS.map(function (f) { return COLOR[f]; }), borderColor: v('--night'), borderWidth: 3 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '62%', animation: { duration: 250 },
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
          tooltip: { callbacks: { label: function (c) { return c.label + ': ' + c.parsed + ' คน (' + (n ? (c.parsed * 100 / n).toFixed(1) : 0) + '%)'; } } } } } };
    if (charts.donut) { charts.donut.data = dcfg.data; charts.donut.update(); }
    else if (haveChart && $('exDonut')) charts.donut = new Chart($('exDonut'), dcfg);

    var mi = matrix(gs, 'income'), ma = matrix(gs, 'age'), mb = matrix(gs, 'budget'), my = matrix(gs, 'buy');
    var buyLabels = D.labels.buy.map(function (b) { return BUY_TH[b] || b; });
    // เลือกประเภทเดียว = ทุกแท่งเต็มร้อยละ ไม่มีความหมาย → แสดงเป็นจำนวนคนแทน (Codex #61)
    var pctMode = !selF.value;
    stacked('income', 'exIncome', D.labels.income.map(short), mi, pctMode, true);
    stacked('age', 'exAge', D.labels.age, ma, pctMode, true);
    stacked('budget', 'exBudget', D.labels.budget.map(short), mb, false, false);
    stacked('buy', 'exBuy', buyLabels, my, pctMode, true);
    var units = document.querySelectorAll('#explore .ex-unit');
    for (var u = 0; u < units.length; u++) units[u].textContent = pctMode ? '(ร้อยละ)' : '(คน)';
    fillTable('exIncomeTable', 'จำนวนผู้ตอบแยกตามรายได้ต่อเดือนและประเภทที่สนใจ', D.labels.income, mi);
    fillTable('exAgeTable', 'จำนวนผู้ตอบแยกตามช่วงอายุและประเภทที่สนใจ', D.labels.age, ma);
    fillTable('exBudgetTable', 'จำนวนผู้ตอบแยกตามงบประมาณและประเภทที่สนใจ', D.labels.budget, mb);
    fillTable('exBuyTable', 'จำนวนผู้ตอบแยกตามแนวโน้มการซื้อและประเภทที่สนใจ', buyLabels, my);
  }

  [selG, selC, selF].forEach(function (s) { s.addEventListener('change', render); });
  $('fReset').addEventListener('click', function () { selG.value = selC.value = selF.value = ''; render(); selG.focus(); });
  render();
})();
