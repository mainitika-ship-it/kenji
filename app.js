(() => {
  'use strict';

  const STORAGE_KEY = 'repair-intake-hoshihime-v1';
  const CONSULTATIONS_KEY = 'repair-intake-hoshihime-consultations-v1';
  const form = document.querySelector('#repair-form');
  const sections = [...document.querySelectorAll('.form-section')];
  const progressButtons = [...document.querySelectorAll('.progress-step')];
  const photoInputs = [...document.querySelectorAll('input[type="file"][data-photo]')];
  const summary = document.querySelector('#summary');
  const riskResult = document.querySelector('#risk-result');
  const validationMessage = document.querySelector('#validation-message');
  const draftStatus = document.querySelector('#draft-status');
  const consultationList = document.querySelector('#consultation-list');
  const objectUrls = new Map();

  let consultationId = createConsultationId();
  let saveTimer;

  function createConsultationId() {
    const now = new Date();
    const stamp = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0')
    ].join('');
    const random = Math.random().toString(36).slice(2, 6).toUpperCase();
    return `HS-${stamp}-${random}`;
  }

  function escapeHtml(value = '') {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function valuesFor(name) {
    return [...form.querySelectorAll(`[name="${CSS.escape(name)}"]:checked`)].map((input) => input.value);
  }

  function fieldValue(name) {
    const field = form.elements.namedItem(name);
    if (!field) return '';
    if (field instanceof RadioNodeList) return field.value || '';
    return field.value?.trim?.() ?? field.value ?? '';
  }

  function getPhotoMetadata() {
    return photoInputs.map((input) => ({
      label: input.dataset.photo,
      selected: Boolean(input.files?.length),
      fileName: input.files?.[0]?.name || ''
    }));
  }

  function collectData() {
    return {
      schemaVersion: 1,
      consultationId,
      updatedAt: new Date().toISOString(),
      productName: fieldValue('productName'),
      modelNumber: fieldValue('modelNumber'),
      problem: fieldValue('problem'),
      desiredOutcome: fieldValue('desiredOutcome'),
      environment: valuesFor('environment'),
      load: fieldValue('load'),
      risk: valuesFor('risk'),
      shippingOriginal: fieldValue('shippingOriginal'),
      photos: getPhotoMetadata()
    };
  }

  function serializableData() {
    const data = collectData();
    data.photos = data.photos.map(({ label, selected, fileName }) => ({ label, selected, fileName }));
    return data;
  }

  function saveDraft() {
    const data = serializableData();
    // Browsers do not persist the image bytes. Only the text and photo slot status are saved.
    data.photos = data.photos.map(({ label }) => ({ label, selected: false, fileName: '' }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    draftStatus.textContent = '端末に保存済み';
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      draftStatus.textContent = '下書き';
    }, 1800);
  }

  function readConsultations() {
    try {
      const items = JSON.parse(localStorage.getItem(CONSULTATIONS_KEY) || '[]');
      return Array.isArray(items) ? items : [];
    } catch (error) {
      console.warn('保存済み相談を読み込めませんでした。', error);
      return [];
    }
  }

  function writeConsultations(items) {
    localStorage.setItem(CONSULTATIONS_KEY, JSON.stringify(items));
  }

  function formatSavedDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '日時不明';
    return new Intl.DateTimeFormat('ja-JP', {
      year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(date);
  }

  function renderConsultationList() {
    const items = readConsultations().sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
    if (!items.length) {
      consultationList.innerHTML = '<p class="consultation-empty">まだ登録された相談はありません。</p>';
      return;
    }

    consultationList.innerHTML = items.map((item) => `
      <article class="consultation-item">
        <div>
          <strong>${escapeHtml(item.productName || '製品名未入力')}</strong>
          <span>${escapeHtml(item.consultationId)}</span>
          <small>更新：${escapeHtml(formatSavedDate(item.updatedAt))}</small>
        </div>
        <div class="consultation-actions">
          <button class="secondary compact-button" type="button" data-open-consultation="${escapeHtml(item.consultationId)}">開く</button>
          <button class="danger-compact" type="button" data-delete-consultation="${escapeHtml(item.consultationId)}">削除</button>
        </div>
      </article>
    `).join('');
  }

  function clearPhotoPreviews() {
    objectUrls.forEach((url) => URL.revokeObjectURL(url));
    objectUrls.clear();
    photoInputs.forEach((input) => { input.value = ''; });
    document.querySelectorAll('.photo-slot').forEach((slot) => {
      slot.classList.remove('has-image');
      const image = slot.querySelector('img');
      image.hidden = true;
      image.removeAttribute('src');
    });
  }

  function applyConsultationData(data) {
    form.reset();
    clearPhotoPreviews();
    consultationId = data.consultationId || createConsultationId();
    ['productName', 'modelNumber', 'problem', 'desiredOutcome', 'shippingOriginal'].forEach((name) => {
      const field = form.elements.namedItem(name);
      if (field && typeof data[name] === 'string') field.value = data[name];
    });

    [...(data.environment || [])].forEach((value) => {
      const input = [...form.querySelectorAll('[name="environment"]')].find((item) => item.value === value);
      if (input) input.checked = true;
    });
    if (data.load) {
      const input = [...form.querySelectorAll('[name="load"]')].find((item) => item.value === data.load);
      if (input) input.checked = true;
    }
    [...(data.risk || [])].forEach((value) => {
      const input = [...form.querySelectorAll('[name="risk"]')].find((item) => item.value === value);
      if (input) input.checked = true;
    });
    renderSummary();
  }

  function scheduleSave() {
    draftStatus.textContent = '保存中…';
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 350);
  }

  function restoreDraft() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    try {
      const data = JSON.parse(raw);
      applyConsultationData(data);

      draftStatus.textContent = '前回の下書きを復元';
      setTimeout(() => { draftStatus.textContent = '下書き'; }, 2200);
    } catch (error) {
      console.warn('下書きを復元できませんでした。', error);
    }
  }

  function formatList(items, empty = '未回答') {
    return items.length ? items.join('、') : empty;
  }

  function assessRisk(data) {
    const materialRisks = data.risk.filter((item) => item !== '該当なし');
    if (materialRisks.length) {
      return {
        level: 'high',
        title: '慎重確認が必要です',
        message: '安全に関係する可能性があります。3Dプリントだけに荷重を任せず、現物確認・金属部品の併用・試験方法を先に決めます。'
      };
    }

    const moderate = data.load === '物を支える・引っ張る'
      || data.environment.some((item) => ['直射日光', '屋外・雨', '車内', '高温付近'].includes(item));

    if (moderate) {
      return {
        level: 'medium',
        title: '材料と耐久試験を確認します',
        message: '直射日光・熱・荷重があるため、PLAの完成品は避け、ASAなどの候補と印刷方向を検討します。'
      };
    }

    return {
      level: 'low',
      title: '通常確認から始められそうです',
      message: '写真と寸法を確認し、まず安価な試作品から進めます。最終的な製作可否は現物条件を見て判断します。'
    };
  }

  function summaryBlock(title, value, empty = '未回答') {
    const content = value && String(value).trim() ? escapeHtml(value) : `<span class="summary-empty">${escapeHtml(empty)}</span>`;
    return `<section class="summary-block"><h3>${escapeHtml(title)}</h3><p>${content}</p></section>`;
  }

  function renderSummary() {
    const data = collectData();
    const selectedPhotos = data.photos.filter((photo) => photo.selected);
    const risk = assessRisk(data);

    riskResult.hidden = false;
    riskResult.classList.toggle('is-low', risk.level === 'low');
    riskResult.innerHTML = `<strong>${escapeHtml(risk.title)}</strong><br><span>${escapeHtml(risk.message)}</span>`;

    const photoItems = data.photos.map((photo) =>
      `<li>${photo.selected ? '✓' : '○'} ${escapeHtml(photo.label)}${photo.fileName ? `：${escapeHtml(photo.fileName)}` : ''}</li>`
    ).join('');

    summary.innerHTML = `
      <section class="summary-block">
        <h3>相談番号</h3>
        <p>${escapeHtml(data.consultationId)}</p>
      </section>
      ${summaryBlock('製品', [data.productName, data.modelNumber].filter(Boolean).join('／'))}
      ${summaryBlock('壊れ方', data.problem)}
      ${summaryBlock('直したい状態', data.desiredOutcome)}
      ${summaryBlock('使用環境', formatList(data.environment))}
      ${summaryBlock('かかる力', data.load)}
      ${summaryBlock('安全確認', formatList(data.risk))}
      ${summaryBlock('元部品の郵送', data.shippingOriginal)}
      <section class="summary-block">
        <h3>写真</h3>
        <p>${selectedPhotos.length}／4枚を選択</p>
        <ul class="summary-list">${photoItems}</ul>
      </section>
    `;
  }

  function validationErrors() {
    const data = collectData();
    const errors = [];
    const photoCount = data.photos.filter((photo) => photo.selected).length;
    if (photoCount < 2) errors.push('写真を最低2枚選んでください。');
    if (!data.problem) errors.push('「どのように壊れましたか？」を入力してください。');
    return errors;
  }

  function validateAndShow() {
    const errors = validationErrors();
    validationMessage.hidden = errors.length === 0;
    validationMessage.innerHTML = errors.length
      ? `<strong>まだ不足があります</strong><ul>${errors.map((error) => `<li>${escapeHtml(error)}</li>`).join('')}</ul>`
      : '';
    return errors.length === 0;
  }

  function gotoSection(id) {
    const section = document.getElementById(id);
    if (!section) return;
    renderSummary();
    if (id === 'review') validateAndShow();
    progressButtons.forEach((button) => button.classList.toggle('is-active', button.dataset.goto === id));
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function consultationText() {
    const data = collectData();
    const risk = assessRisk(data);
    return [
      '【写真で補修部品相談】',
      `相談番号：${data.consultationId}`,
      `製品名：${data.productName || '不明'}`,
      `型番：${data.modelNumber || '不明'}`,
      `壊れ方：${data.problem || '未入力'}`,
      `直したい状態：${data.desiredOutcome || '未回答'}`,
      `使用環境：${formatList(data.environment)}`,
      `かかる力：${data.load || '未回答'}`,
      `安全確認：${formatList(data.risk)}`,
      `元部品の郵送：${data.shippingOriginal || '未回答'}`,
      `写真：${data.photos.filter((photo) => photo.selected).length}／4枚`,
      `一次判定：${risk.title}`,
      '',
      '※写真ファイルはこの文章には添付されません。メール画面で写真を追加してください。'
    ].join('\n');
  }

  async function copySummary() {
    const okay = validateAndShow();
    if (!okay) {
      showToast('不足項目を確認してください');
      return;
    }
    try {
      await navigator.clipboard.writeText(consultationText());
      showToast('相談内容をコピーしました');
    } catch {
      const temporary = document.createElement('textarea');
      temporary.value = consultationText();
      temporary.style.position = 'fixed';
      temporary.style.opacity = '0';
      document.body.appendChild(temporary);
      temporary.select();
      document.execCommand('copy');
      temporary.remove();
      showToast('相談内容をコピーしました');
    }
  }

  function openEmailDraft() {
    if (!validateAndShow()) {
      showToast('不足項目を確認してください');
      return;
    }
    const data = collectData();
    const subject = `補修部品相談 ${data.consultationId} ${data.productName || ''}`.trim();
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(consultationText())}`;
  }

  function downloadJson() {
    const data = serializableData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${data.consultationId}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showToast('整理票を保存しました');
  }

  function saveConsultation() {
    if (!validateAndShow()) {
      gotoSection('review');
      showToast('不足項目を確認してください');
      return;
    }
    const data = serializableData();
    data.photos = data.photos.map(({ label, selected, fileName }) => ({ label, selected, fileName }));
    const items = readConsultations();
    const existingIndex = items.findIndex((item) => item.consultationId === data.consultationId);
    if (existingIndex >= 0) items[existingIndex] = data;
    else items.push(data);
    writeConsultations(items);
    saveDraft();
    renderConsultationList();
    showToast(existingIndex >= 0 ? '相談を更新しました' : '相談を登録しました');
  }

  function startNewConsultation() {
    const confirmed = window.confirm('新しい相談を始めます。現在の入力を登録していない場合は失われます。よろしいですか？');
    if (!confirmed) return;
    form.reset();
    clearPhotoPreviews();
    localStorage.removeItem(STORAGE_KEY);
    consultationId = createConsultationId();
    validationMessage.hidden = true;
    draftStatus.textContent = '新しい下書き';
    renderSummary();
    gotoSection('photos');
    showToast('新しい相談を開始しました');
  }

  function openConsultation(id) {
    const item = readConsultations().find((consultation) => consultation.consultationId === id);
    if (!item) {
      showToast('相談が見つかりません');
      renderConsultationList();
      return;
    }
    applyConsultationData(item);
    saveDraft();
    gotoSection('details');
    showToast('相談を開きました。写真は再選択してください');
  }

  function deleteConsultation(id) {
    const item = readConsultations().find((consultation) => consultation.consultationId === id);
    if (!item) return;
    const name = item.productName || item.consultationId;
    if (!window.confirm(`「${name}」を保存済み一覧から削除します。よろしいですか？`)) return;
    writeConsultations(readConsultations().filter((consultation) => consultation.consultationId !== id));
    renderConsultationList();
    showToast('保存済み相談を削除しました');
  }

  function showToast(message) {
    let toast = document.querySelector('.toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast';
      toast.setAttribute('role', 'status');
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toast.hideTimer);
    toast.hideTimer = setTimeout(() => toast.classList.remove('is-visible'), 2200);
  }

  function resetAll() {
    const confirmed = window.confirm('入力内容と写真の選択をすべて消します。よろしいですか？');
    if (!confirmed) return;
    form.reset();
    localStorage.removeItem(STORAGE_KEY);
    consultationId = createConsultationId();
    clearPhotoPreviews();
    validationMessage.hidden = true;
    renderSummary();
    gotoSection('photos');
    showToast('入力を消しました');
  }

  function enforceRiskExclusivity(changedInput) {
    if (changedInput.name !== 'risk' || !changedInput.checked) return;
    const riskInputs = [...form.querySelectorAll('[name="risk"]')];
    if (changedInput.dataset.exclusive !== undefined) {
      riskInputs.forEach((input) => { if (input !== changedInput) input.checked = false; });
    } else {
      const exclusive = riskInputs.find((input) => input.dataset.exclusive !== undefined);
      if (exclusive) exclusive.checked = false;
    }
  }

  photoInputs.forEach((input) => {
    input.addEventListener('change', () => {
      const slot = input.closest('.photo-slot');
      const image = slot.querySelector('img');
      const file = input.files?.[0];
      const previous = objectUrls.get(input.name);
      if (previous) URL.revokeObjectURL(previous);

      if (file) {
        const url = URL.createObjectURL(file);
        objectUrls.set(input.name, url);
        image.src = url;
        image.hidden = false;
        slot.classList.add('has-image');
      } else {
        image.hidden = true;
        image.removeAttribute('src');
        slot.classList.remove('has-image');
      }
      renderSummary();
    });
  });

  form.addEventListener('input', (event) => {
    enforceRiskExclusivity(event.target);
    scheduleSave();
    renderSummary();
  });
  form.addEventListener('change', (event) => {
    enforceRiskExclusivity(event.target);
    scheduleSave();
    renderSummary();
  });

  document.querySelectorAll('[data-next]').forEach((button) => button.addEventListener('click', () => gotoSection(button.dataset.next)));
  document.querySelectorAll('[data-back]').forEach((button) => button.addEventListener('click', () => gotoSection(button.dataset.back)));
  progressButtons.forEach((button) => button.addEventListener('click', () => gotoSection(button.dataset.goto)));
  document.querySelector('#copy-summary').addEventListener('click', copySummary);
  document.querySelector('#email-draft').addEventListener('click', openEmailDraft);
  document.querySelector('#download-json').addEventListener('click', downloadJson);
  document.querySelector('#save-consultation').addEventListener('click', saveConsultation);
  document.querySelector('#new-consultation').addEventListener('click', startNewConsultation);
  document.querySelector('#reset-form').addEventListener('click', resetAll);
  consultationList.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-consultation]');
    if (openButton) openConsultation(openButton.dataset.openConsultation);
    const deleteButton = event.target.closest('[data-delete-consultation]');
    if (deleteButton) deleteConsultation(deleteButton.dataset.deleteConsultation);
  });

  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    progressButtons.forEach((button) => button.classList.toggle('is-active', button.dataset.goto === visible.target.id));
  }, { rootMargin: '-18% 0px -62% 0px', threshold: [0.05, 0.25, 0.5] });
  sections.forEach((section) => observer.observe(section));

  restoreDraft();
  renderConsultationList();
  renderSummary();
})();
