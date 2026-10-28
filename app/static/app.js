// CanvasDL Mission Control Frontend Logic
(function () {
  'use strict';

  // State
  const state = {
    courses: [],
    activeTab: 'active', // 'active' | 'all'
    searchQuery: '',
    selectedCourse: null,
    viewMode: 'modules', // 'modules' | 'assignments' | 'files'
    courseModules: [],
    courseAssignments: [],
    courseFilesData: null,
    selectedFiles: new Map(), // key: file_id -> file object
    currentExtFilter: 'all',
    status: null,
    isDownloading: false,
    eventSource: null,
  };

  // SVG Icons Helper (Zero-dependency Crisp SVG)
  const icons = {
    file: `<svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
    assignment: `<svg class="w-4 h-4 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="m9 14 2 2 4-4"/></svg>`,
    pdf: `<svg class="w-4 h-4 text-red-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13v4"/><path d="M9 15h2a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1H9"/></svg>`,
    slide: `<svg class="w-4 h-4 text-orange-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
    doc: `<svg class="w-4 h-4 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
    sheet: `<svg class="w-4 h-4 text-emerald-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>`,
    zip: `<svg class="w-4 h-4 text-purple-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>`,
    folder: `<svg class="w-4 h-4 text-amber-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`,
    chevronDown: `<svg class="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`,
    chevronRight: `<svg class="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>`,
    download: `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
    star: `<svg class="w-3.5 h-3.5 text-amber-400 fill-amber-400 shrink-0" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
    check: `<svg class="w-3.5 h-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
  };

  function getFileIcon(filename = '') {
    const lower = filename.toLowerCase();
    if (lower.endsWith('.pdf')) return icons.pdf;
    if (lower.endsWith('.ppt') || lower.endsWith('.pptx')) return icons.slide;
    if (lower.endsWith('.doc') || lower.endsWith('.docx')) return icons.doc;
    if (lower.endsWith('.xls') || lower.endsWith('.xlsx') || lower.endsWith('.csv')) return icons.sheet;
    if (lower.endsWith('.zip') || lower.endsWith('.rar') || lower.endsWith('.7z')) return icons.zip;
    return icons.file;
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // DOM Elements
  const el = {
    userNameDisplay: document.getElementById('userNameDisplay'),
    diskFreeDisplay: document.getElementById('diskFreeDisplay'),
    downloadPathShort: document.getElementById('downloadPathShort'),
    openFolderBtn: document.getElementById('openFolderBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    courseSearchInput: document.getElementById('courseSearchInput'),
    tabActiveCourses: document.getElementById('tabActiveCourses'),
    tabAllCourses: document.getElementById('tabAllCourses'),
    activeCountBadge: document.getElementById('activeCountBadge'),
    allCountBadge: document.getElementById('allCountBadge'),
    coursesListContainer: document.getElementById('coursesListContainer'),
    courseHeaderSection: document.getElementById('courseHeaderSection'),
    courseTermBadge: document.getElementById('courseTermBadge'),
    courseCodeDisplay: document.getElementById('courseCodeDisplay'),
    courseTitleDisplay: document.getElementById('courseTitleDisplay'),
    courseTeachersDisplay: document.getElementById('courseTeachersDisplay'),
    openInCanvasLink: document.getElementById('openInCanvasLink'),
    downloadFullCourseBtn: document.getElementById('downloadFullCourseBtn'),
    viewModeModulesBtn: document.getElementById('viewModeModulesBtn'),
    viewModeAssignmentsBtn: document.getElementById('viewModeAssignmentsBtn'),
    viewModeFilesBtn: document.getElementById('viewModeFilesBtn'),
    courseItemsStats: document.getElementById('courseItemsStats'),
    selectAllBtn: document.getElementById('selectAllBtn'),
    deselectAllBtn: document.getElementById('deselectAllBtn'),
    courseExplorerContainer: document.getElementById('courseExplorerContainer'),
    emptySelectPrompt: document.getElementById('emptySelectPrompt'),
    batchDock: document.getElementById('batchDock'),
    selectedCountText: document.getElementById('selectedCountText'),
    selectedSizeText: document.getElementById('selectedSizeText'),
    dockTitle: document.getElementById('dockTitle'),
    dockSubtitle: document.getElementById('dockSubtitle'),
    dockProgressSection: document.getElementById('dockProgressSection'),
    downloadProgressBar: document.getElementById('downloadProgressBar'),
    downloadProgressPercentage: document.getElementById('downloadProgressPercentage'),
    downloadProgressCount: document.getElementById('downloadProgressCount'),
    startDownloadBtn: document.getElementById('startDownloadBtn'),
    startDownloadBtnLabel: document.getElementById('startDownloadBtnLabel'),
    cancelDownloadBtn: document.getElementById('cancelDownloadBtn'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettingsModalBtn: document.getElementById('closeSettingsModalBtn'),
    closeSettingsModalBtn2: document.getElementById('closeSettingsModalBtn2'),
    settingsDownloadDirInput: document.getElementById('settingsDownloadDirInput'),
    settingsSaveDirBtn: document.getElementById('settingsSaveDirBtn'),
    settingsAutoOpenCheckbox: document.getElementById('settingsAutoOpenCheckbox'),
    settingsTokenInput: document.getElementById('settingsTokenInput'),
    settingsSaveTokenBtn: document.getElementById('settingsSaveTokenBtn'),
  };

  // Initialization
  async function init() {
    setupEventListeners();
    await fetchStatus();
    await fetchCourses();
    initSSE();
  }

  // Fetch System Status
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      state.status = data;

      if (data.authenticated && data.user) {
        el.userNameDisplay.textContent = data.user.name || 'Conectado a Canvas';
        const userInit = document.getElementById('userInitialDisplay');
        if (userInit && data.user.name) {
          userInit.textContent = data.user.name.trim().charAt(0).toUpperCase();
        }
      } else {
        el.userNameDisplay.textContent = 'Sin sesión Canvas';
      }

      if (data.disk_free_gb) {
        el.diskFreeDisplay.textContent = `${data.disk_free_gb} GB`;
      }

      if (data.download_dir) {
        const parts = data.download_dir.split('/');
        el.downloadPathShort.textContent = parts[parts.length - 1] || 'CanvasDL';
        el.settingsDownloadDirInput.value = data.download_dir;
      }

      if (data.settings && data.settings.auto_open_folder !== undefined) {
        el.settingsAutoOpenCheckbox.checked = data.settings.auto_open_folder;
      }
    } catch (err) {
      console.error('Error cargando estado:', err);
      el.userNameDisplay.textContent = 'Error de conexión';
    }
  }

  // Fetch Courses
  async function fetchCourses() {
    try {
      const res = await fetch('/api/courses');
      const data = await res.json();
      state.courses = data.courses || [];

      const activeList = state.courses.filter(c => c.is_active);
      el.activeCountBadge.textContent = activeList.length;
      el.allCountBadge.textContent = state.courses.length;

      renderCoursesList();

      // Auto-select first active course if available
      if (activeList.length > 0 && !state.selectedCourse) {
        selectCourse(activeList[0]);
      }
    } catch (err) {
      console.error('Error cargando cursos:', err);
      el.coursesListContainer.innerHTML = `
        <div class="p-4 text-center text-red-400 text-xs">
          No se pudieron cargar los cursos. Verifica tu token o conexión de Canvas.
        </div>`;
    }
  }

  // Render Courses in Sidebar
  function renderCoursesList() {
    const q = state.searchQuery.toLowerCase().trim();
    let filtered = state.courses;

    if (state.activeTab === 'active') {
      filtered = filtered.filter(c => c.is_active);
    }

    if (q) {
      filtered = filtered.filter(c => 
        c.name.toLowerCase().includes(q) || 
        c.course_code.toLowerCase().includes(q) ||
        (c.term_name && c.term_name.toLowerCase().includes(q))
      );
    }

    if (filtered.length === 0) {
      el.coursesListContainer.innerHTML = `
        <div class="p-6 text-center text-slate-500 text-xs">
          No se encontraron cursos ${state.activeTab === 'active' ? 'activos' : ''} que coincidan con "${q}".
        </div>`;
      return;
    }

    el.coursesListContainer.innerHTML = '';
    filtered.forEach(course => {
      const isSelected = state.selectedCourse && state.selectedCourse.id === course.id;
      const card = document.createElement('div');
      card.className = `course-card ${isSelected ? 'active' : ''}`;
      
      const teacher = course.teachers && course.teachers.length > 0 ? course.teachers[0] : null;

      card.innerHTML = `
        <div class="flex items-start justify-between gap-2.5">
          <div class="min-w-0 flex-1 space-y-1.5">
            <div class="flex items-center gap-1.5 flex-wrap">
              ${course.is_favorite ? icons.star : ''}
              <span class="text-xs font-mono px-2 py-0.5 rounded bg-canvas-header border border-canvas-border text-slate-300 font-medium truncate max-w-[150px]">${escapeHtml(course.term_name)}</span>
              ${course.is_active ? '<span class="w-2 h-2 rounded-full bg-emerald-400" title="Activo"></span>' : ''}
            </div>
            <h3 class="text-sm md:text-base font-semibold text-slate-100 leading-snug line-clamp-2">${escapeHtml(course.name)}</h3>
            ${teacher ? `<p class="text-xs text-slate-400 truncate">${escapeHtml(teacher)}</p>` : ''}
          </div>
        </div>
      `;

      card.addEventListener('click', () => selectCourse(course));
      el.coursesListContainer.appendChild(card);
    });
  }

  // Select Course
  async function selectCourse(course) {
    state.selectedCourse = course;
    renderCoursesList(); // update active highlight in sidebar

    // Update Header
    el.courseTitleDisplay.textContent = course.name;
    el.courseCodeDisplay.textContent = course.course_code || `ID: ${course.id}`;
    el.courseTermBadge.textContent = course.term_name || 'Sin período';
    
    if (course.teachers && course.teachers.length > 0) {
      el.courseTeachersDisplay.textContent = `Docente(s): ${course.teachers.join(', ')}`;
    } else {
      el.courseTeachersDisplay.textContent = 'Asignatura Canvas';
    }

    const canvasHost = (state.status && state.status.canvas_url) ? state.status.canvas_url : 'https://canvas.instructure.com';
    el.openInCanvasLink.href = `${canvasHost}/courses/${course.id}`;
    el.openInCanvasLink.classList.remove('hidden');

    // Reset selection for this view or keep global
    await loadCourseContent();
  }

  // Load Course Content (Modules or Files)
  async function loadCourseContent() {
    if (!state.selectedCourse) return;
    const cid = state.selectedCourse.id;

    el.courseExplorerContainer.innerHTML = `
      <div class="p-8 text-center space-y-2">
        <div class="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-xs text-slate-400">Cargando material del curso...</p>
      </div>`;

    try {
      if (state.viewMode === 'modules') {
        const res = await fetch(`/api/courses/${cid}/modules`);
        const data = await res.json();
        state.courseModules = data.modules || [];
        renderModulesView();
      } else if (state.viewMode === 'assignments') {
        const res = await fetch(`/api/courses/${cid}/assignments`);
        const data = await res.json();
        state.courseAssignments = data.assignments || [];
        renderAssignmentsView();
      } else {
        const res = await fetch(`/api/courses/${cid}/files`);
        const data = await res.json();
        state.courseFilesData = data;
        renderFilesView();
      }
    } catch (err) {
      console.error('Error cargando contenido del curso:', err);
      el.courseExplorerContainer.innerHTML = `
        <div class="p-6 text-center text-red-400 text-xs">
          Error al cargar los módulos o archivos de este curso.
        </div>`;
    }
  }

  // Render Modules View
  function renderModulesView() {
    if (!state.courseModules || state.courseModules.length === 0) {
      el.courseExplorerContainer.innerHTML = `
        <div class="p-8 text-center text-slate-500 text-xs">
          Este curso no tiene módulos publicados en Canvas.
        </div>`;
      el.courseItemsStats.textContent = '0 archivos';
      return;
    }

    let totalCourseFiles = 0;
    let totalCourseBytes = 0;

    state.courseModules.forEach(m => {
      totalCourseFiles += m.files_count || 0;
      totalCourseBytes += m.total_bytes || 0;
    });

    el.courseItemsStats.textContent = `${totalCourseFiles} archivos (${formatBytes(totalCourseBytes)})`;

    el.courseExplorerContainer.innerHTML = '';

    state.courseModules.forEach((mod, modIdx) => {
      // Filtrar items según tipo de archivo
      const fileItems = (mod.items || []).filter(it => it.type === 'File' && it.file && it.file.download_url);
      
      // Filtrar por extensión si hay filtro activo
      const displayedItems = fileItems.filter(it => {
        if (state.currentExtFilter === 'all') return true;
        const name = (it.file.filename || '').toLowerCase();
        return name.endsWith(`.${state.currentExtFilter}`) || (state.currentExtFilter === 'doc' && (name.endsWith('.doc') || name.endsWith('.docx')));
      });

      if (fileItems.length === 0 && mod.items_count === 0) return;

      const modBox = document.createElement('div');
      modBox.className = 'module-box';

      // Header del módulo
      const modHeader = document.createElement('div');
      modHeader.className = 'module-header';

      const allModSelected = fileItems.length > 0 && fileItems.every(it => state.selectedFiles.has(it.file.file_id));

      modHeader.innerHTML = `
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <button class="toggle-collapse-btn p-1 text-slate-300 hover:text-white transition-transform">
            ${icons.chevronDown}
          </button>
          <div class="min-w-0 flex-1">
            <h4 class="text-base md:text-lg font-bold text-white truncate">${escapeHtml(mod.name)}</h4>
            <span class="text-xs font-mono text-slate-300">${fileItems.length} archivos · ${formatBytes(mod.total_bytes)}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <label class="flex items-center gap-1.5 text-xs text-slate-300 font-medium cursor-pointer">
            <input type="checkbox" class="mod-checkbox" ${allModSelected ? 'checked' : ''} ${fileItems.length === 0 ? 'disabled' : ''}>
            <span class="hidden sm:inline">Seleccionar módulo</span>
          </label>
        </div>
      `;

      // Checkbox del módulo completo
      const modCheckbox = modHeader.querySelector('.mod-checkbox');
      modCheckbox.addEventListener('click', (e) => {
        e.stopPropagation();
        const checkState = modCheckbox.checked;
        fileItems.forEach(it => {
          if (checkState) {
            state.selectedFiles.set(it.file.file_id, {
              file_id: it.file.file_id,
              filename: it.file.filename,
              size: it.file.size,
              url: it.file.download_url,
              course_name: state.selectedCourse.name,
              module_name: mod.name,
            });
          } else {
            state.selectedFiles.delete(it.file.file_id);
          }
        });
        updateBatchDock();
        renderModulesView();
      });

      // Contenido del módulo
      const modContent = document.createElement('div');
      modContent.className = 'module-content';

      if (displayedItems.length === 0) {
        modContent.innerHTML = `<div class="p-3.5 text-xs text-slate-400 italic pl-10">Sin archivos en este módulo con el filtro actual</div>`;
      } else {
        displayedItems.forEach(it => {
          const file = it.file;
          const isSelected = state.selectedFiles.has(file.file_id);
          const row = document.createElement('div');
          row.className = `file-row ${isSelected ? 'selected' : ''}`;

          row.innerHTML = `
            <div class="flex items-center gap-3.5 min-w-0 flex-1">
              <input type="checkbox" class="file-checkbox" ${isSelected ? 'checked' : ''}>
              ${getFileIcon(file.filename)}
              <div class="min-w-0 flex-1">
                <span class="text-sm md:text-base text-slate-100 truncate block font-medium hover:text-blue-400 transition-colors cursor-pointer" title="${escapeHtml(file.filename)}">
                  ${escapeHtml(file.filename)}
                </span>
              </div>
            </div>
            <div class="flex items-center gap-4 shrink-0 font-mono text-xs text-slate-300">
              <span class="tabular-nums font-semibold">${formatBytes(file.size)}</span>
              <button class="single-dl-btn p-1.5 rounded-md hover:bg-slate-700 text-slate-300 hover:text-blue-400 transition-colors" title="Descargar solo este archivo">
                ${icons.download}
              </button>
            </div>
          `;

          const fileCheckbox = row.querySelector('.file-checkbox');
          fileCheckbox.addEventListener('change', () => {
            if (fileCheckbox.checked) {
              state.selectedFiles.set(file.file_id, {
                file_id: file.file_id,
                filename: file.filename,
                size: file.size,
                url: file.download_url,
                course_name: state.selectedCourse.name,
                module_name: mod.name,
              });
            } else {
              state.selectedFiles.delete(file.file_id);
            }
            updateBatchDock();
            row.classList.toggle('selected', fileCheckbox.checked);
          });

          const singleDlBtn = row.querySelector('.single-dl-btn');
          singleDlBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            startSingleDownload({
              file_id: file.file_id,
              filename: file.filename,
              size: file.size,
              url: file.download_url,
              course_name: state.selectedCourse.name,
              module_name: mod.name,
            });
          });

          modContent.appendChild(row);
        });
      }

      // Colapsar / Desplegar
      modHeader.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        modContent.classList.toggle('collapsed');
        const iconBtn = modHeader.querySelector('.toggle-collapse-btn');
        iconBtn.innerHTML = modContent.classList.contains('collapsed') ? icons.chevronRight : icons.chevronDown;
      });

      modBox.appendChild(modHeader);
      modBox.appendChild(modContent);
      el.courseExplorerContainer.appendChild(modBox);
    });
  }

  function formatDueDate(isoString) {
    if (!isoString) return 'Sin fecha límite';
    try {
      const d = new Date(isoString);
      return 'Vence: ' + d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return 'Vence: ' + isoString;
    }
  }

  // Render Assignments View (Tareas del Curso)
  function renderAssignmentsView() {
    if (!state.courseAssignments || state.courseAssignments.length === 0) {
      el.courseExplorerContainer.innerHTML = `
        <div class="p-8 text-center text-slate-400 text-sm">
          No hay tareas ni actividades registradas en este curso.
        </div>`;
      el.courseItemsStats.textContent = '0 tareas';
      return;
    }

    let totalFiles = 0;
    let totalBytes = 0;
    state.courseAssignments.forEach(a => {
      (a.teacher_files || []).forEach(f => { totalFiles++; totalBytes += f.size || 0; });
      (a.submission_files || []).forEach(f => { totalFiles++; totalBytes += f.size || 0; });
    });

    el.courseItemsStats.textContent = `${state.courseAssignments.length} tareas (${totalFiles} archivos · ${formatBytes(totalBytes)})`;
    el.courseExplorerContainer.innerHTML = '';

    state.courseAssignments.forEach(a => {
      const allFiles = [...(a.teacher_files || []), ...(a.submission_files || [])];
      const allSelected = allFiles.length > 0 && allFiles.every(f => state.selectedFiles.has(f.file_id));

      const box = document.createElement('div');
      box.className = 'module-box';

      // Status Badge
      let statusBadgeHtml = '';
      if (a.score !== null && a.score !== undefined) {
        statusBadgeHtml = `<span class="badge-status badge-status-submitted">⭐ Calificado (${a.score}${a.points_possible ? '/' + a.points_possible : ''} pts)</span>`;
      } else if (a.has_submitted) {
        statusBadgeHtml = `<span class="badge-status badge-status-submitted">✓ Entregada</span>`;
      } else if (a.group === 'upcoming') {
        statusBadgeHtml = `<span class="badge-status badge-status-pending">⏳ Pendiente</span>`;
      } else {
        statusBadgeHtml = `<span class="badge-status badge-status-undated">Sin entregar</span>`;
      }

      const header = document.createElement('div');
      header.className = 'module-header';
      header.innerHTML = `
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <button class="toggle-collapse-btn p-1 text-slate-300 hover:text-white transition-transform">
            ${icons.chevronDown}
          </button>
          ${icons.assignment}
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <h4 class="text-base md:text-lg font-bold text-white truncate">${escapeHtml(a.name)}</h4>
              ${statusBadgeHtml}
            </div>
            <div class="flex items-center gap-3 text-xs font-mono text-slate-300 mt-0.5">
              <span>${formatDueDate(a.due_at)}</span>
              ${a.points_possible ? `<span>· ${a.points_possible} pts</span>` : ''}
              <span>· ${allFiles.length} archivo${allFiles.length === 1 ? '' : 's'}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <label class="flex items-center gap-1.5 text-xs text-slate-300 font-medium cursor-pointer" title="Seleccionar todos los archivos de esta tarea">
            <input type="checkbox" class="assignment-master-checkbox" ${allSelected ? 'checked' : ''} ${allFiles.length === 0 ? 'disabled' : ''}>
            <span class="hidden sm:inline">Seleccionar tarea</span>
          </label>
        </div>
      `;

      const masterCheckbox = header.querySelector('.assignment-master-checkbox');
      masterCheckbox.addEventListener('click', (e) => {
        e.stopPropagation();
        const check = masterCheckbox.checked;
        allFiles.forEach(f => {
          if (check) {
            state.selectedFiles.set(f.file_id, {
              file_id: f.file_id,
              filename: f.filename,
              size: f.size,
              url: f.download_url,
              course_name: state.selectedCourse.name,
              module_name: `Tareas/${a.name}`,
            });
          } else {
            state.selectedFiles.delete(f.file_id);
          }
        });
        updateBatchDock();
        renderAssignmentsView();
      });

      const content = document.createElement('div');
      content.className = 'module-content';

      // 1. Materiales de la Tarea (Docente)
      if (a.teacher_files && a.teacher_files.length > 0) {
        const secTitle = document.createElement('div');
        secTitle.className = 'assignment-section-title flex items-center justify-between';
        secTitle.innerHTML = `
          <span>📄 Materiales y Enunciados (${a.teacher_files.length})</span>
          <span class="font-mono text-xs text-slate-400 font-normal">Pautas / Instrucciones adjuntas</span>
        `;
        content.appendChild(secTitle);

        a.teacher_files.forEach(f => {
          const isSelected = state.selectedFiles.has(f.file_id);
          const row = document.createElement('div');
          row.className = `file-row ${isSelected ? 'selected' : ''}`;
          row.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <input type="checkbox" class="file-checkbox" ${isSelected ? 'checked' : ''}>
              ${getFileIcon(f.filename)}
              <span class="text-sm text-slate-200 truncate font-medium">${escapeHtml(f.filename)}</span>
              <span class="badge-hidden-file">Material docente</span>
            </div>
            <div class="flex items-center gap-4 shrink-0 font-mono text-xs text-slate-400">
              <span class="tabular-nums">${formatBytes(f.size)}</span>
              <button class="single-dl-btn p-1.5 hover:bg-slate-700/60 rounded text-slate-400 hover:text-white transition-colors" title="Descargar este archivo">
                ${icons.download}
              </button>
            </div>
          `;

          const cb = row.querySelector('.file-checkbox');
          cb.addEventListener('change', () => {
            if (cb.checked) {
              state.selectedFiles.set(f.file_id, {
                file_id: f.file_id,
                filename: f.filename,
                size: f.size,
                url: f.download_url,
                course_name: state.selectedCourse.name,
                module_name: `Tareas/${a.name}`,
              });
            } else {
              state.selectedFiles.delete(f.file_id);
            }
            updateBatchDock();
            row.classList.toggle('selected', cb.checked);
          });

          row.querySelector('.single-dl-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            startSingleDownload({
              file_id: f.file_id,
              filename: f.filename,
              size: f.size,
              url: f.download_url,
              course_name: state.selectedCourse.name,
              module_name: `Tareas/${a.name}`,
            });
          });

          content.appendChild(row);
        });
      }

      // 2. Mis Entregas (Estudiante)
      if (a.submission_files && a.submission_files.length > 0) {
        const secTitle = document.createElement('div');
        secTitle.className = 'assignment-section-title flex items-center justify-between text-emerald-300';
        secTitle.innerHTML = `
          <span>📤 Mi Entrega (${a.submission_files.length})</span>
          <span class="font-mono text-xs text-slate-400 font-normal">${a.submitted_at ? 'Entregado: ' + formatDueDate(a.submitted_at) : 'Archivos entregados'}</span>
        `;
        content.appendChild(secTitle);

        a.submission_files.forEach(f => {
          const isSelected = state.selectedFiles.has(f.file_id);
          const row = document.createElement('div');
          row.className = `file-row ${isSelected ? 'selected' : ''}`;
          row.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <input type="checkbox" class="file-checkbox" ${isSelected ? 'checked' : ''}>
              ${getFileIcon(f.filename)}
              <span class="text-sm text-slate-200 truncate font-medium">${escapeHtml(f.filename)}</span>
              <span class="badge-status badge-status-submitted">Entregado</span>
            </div>
            <div class="flex items-center gap-4 shrink-0 font-mono text-xs text-slate-400">
              <span class="tabular-nums">${formatBytes(f.size)}</span>
              <button class="single-dl-btn p-1.5 hover:bg-slate-700/60 rounded text-slate-400 hover:text-white transition-colors" title="Descargar este archivo">
                ${icons.download}
              </button>
            </div>
          `;

          const cb = row.querySelector('.file-checkbox');
          cb.addEventListener('change', () => {
            if (cb.checked) {
              state.selectedFiles.set(f.file_id, {
                file_id: f.file_id,
                filename: f.filename,
                size: f.size,
                url: f.download_url,
                course_name: state.selectedCourse.name,
                module_name: `Tareas/${a.name}`,
              });
            } else {
              state.selectedFiles.delete(f.file_id);
            }
            updateBatchDock();
            row.classList.toggle('selected', cb.checked);
          });

          row.querySelector('.single-dl-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            startSingleDownload({
              file_id: f.file_id,
              filename: f.filename,
              size: f.size,
              url: f.download_url,
              course_name: state.selectedCourse.name,
              module_name: `Tareas/${a.name}`,
            });
          });

          content.appendChild(row);
        });
      }

      // Si no hay archivos adjuntos en el docente ni entregas
      if (allFiles.length === 0) {
        const noFilesRow = document.createElement('div');
        noFilesRow.className = 'p-3 text-xs text-slate-400 italic px-5';
        noFilesRow.textContent = 'Sin archivos adjuntos ni entregas cargadas para esta tarea.';
        content.appendChild(noFilesRow);
      }

      // 3. Enunciado / Descripción en HTML
      if (a.description_html && a.description_html.trim().length > 10) {
        const descBar = document.createElement('div');
        descBar.className = 'p-2.5 px-4 bg-canvas-sidebar/40 border-t border-canvas-border flex items-center justify-between text-xs flex-wrap gap-2';
        descBar.innerHTML = `
          <span class="text-slate-400">Pauta e instrucciones del docente disponibles en texto</span>
          <button class="download-instructions-btn px-2.5 py-1 rounded bg-canvas-card hover:bg-canvas-hover border border-canvas-border text-blue-400 hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer font-medium">
            ${icons.download} Guardar Enunciado (HTML)
          </button>
        `;

        descBar.querySelector('.download-instructions-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          const cleanName = `${a.name.replace(/[/\\?%*:|"<>]/g, '_')}_Instrucciones.html`;
          const htmlContent = `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>${escapeHtml(a.name)}</title><style>body{font-family:sans-serif;padding:2.5rem;max-width:850px;margin:auto;line-height:1.6;color:#1e293b;}h1{color:#2563eb;}hr{border:0;border-top:1px solid #cbd5e1;margin:1.5rem 0;}</style></head><body><h1>${escapeHtml(a.name)}</h1><p><strong>Curso:</strong> ${escapeHtml(state.selectedCourse.name)}<br><strong>Fecha de entrega:</strong> ${escapeHtml(formatDueDate(a.due_at))}</p><hr>${a.description_html}</body></html>`;

          startSingleDownload({
            filename: cleanName,
            size: htmlContent.length,
            raw_content: htmlContent,
            course_name: state.selectedCourse.name,
            module_name: `Tareas/${a.name}`,
          });
        });

        content.appendChild(descBar);
      }

      // Collapse toggle
      header.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.closest('button.download-instructions-btn')) return;
        content.classList.toggle('collapsed');
        const iconBtn = header.querySelector('.toggle-collapse-btn');
        iconBtn.innerHTML = content.classList.contains('collapsed') ? icons.chevronRight : icons.chevronDown;
      });

      box.appendChild(header);
      box.appendChild(content);
      el.courseExplorerContainer.appendChild(box);
    });
  }

  // Render Files View
  function renderFilesView() {
    if (!state.courseFilesData || !state.courseFilesData.folders) {
      el.courseExplorerContainer.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">Sin archivos disponibles</div>`;
      return;
    }

    const { folders, total_files, total_bytes, hidden_files_count } = state.courseFilesData;
    const hiddenNotice = hidden_files_count ? ` · ${hidden_files_count} recuperados de páginas/tareas` : '';
    el.courseItemsStats.textContent = `${total_files} archivos (${formatBytes(total_bytes)}${hiddenNotice})`;

    el.courseExplorerContainer.innerHTML = '';

    folders.forEach(fld => {
      if (!fld.files || fld.files.length === 0) return;

      const modBox = document.createElement('div');
      modBox.className = `module-box ${fld.is_special ? 'special-box' : ''}`;

      const modHeader = document.createElement('div');
      modHeader.className = 'module-header';

      modHeader.innerHTML = `
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <button class="toggle-collapse-btn p-1 text-slate-300 hover:text-white transition-transform">
            ${icons.chevronDown}
          </button>
          ${icons.folder}
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <h4 class="text-base md:text-lg font-bold text-white truncate">${escapeHtml(fld.name)}</h4>
              ${fld.is_special ? `<span class="badge-status badge-status-pending">👁️ Recuperados</span>` : ''}
            </div>
            <span class="text-xs font-mono text-slate-300">${fld.files.length} archivos</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <label class="flex items-center gap-1.5 text-xs text-slate-300 font-medium cursor-pointer">
            <input type="checkbox" class="mod-checkbox">
            <span class="hidden sm:inline">Seleccionar carpeta</span>
          </label>
        </div>
      `;

      const modCheckbox = modHeader.querySelector('.mod-checkbox');
      modCheckbox.addEventListener('click', (e) => {
        e.stopPropagation();
        const check = modCheckbox.checked;
        fld.files.forEach(file => {
          if (check) {
            state.selectedFiles.set(file.file_id, {
              file_id: file.file_id,
              filename: file.filename,
              size: file.size,
              url: file.download_url,
              course_name: state.selectedCourse.name,
              folder_name: fld.name,
            });
          } else {
            state.selectedFiles.delete(file.file_id);
          }
        });
        updateBatchDock();
        renderFilesView();
      });

      const modContent = document.createElement('div');
      modContent.className = 'module-content';

      // Si es la carpeta especial de archivos ocultos/recuperados
      if (fld.is_special) {
        const banner = document.createElement('div');
        banner.className = 'p-3 bg-blue-950/40 border-b border-blue-500/20 text-xs text-blue-200 flex items-center gap-2';
        banner.innerHTML = `
          <svg class="w-4 h-4 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>Estos archivos no aparecen en la pestaña oficial de archivos del curso (o la pestaña está restringida), pero fueron localizados y recuperados automáticamente por CanvasDL desde páginas, tareas y módulos.</span>
        `;
        modContent.appendChild(banner);
      }

      fld.files.forEach(file => {
        const isSelected = state.selectedFiles.has(file.file_id);
        const row = document.createElement('div');
        row.className = `file-row ${isSelected ? 'selected' : ''}`;

        row.innerHTML = `
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <input type="checkbox" class="file-checkbox" ${isSelected ? 'checked' : ''}>
            ${getFileIcon(file.filename)}
            <div class="min-w-0 flex-1">
              <span class="text-sm text-slate-200 truncate font-medium block">${escapeHtml(file.filename)}</span>
              ${file.source ? `<span class="text-xs text-slate-400 truncate block">${escapeHtml(file.source)}</span>` : ''}
            </div>
            ${file.is_hidden ? `<span class="badge-hidden-file">👁️ Enlazado</span>` : ''}
          </div>
          <div class="flex items-center gap-4 shrink-0 font-mono text-xs text-slate-400">
            <span class="tabular-nums">${formatBytes(file.size)}</span>
            <button class="single-dl-btn p-1.5 hover:bg-slate-700/60 rounded text-slate-400 hover:text-white transition-colors" title="Descargar este archivo">
              ${icons.download}
            </button>
          </div>
        `;

        const fileCheckbox = row.querySelector('.file-checkbox');
        fileCheckbox.addEventListener('change', () => {
          if (fileCheckbox.checked) {
            state.selectedFiles.set(file.file_id, {
              file_id: file.file_id,
              filename: file.filename,
              size: file.size,
              url: file.download_url,
              course_name: state.selectedCourse.name,
              folder_name: fld.name,
            });
          } else {
            state.selectedFiles.delete(file.file_id);
          }
          updateBatchDock();
          row.classList.toggle('selected', fileCheckbox.checked);
        });

        row.querySelector('.single-dl-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          startSingleDownload({
            file_id: file.file_id,
            filename: file.filename,
            size: file.size,
            url: file.download_url,
            course_name: state.selectedCourse.name,
            folder_name: fld.name,
          });
        });

        modContent.appendChild(row);
      });

      modHeader.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        modContent.classList.toggle('collapsed');
        const iconBtn = modHeader.querySelector('.toggle-collapse-btn');
        iconBtn.innerHTML = modContent.classList.contains('collapsed') ? icons.chevronRight : icons.chevronDown;
      });

      modBox.appendChild(modHeader);
      modBox.appendChild(modContent);
      el.courseExplorerContainer.appendChild(modBox);
    });
  }

  // Update Batch Dock Status
  function updateBatchDock() {
    const count = state.selectedFiles.size;
    let totalBytes = 0;
    state.selectedFiles.forEach(f => {
      totalBytes += f.size || 0;
    });

    el.selectedCountText.textContent = `${count} archivo${count === 1 ? '' : 's'} seleccionado${count === 1 ? '' : 's'}`;
    el.selectedSizeText.textContent = `· ${formatBytes(totalBytes)}`;

    if (count > 0) {
      el.startDownloadBtn.removeAttribute('disabled');
      el.startDownloadBtnLabel.textContent = `Descargar Selección (${count})`;
    } else {
      el.startDownloadBtn.setAttribute('disabled', 'true');
      el.startDownloadBtnLabel.textContent = 'Descargar Selección';
    }
  }

  // Start Batch Download
  async function startBatchDownload() {
    if (state.selectedFiles.size === 0) return;

    const items = Array.from(state.selectedFiles.values());

    el.startDownloadBtn.setAttribute('disabled', 'true');
    el.dockProgressSection.classList.remove('hidden');
    el.cancelDownloadBtn.classList.remove('hidden');

    try {
      const res = await fetch('/api/downloads/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
      }
    } catch (err) {
      console.error('Error iniciando descarga:', err);
      alert('Error de conexión al iniciar la descarga.');
    }
  }

  // Start Single Download
  async function startSingleDownload(fileItem) {
    el.dockProgressSection.classList.remove('hidden');
    el.cancelDownloadBtn.classList.remove('hidden');

    try {
      await fetch('/api/downloads/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: [fileItem] }),
      });
    } catch (err) {
      console.error('Error descargando archivo:', err);
    }
  }

  // Download Entire Course: módulos, tareas (con enunciados), anuncios y archivos
  async function downloadFullCourse() {
    if (!state.selectedCourse) return;
    const course = state.selectedCourse;
    const btn = el.downloadFullCourseBtn;
    const btnLabel = btn.querySelector('span');
    const originalLabel = btnLabel.textContent;

    btn.setAttribute('disabled', 'true');
    btnLabel.textContent = 'Preparando...';
    let plan;
    try {
      const q = new URLSearchParams({ course_name: course.name });
      const res = await fetch(`/api/courses/${course.id}/full-plan?${q}`);
      plan = await res.json();
      if (!res.ok) throw new Error(plan.detail || `HTTP ${res.status}`);
    } catch (err) {
      console.error('Error preparando descarga completa:', err);
      alert(`No se pudo preparar la descarga del curso: ${err.message}`);
      return;
    } finally {
      btn.removeAttribute('disabled');
      btnLabel.textContent = originalLabel;
    }

    const { items, errors } = plan;
    if (items.length === 0) {
      alert('No se encontró contenido para descargar en este curso.');
      return;
    }

    const totalSize = items.reduce((sum, it) => sum + (it.size || 0), 0);
    let msg = `¿Descargar todo "${course.name}"?\n\n${items.length} elementos (módulos, tareas, anuncios y archivos) · ${formatBytes(totalSize)}\nLos archivos duplicados se detectan por hash y se conserva una sola copia.`;
    if (errors.length) msg += `\n\nAlgunas secciones no se pudieron leer:\n- ${errors.join('\n- ')}`;
    if (!confirm(msg)) return;

    state.selectedFiles.clear();
    items.forEach((it, i) => state.selectedFiles.set(it.file_id ?? `raw_${i}`, it));
    updateBatchDock();
    await startBatchDownload();
  }

  // Server-Sent Events (SSE) for Real-Time Progress
  function initSSE() {
    if (state.eventSource) {
      state.eventSource.close();
    }

    state.eventSource = new EventSource('/api/downloads/events');

    state.eventSource.onmessage = function (event) {
      try {
        const payload = JSON.parse(event.data);
        handleSSEEvent(payload);
      } catch (e) {}
    };

    state.eventSource.onerror = function () {
      // Reconexión automática nativa de EventSource
    };
  }

  function handleSSEEvent(payload) {
    const { type, data } = payload;

    if (type === 'init' || type === 'batch_started' || type === 'batch_finished') {
      updateProgressDisplay(data);
    } else if (type === 'task_updated') {
      // Actualización de tarea específica
      fetch('/api/downloads/status')
        .then(r => r.json())
        .then(st => updateProgressDisplay(st))
        .catch(() => {});
    }
  }

  function updateProgressDisplay(status) {
    if (!status) return;

    const total = status.total_tasks || 0;
    const completed = (status.completed || 0) + (status.skipped || 0);

    if (status.is_running) {
      el.dockProgressSection.classList.remove('hidden');
      el.cancelDownloadBtn.classList.remove('hidden');
      el.startDownloadBtn.setAttribute('disabled', 'true');

      const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
      el.downloadProgressBar.style.width = `${pct}%`;
      el.downloadProgressPercentage.textContent = `${pct}%`;
      el.downloadProgressCount.textContent = `${completed} / ${total} completados`;
      el.dockSubtitle.textContent = `Descargando masivamente a disco local... (${completed} de ${total})`;
    } else {
      if (total > 0 && completed === total) {
        el.downloadProgressBar.style.width = '100%';
        el.downloadProgressPercentage.textContent = '100%';
        el.downloadProgressCount.textContent = `¡Completado! (${total} archivos)`;
        el.dockSubtitle.textContent = '✓ Todos los archivos fueron guardados exitosamente en tu equipo.';
        el.cancelDownloadBtn.classList.add('hidden');
        el.startDownloadBtn.removeAttribute('disabled');
      } else {
        el.dockProgressSection.classList.add('hidden');
        el.cancelDownloadBtn.classList.add('hidden');
        updateBatchDock();
      }
    }
  }

  // Setup Event Listeners
  function setupEventListeners() {
    // Search
    el.courseSearchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      renderCoursesList();
    });

    // Tabs
    el.tabActiveCourses.addEventListener('click', () => {
      state.activeTab = 'active';
      el.tabActiveCourses.className = 'flex-1 py-1.5 px-3 rounded-md text-center transition-all font-semibold text-white bg-dark-card shadow-sm flex items-center justify-center gap-2 cursor-pointer';
      el.tabAllCourses.className = 'flex-1 py-1.5 px-3 rounded-md text-center transition-all text-slate-400 hover:text-slate-200 flex items-center justify-center gap-2 cursor-pointer';
      renderCoursesList();
    });

    el.tabAllCourses.addEventListener('click', () => {
      state.activeTab = 'all';
      el.tabAllCourses.className = 'flex-1 py-1.5 px-3 rounded-md text-center transition-all font-semibold text-white bg-dark-card shadow-sm flex items-center justify-center gap-2 cursor-pointer';
      el.tabActiveCourses.className = 'flex-1 py-1.5 px-3 rounded-md text-center transition-all text-slate-400 hover:text-slate-200 flex items-center justify-center gap-2 cursor-pointer';
      renderCoursesList();
    });

    function updateViewTabs() {
      const activeClass = 'py-1.5 px-3.5 rounded-md bg-canvas-header text-white font-bold flex items-center gap-2 cursor-pointer border border-canvas-border shadow-sm';
      const inactiveClass = 'py-1.5 px-3.5 rounded-md text-slate-300 hover:text-white font-semibold flex items-center gap-2 cursor-pointer transition-colors';

      if (el.viewModeModulesBtn) el.viewModeModulesBtn.className = state.viewMode === 'modules' ? activeClass : inactiveClass;
      if (el.viewModeAssignmentsBtn) el.viewModeAssignmentsBtn.className = state.viewMode === 'assignments' ? activeClass : inactiveClass;
      if (el.viewModeFilesBtn) el.viewModeFilesBtn.className = state.viewMode === 'files' ? activeClass : inactiveClass;
    }

    // View Modes (Módulos vs Tareas vs Archivos)
    if (el.viewModeModulesBtn) {
      el.viewModeModulesBtn.addEventListener('click', () => {
        if (state.viewMode === 'modules') return;
        state.viewMode = 'modules';
        updateViewTabs();
        loadCourseContent();
      });
    }

    if (el.viewModeAssignmentsBtn) {
      el.viewModeAssignmentsBtn.addEventListener('click', () => {
        if (state.viewMode === 'assignments') return;
        state.viewMode = 'assignments';
        updateViewTabs();
        loadCourseContent();
      });
    }

    if (el.viewModeFilesBtn) {
      el.viewModeFilesBtn.addEventListener('click', () => {
        if (state.viewMode === 'files') return;
        state.viewMode = 'files';
        updateViewTabs();
        loadCourseContent();
      });
    }

    // Extension Filters
    document.querySelectorAll('.filter-ext-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-ext-btn').forEach(b => {
          b.className = 'filter-ext-btn px-2.5 py-1 rounded bg-canvas-card text-slate-300 hover:text-white border border-canvas-border';
        });
        btn.className = 'filter-ext-btn px-2.5 py-1 rounded bg-blue-600/25 text-blue-300 border border-blue-500/30 font-semibold';
        state.currentExtFilter = btn.dataset.ext;
        if (state.viewMode === 'modules') {
          renderModulesView();
        }
      });
    });

    // Selection buttons
    el.selectAllBtn.addEventListener('click', () => {
      if (state.viewMode === 'modules') {
        state.courseModules.forEach(m => {
          (m.items || []).forEach(it => {
            if (it.type === 'File' && it.file && it.file.download_url) {
              state.selectedFiles.set(it.file.file_id, {
                file_id: it.file.file_id,
                filename: it.file.filename,
                size: it.file.size,
                url: it.file.download_url,
                course_name: state.selectedCourse.name,
                module_name: m.name,
              });
            }
          });
        });
        renderModulesView();
      } else if (state.viewMode === 'assignments') {
        state.courseAssignments.forEach(a => {
          [...(a.teacher_files || []), ...(a.submission_files || [])].forEach(f => {
            state.selectedFiles.set(f.file_id, {
              file_id: f.file_id,
              filename: f.filename,
              size: f.size,
              url: f.download_url,
              course_name: state.selectedCourse.name,
              module_name: `Tareas/${a.name}`,
            });
          });
        });
        renderAssignmentsView();
      } else if (state.courseFilesData && state.courseFilesData.folders) {
        state.courseFilesData.folders.forEach(fld => {
          (fld.files || []).forEach(file => {
            state.selectedFiles.set(file.file_id, {
              file_id: file.file_id,
              filename: file.filename,
              size: file.size,
              url: file.download_url,
              course_name: state.selectedCourse.name,
              folder_name: fld.name,
            });
          });
        });
        renderFilesView();
      }
      updateBatchDock();
    });

    el.deselectAllBtn.addEventListener('click', () => {
      state.selectedFiles.clear();
      if (state.viewMode === 'modules') {
        renderModulesView();
      } else if (state.viewMode === 'assignments') {
        renderAssignmentsView();
      } else {
        renderFilesView();
      }
      updateBatchDock();
    });

    // Download Actions
    el.startDownloadBtn.addEventListener('click', startBatchDownload);
    el.downloadFullCourseBtn.addEventListener('click', downloadFullCourse);

    el.cancelDownloadBtn.addEventListener('click', async () => {
      await fetch('/api/downloads/cancel', { method: 'POST' });
    });

    // Open Folder
    const handleOpenFolder = async () => {
      await fetch('/api/open-folder', { method: 'POST' });
    };
    if (el.openFolderBtn) el.openFolderBtn.addEventListener('click', handleOpenFolder);
    const openFolderRailBtn = document.getElementById('openFolderRailBtn');
    if (openFolderRailBtn) openFolderRailBtn.addEventListener('click', handleOpenFolder);

    // Settings Modal
    const openSettings = () => el.settingsModal.classList.remove('hidden');
    if (el.settingsBtn) el.settingsBtn.addEventListener('click', openSettings);
    const settingsRailBtn = document.getElementById('settingsRailBtn');
    if (settingsRailBtn) settingsRailBtn.addEventListener('click', openSettings);

    const closeModal = () => el.settingsModal.classList.add('hidden');
    el.closeSettingsModalBtn.addEventListener('click', closeModal);
    el.closeSettingsModalBtn2.addEventListener('click', closeModal);

    el.settingsSaveDirBtn.addEventListener('click', async () => {
      const newDir = el.settingsDownloadDirInput.value.trim();
      if (!newDir) return;
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ download_dir: newDir }),
      });
      await fetchStatus();
      alert('Carpeta de descargas actualizada.');
    });

    el.settingsAutoOpenCheckbox.addEventListener('change', async (e) => {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_open_folder: e.target.checked }),
      });
    });

    el.settingsSaveTokenBtn.addEventListener('click', async () => {
      const token = el.settingsTokenInput.value.trim();
      if (!token) return;
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (data.authenticated) {
        alert('Token actualizado correctamente. Conectado como: ' + data.user.name);
        el.settingsTokenInput.value = '';
        closeModal();
        await fetchStatus();
        await fetchCourses();
      } else {
        alert('Token inválido: ' + data.error);
      }
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Run on DOM ready
  document.addEventListener('DOMContentLoaded', init);
})();
