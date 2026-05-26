const state = {
  user: JSON.parse(localStorage.getItem("cleanops_user") || "null"),
  data: null,
  tasks: [],
  analytics: null,
  view: "dashboard",
  activeTask: null
};

const statusLabels = {
  created: "Создано",
  in_progress: "В работе",
  on_review: "На проверке",
  completed: "Завершено",
  rework: "Доработка"
};

const roleLabels = {
  admin: "Администратор",
  supervisor: "Ответственный за уборку",
  cleaner: "Сотрудник клининга"
};

const priorityLabels = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический"
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Ошибка запроса");
  return data;
}

async function loadAll() {
  state.data = await api("/api/bootstrap");
  await Promise.all([loadTasks(), loadAnalytics()]);
  fillTaskFormOptions();
}

async function loadTasks() {
  const params = new URLSearchParams();
  if (state.user?.role_name === "cleaner") {
    params.set("role", "cleaner");
    params.set("user_id", state.user.user_id);
  }
  const result = await api(`/api/tasks?${params.toString()}`);
  state.tasks = result.tasks;
}

async function loadAnalytics() {
  state.analytics = await api("/api/analytics");
}

function setSession(user) {
  state.user = user;
  localStorage.setItem("cleanops_user", JSON.stringify(user));
  $("#loginView").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  $("#userName").textContent = user.full_name;
  $("#userRole").textContent = roleLabels[user.role_name] || user.role_name;
  $$(".supervisor-only").forEach((el) => {
    el.classList.toggle("hidden", user.role_name === "cleaner");
  });
}

function showLogin() {
  state.user = null;
  localStorage.removeItem("cleanops_user");
  $("#workspace").classList.add("hidden");
  $("#loginView").classList.remove("hidden");
}

function setView(view) {
  state.view = view;
  $$("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $$(".view").forEach((section) => section.classList.remove("active"));
  $(`#${view}View`).classList.add("active");
  const titles = {
    dashboard: "Сводка",
    tasks: "Задания",
    quality: "Проверка качества",
    reports: "Отчеты и аналитика",
    audit: "Журнал действий"
  };
  $("#pageTitle").textContent = titles[view];
  render();
}

function render() {
  $("#todayLabel").textContent = new Intl.DateTimeFormat("ru-RU", { dateStyle: "full" }).format(new Date());
  if (!state.data || !state.analytics) return;
  renderDashboard();
  renderTasks();
  renderQuality();
  renderReports();
  renderAudit();
}

function renderDashboard() {
  const totals = state.analytics.totals;
  const completedPercent = totals.tasks_total ? Math.round((totals.tasks_completed / totals.tasks_total) * 100) : 0;
  $("#dashboardView").innerHTML = `
    <div class="stat-grid">
      <article class="stat-card"><span>Всего заданий</span><strong>${totals.tasks_total || 0}</strong></article>
      <article class="stat-card"><span>Завершено</span><strong>${totals.tasks_completed || 0}</strong></article>
      <article class="stat-card"><span>Просрочено</span><strong>${totals.overdue_tasks || 0}</strong></article>
      <article class="stat-card"><span>Выполнение</span><strong>${completedPercent}%</strong></article>
    </div>
    <div class="grid two">
      <section class="panel">
        <h2>Статусы заданий</h2>
        ${renderStatusChart()}
      </section>
      <section class="panel">
        <h2>Эффективность сотрудников</h2>
        ${renderEmployeeTable()}
      </section>
    </div>
    <section class="panel" style="margin-top:14px">
      <h2>Критичные и ближайшие работы</h2>
      <div class="task-list">${state.tasks.slice(0, 4).map(taskCard).join("") || `<div class="empty">Нет активных заданий</div>`}</div>
    </section>
  `;
}

function renderStatusChart() {
  const max = Math.max(1, ...state.analytics.status_counts.map((item) => item.total));
  return state.analytics.status_counts.map((item) => `
    <div class="chart-row">
      <span>${statusLabels[item.status_name] || item.status_name}</span>
      <div class="chart-bar"><span style="width:${Math.max(6, item.total / max * 100)}%"></span></div>
      <strong>${item.total}</strong>
    </div>
  `).join("");
}

function renderEmployeeTable() {
  return `
    <table>
      <thead><tr><th>Сотрудник</th><th>Задач</th><th>Готово</th><th>Возвраты</th></tr></thead>
      <tbody>
        ${state.analytics.employee_stats.map((item) => `
          <tr>
            <td>${escapeHtml(item.full_name)}</td>
            <td>${item.total_tasks || 0}</td>
            <td>${item.completed_tasks || 0}</td>
            <td>${item.reworks || 0}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderTasks() {
  const currentSearch = $("#taskSearch")?.value || "";
  const currentStatus = $("#statusFilter")?.value || "";
  const filtered = state.tasks.filter((task) => {
    const text = `${task.title} ${task.room_number} ${task.assigned_name}`.toLowerCase();
    const bySearch = !currentSearch || text.includes(currentSearch.toLowerCase());
    const byStatus = !currentStatus || task.status_name === currentStatus;
    return bySearch && byStatus;
  });
  $("#tasksView").innerHTML = `
    <div class="toolbar">
      <input id="taskSearch" placeholder="Поиск по заданию, помещению или сотруднику" value="${escapeHtml(currentSearch)}">
      <select id="statusFilter">
        <option value="">Все статусы</option>
        ${state.data.statuses.map((status) => `
          <option value="${status.status_name}" ${currentStatus === status.status_name ? "selected" : ""}>${statusLabels[status.status_name]}</option>
        `).join("")}
      </select>
    </div>
    <div class="task-list">${filtered.map(taskCard).join("") || `<div class="empty">Заданий по выбранным фильтрам нет</div>`}</div>
  `;
  $("#taskSearch").addEventListener("input", renderTasks);
  $("#statusFilter").addEventListener("change", renderTasks);
}

function taskCard(task) {
  const progress = task.total_items ? Math.round((task.completed_items / task.total_items) * 100) : 0;
  return `
    <article class="task-card priority-${task.priority}">
      <div>
        <div class="task-meta">
          <span class="badge status-${task.status_name}">${statusLabels[task.status_name]}</span>
          <span>${priorityLabels[task.priority]}</span>
          <span>${escapeHtml(task.building)}, ${escapeHtml(task.room_number)}</span>
          <span>Срок: ${formatDate(task.deadline)}</span>
        </div>
        <h3>${escapeHtml(task.title)}</h3>
        <p>${escapeHtml(task.description || "")}</p>
        <div class="progress" title="Чек-лист: ${progress}%"><span style="width:${progress}%"></span></div>
        <div class="task-meta" style="margin-top:8px">
          <span>Исполнитель: ${escapeHtml(task.assigned_name)}</span>
          <span>Фото: ${task.photo_count}</span>
          <span>Возвраты: ${task.rework_count}</span>
        </div>
      </div>
      <div class="actions">
        ${task.status_name === "created" && state.user.role_name === "cleaner" ? `<button class="secondary" data-status="in_progress" data-task="${task.task_id}">В работу</button>` : ""}
        <button class="primary" data-open-task="${task.task_id}">Открыть</button>
      </div>
    </article>
  `;
}

function renderQuality() {
  const queue = state.tasks.filter((task) => task.status_name === "on_review" || task.status_name === "rework");
  $("#qualityView").innerHTML = `
    <div class="grid two">
      <section class="panel">
        <h2>Очередь проверки</h2>
        <div class="task-list">${queue.map(taskCard).join("") || `<div class="empty">Нет заданий, ожидающих проверки</div>`}</div>
      </section>
      <section class="panel">
        <h2>Возвраты на доработку</h2>
        ${renderReworkTable()}
      </section>
    </div>
  `;
}

function renderReworkTable() {
  const rows = state.tasks.filter((task) => task.rework_count > 0);
  if (!rows.length) return `<div class="empty">Замечаний пока нет</div>`;
  return `
    <table>
      <thead><tr><th>Задание</th><th>Помещение</th><th>Возвратов</th></tr></thead>
      <tbody>${rows.map((task) => `
        <tr>
          <td>${escapeHtml(task.title)}</td>
          <td>${escapeHtml(task.room_number)}</td>
          <td>${task.rework_count}</td>
        </tr>
      `).join("")}</tbody>
    </table>
  `;
}

function renderReports() {
  $("#reportsView").innerHTML = `
    <div class="grid two">
      <section class="panel">
        <h2>Формирование отчета</h2>
        <div class="grid three">
          <button class="primary" data-report="daily">Ежедневный</button>
          <button class="secondary" data-report="weekly">Еженедельный</button>
          <button class="secondary" data-report="monthly">Ежемесячный</button>
        </div>
        <div id="reportResult" class="empty" style="margin-top:14px">Выберите тип отчета для формирования</div>
      </section>
      <section class="panel">
        <h2>Остатки расходных материалов</h2>
        <table>
          <thead><tr><th>Материал</th><th>Остаток</th><th>Израсходовано</th></tr></thead>
          <tbody>${state.analytics.consumable_stats.map((item) => `
            <tr>
              <td>${escapeHtml(item.name)}</td>
              <td>${item.current_stock} ${escapeHtml(item.unit)}</td>
              <td>${item.used_total} ${escapeHtml(item.unit)}</td>
            </tr>
          `).join("")}</tbody>
        </table>
      </section>
    </div>
  `;
}

async function renderAudit() {
  if (state.user.role_name === "cleaner") {
    $("#auditView").innerHTML = `<div class="empty">Журнал действий доступен ответственному и администратору</div>`;
    return;
  }
  const result = await api("/api/audit");
  $("#auditView").innerHTML = `
    <section class="panel">
      <h2>Последние действия</h2>
      <table>
        <thead><tr><th>Дата</th><th>Пользователь</th><th>Действие</th><th>Объект</th></tr></thead>
        <tbody>${result.items.map((item) => `
          <tr>
            <td>${escapeHtml(item.created_at)}</td>
            <td>${escapeHtml(item.full_name || "Система")}</td>
            <td>${escapeHtml(item.action_type)}</td>
            <td>${escapeHtml(item.table_name || "")} #${item.record_id || ""}</td>
          </tr>
        `).join("")}</tbody>
      </table>
    </section>
  `;
}

function fillTaskFormOptions() {
  const cleaners = state.data.users.filter((user) => user.role_name === "cleaner");
  $("#roomSelect").innerHTML = state.data.rooms.map((room) => `
    <option value="${room.room_id}">${escapeHtml(room.building)} / ${escapeHtml(room.room_number)} / ${escapeHtml(room.type_name)}</option>
  `).join("");
  $("#assigneeSelect").innerHTML = cleaners.map((user) => `
    <option value="${user.user_id}">${escapeHtml(user.full_name)}</option>
  `).join("");
  $("#taskForm [name=deadline]").value = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
}

async function openTask(taskId) {
  const detail = await api(`/api/tasks/${taskId}`);
  state.activeTask = detail;
  $("#detailTitle").textContent = detail.task.title;
  $("#taskDetail").innerHTML = renderTaskDetail(detail);
  $("#taskDetailDialog").showModal();
}

function renderTaskDetail(detail) {
  const task = detail.task;
  return `
    <div class="detail-layout">
      <div class="grid">
        <section class="panel">
          <div class="task-meta">
            <span class="badge status-${task.status_name}">${statusLabels[task.status_name]}</span>
            <span>${priorityLabels[task.priority]}</span>
            <span>${escapeHtml(task.building)}, ${escapeHtml(task.room_number)}</span>
          </div>
          <p>${escapeHtml(task.description || "")}</p>
          <div class="grid two">
            <p><strong>Исполнитель:</strong><br>${escapeHtml(task.assigned_name)}</p>
            <p><strong>Срок:</strong><br>${formatDate(task.deadline)}</p>
          </div>
        </section>

        <section class="panel">
          <h3>Чек-лист выполнения</h3>
          <form id="checklistForm">
            ${detail.items.map((item) => `
              <label class="check-item">
                <input type="checkbox" data-item-id="${item.item_id}" ${item.is_completed ? "checked" : ""}>
                <span>${escapeHtml(item.work_description)}</span>
              </label>
            `).join("") || `<div class="empty">Чек-лист не создан</div>`}
            <label>Комментарий исполнителя
              <textarea name="comments" rows="3">${escapeHtml(detail.checklist?.comments || "")}</textarea>
            </label>
            <h3>Расход материалов</h3>
            <div class="grid two">
              ${state.data.consumables.map((item) => `
                <label>${escapeHtml(item.name)} (${escapeHtml(item.unit)})
                  <input type="number" min="0" step="0.1" data-consumable="${item.consumable_id}" value="${detail.used_consumables.find((used) => used.consumable_id === item.consumable_id)?.quantity || 0}">
                </label>
              `).join("")}
            </div>
            ${state.user.role_name === "cleaner" ? `<button class="primary" type="submit" style="margin-top:14px">Отправить на проверку</button>` : ""}
          </form>
        </section>

        <section class="panel">
          <h3>Проверки и замечания</h3>
          ${detail.inspections.length ? detail.inspections.map((inspection) => `
            <p><strong>${inspection.result === "approved" ? "Принято" : "Доработка"}</strong> - ${escapeHtml(inspection.inspector_name)}<br><small>${escapeHtml(inspection.inspection_date)}</small></p>
          `).join("") : `<div class="empty">Проверок пока нет</div>`}
          ${detail.comments.map((comment) => `<p><strong>Замечание:</strong> ${escapeHtml(comment.comment_text)}</p>`).join("")}
          ${state.user.role_name !== "cleaner" && task.status_name === "on_review" ? `
            <form id="inspectionForm" class="grid">
              <label>Результат
                <select name="result">
                  <option value="approved">Принять</option>
                  <option value="rework">Вернуть на доработку</option>
                </select>
              </label>
              <label>Комментарий<textarea name="comment" rows="3"></textarea></label>
              <button class="primary" type="submit">Сохранить проверку</button>
            </form>
          ` : ""}
        </section>
      </div>

      <aside class="grid">
        <section class="panel">
          <h3>Фотофиксация</h3>
          <div class="photo-grid">
            ${detail.photos.map((photo) => `<img src="${photo.file_path}" alt="${photo.photo_type}">`).join("") || `<div class="empty">Фото пока нет</div>`}
          </div>
          ${state.user.role_name === "cleaner" ? `
            <form id="photoForm" class="grid" style="margin-top:12px">
              <label>Тип фото
                <select name="photo_type">
                  <option value="before">До</option>
                  <option value="after">После</option>
                  <option value="deficiency">Недочет</option>
                </select>
              </label>
              <label>Файл<input name="photo" type="file" accept="image/*" required></label>
              <button class="secondary" type="submit">Загрузить фото</button>
            </form>
          ` : ""}
        </section>
      </aside>
    </div>
  `;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ru-RU").format(new Date(`${value}T00:00:00`));
}

async function refresh() {
  await loadAll();
  render();
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;

  if (target.matches("[data-login]")) {
    $("#loginForm [name=login]").value = target.dataset.login;
    $("#loginForm [name=password]").value = target.dataset.password;
  }

  if (target.matches("[data-view]")) setView(target.dataset.view);
  if (target.id === "logoutBtn") showLogin();
  if (target.id === "refreshBtn") await refresh();
  if (target.id === "openTaskForm") $("#taskDialog").showModal();
  if (target.matches("[data-close-dialog]")) $("#taskDialog").close();
  if (target.matches("[data-close-detail]")) $("#taskDetailDialog").close();

  if (target.matches("[data-open-task]")) await openTask(target.dataset.openTask);

  if (target.matches("[data-status]")) {
    await api(`/api/tasks/${target.dataset.task}/status`, {
      method: "POST",
      body: JSON.stringify({ status: target.dataset.status, user_id: state.user.user_id })
    });
    await refresh();
  }

  if (target.matches("[data-report]")) {
    const report = await api("/api/reports", {
      method: "POST",
      body: JSON.stringify({ report_type: target.dataset.report, user_id: state.user.user_id })
    });
    $("#reportResult").innerHTML = `
      <strong>Отчет сформирован.</strong><br>
      Период: ${formatDate(report.date_from)} - ${formatDate(report.date_to)}<br>
      <a href="${report.file_path}" target="_blank">Скачать CSV</a>
    `;
  }
});

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#loginError").textContent = "";
  const form = new FormData(event.currentTarget);
  try {
    const result = await api("/api/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form))
    });
    setSession(result.user);
    await loadAll();
    setView("dashboard");
  } catch (error) {
    $("#loginError").textContent = error.message;
  }
});

$("#taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form);
  payload.created_by = state.user.user_id;
  payload.items = payload.items.split("\n").map((item) => item.trim()).filter(Boolean);
  await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
  $("#taskDialog").close();
  event.currentTarget.reset();
  fillTaskFormOptions();
  await refresh();
  setView("tasks");
});

$("#taskDetail").addEventListener("submit", async (event) => {
  event.preventDefault();
  const taskId = state.activeTask.task.task_id;

  if (event.target.id === "checklistForm") {
    const items = $$("#checklistForm .check-item").map((label) => ({
      work_description: label.querySelector("span").textContent,
      is_completed: label.querySelector("input").checked
    }));
    const used_consumables = $$("#checklistForm [data-consumable]").map((input) => ({
      consumable_id: input.dataset.consumable,
      quantity: input.value
    }));
    const comments = $("#checklistForm textarea[name=comments]").value;
    const detail = await api(`/api/tasks/${taskId}/checklist`, {
      method: "POST",
      body: JSON.stringify({ user_id: state.user.user_id, items, used_consumables, comments })
    });
    state.activeTask = detail;
    $("#taskDetail").innerHTML = renderTaskDetail(detail);
    await refresh();
  }

  if (event.target.id === "photoForm") {
    const file = event.target.photo.files[0];
    const dataUrl = await fileToDataUrl(file);
    const detail = await api(`/api/tasks/${taskId}/photos`, {
      method: "POST",
      body: JSON.stringify({ user_id: state.user.user_id, photo_type: event.target.photo_type.value, data_url: dataUrl })
    });
    state.activeTask = detail;
    $("#taskDetail").innerHTML = renderTaskDetail(detail);
    await refresh();
  }

  if (event.target.id === "inspectionForm") {
    const form = new FormData(event.target);
    const payload = Object.fromEntries(form);
    payload.inspector_id = state.user.user_id;
    const detail = await api(`/api/tasks/${taskId}/inspection`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
    state.activeTask = detail;
    $("#taskDetail").innerHTML = renderTaskDetail(detail);
    await refresh();
  }
});

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function boot() {
  if (!state.user) {
    showLogin();
    return;
  }
  setSession(state.user);
  await loadAll();
  setView("dashboard");
}

boot();
