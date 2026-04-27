let funnelChart, editor;
let currentEditingNodeId = null, allNodes = [];
let currentLang = localStorage.getItem('lang') || 'ru';

const translations = {
    ru: {
        nav_overview: "Обзор", nav_clients: "Клиенты", nav_planner: "Рассылки", nav_constructor: "Конструктор", nav_logs: "Активность",
        stat_volume: "Выручка", stat_users: "Пользователи", stat_conv: "Конверсия",
        funnel_title: "Воронка продаж", crm_title: "База клиентов", crm_search: "Поиск по базе...",
        table_user: "Клиент", table_email: "Email", table_status: "Статус",
        btn_save: "Сохранить", btn_add_node: "Создать блок", btn_delete: "Удалить",
        stage_starts: "Входы", stage_engagement: "Интерес", stage_leads: "Лиды", stage_payments: "Оплата", stage_success: "Успех",
        node_editor: "Редактор блока", label_node_id: "ID Блока", label_node_title: "Название шага",
        label_node_content: "Текст сообщения", label_funnel_stage: "Этап воронки", label_buttons: "Кнопки",
        label_node_type: "Тип блока", label_delay: "Задержка (напр: 2h, 24h)"
    },
    en: {
        nav_overview: "Overview", nav_clients: "Clients", nav_planner: "Planner", nav_constructor: "Constructor", nav_logs: "Logs",
        stat_volume: "Volume", stat_users: "Total Users", stat_conv: "Conversion",
        funnel_title: "Conversion Funnel", crm_title: "Customer Base", crm_search: "Search...",
        table_user: "User", table_email: "Email", table_status: "Status",
        btn_save: "Save", btn_add_node: "Create Block", btn_delete: "Delete",
        stage_starts: "Starts", stage_engagement: "Engagement", stage_leads: "Leads", stage_payments: "Payments", stage_success: "Success",
        node_editor: "Node Editor", label_node_id: "Node ID", label_node_title: "Step Title",
        label_node_content: "Message Content", label_funnel_stage: "Funnel Stage", label_buttons: "Buttons",
        label_node_type: "Node Type", label_delay: "Delay (e.g. 2h, 24h)"
    }
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    initDrawflow();
    updateDashboard();
    loadUsers();
    loadNodes();
    loadBroadcasts();
    applyTranslations();
});

function initDrawflow() {
    const id = document.getElementById("drawflow");
    if (!id) return;
    editor = new Drawflow(id);
    editor.reroute = true;
    editor.start();

    editor.on('nodeSelected', (id) => {
        const node = editor.getNodeFromId(id);
        openSidepanel(node.data.id);
    });

    editor.on('nodeMoved', (id) => {
        const node = editor.getNodeFromId(id);
        saveNodePosition(node.data.id, node.pos_x, node.pos_y);
    });

    editor.on('connectionCreated', async (info) => {
        const sourceNode = editor.getNodeFromId(info.output_id).data.id;
        const targetNodeId = editor.getNodeFromId(info.input_id).data.id;
        const target = allNodes.find(n => n.id === targetNodeId);
        if (target && target.node_type === 'reminder') {
            await fetch('/api/nodes', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: target.id, parent_node_id: sourceNode })
            });
            loadNodes();
        }
    });
}

// --- NAVIGATION ---
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(`${tabId}-tab`).classList.add('active');
    const btn = Array.from(document.querySelectorAll('.nav-btn')).find(b => {
        const onclick = b.getAttribute('onclick');
        return onclick && onclick.includes(tabId);
    });
    if (btn) btn.classList.add('active');
    
    if (tabId === 'constructor') {
        setTimeout(() => editor.zoom_reset(), 100);
    }
}

// --- DASHBOARD DATA ---
async function updateDashboard() {
    try {
        const r = await fetch('/api/stats');
        const data = await r.json();
        document.getElementById('revenue').innerText = `${data.revenue.toLocaleString()}₽`;
        document.getElementById('total_users').innerText = data.total_users;
        document.getElementById('conversion').innerText = `${data.conversion_rate || 0}%`;
        
        const t = translations[currentLang];
        const stages = [
            { label: t.stage_starts, val: data.funnel.starts || 0 },
            { label: t.stage_engagement, val: data.funnel.engagement || 0 },
            { label: t.stage_leads, val: data.funnel.leads || 0 },
            { label: t.stage_payments, val: data.funnel.payments || 0 },
            { label: t.stage_success, val: data.funnel.success || 0 }
        ];

        const container = document.getElementById('visual-funnel');
        if (container) {
            container.innerHTML = '';
            const maxVal = Math.max(...stages.map(s => s.val)) || 1;
            stages.forEach((s, i) => {
                const width = (s.val / maxVal) * 100;
                container.innerHTML += `<div class="funnel-stage"><div class="funnel-bar" style="width: ${width}%"></div><div class="stage-info"><div>${s.label}</div></div><div class="stage-val">${s.val}</div></div>`;
                if (i < stages.length - 1) { 
                    const drop = s.val ? Math.round((stages[i+1].val / s.val) * 100) : 0; 
                    container.innerHTML += `<div class="funnel-sep" data-drop="${drop}% CR"></div>`; 
                }
            });
        }
    } catch (e) { console.error(e); }
}

async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const users = await response.json();
        const tb = document.querySelector('#usersTable tbody');
        if (!tb) return;
        tb.innerHTML = '';
        users.forEach(u => {
            const username = u.username || u.telegram_id;
            tb.innerHTML += `<tr>
                <td>@${username}</td>
                <td>${u.email || '—'}</td>
                <td><span class="badge ${u.is_paid ? 'paid' : 'pending'}" onclick="togglePaid('${u.telegram_id}')" style="cursor:pointer">${u.is_paid ? 'PAID' : 'FREE'}</span></td>
                <td><button class="dm-btn" onclick="openDM('${u.telegram_id}', '${username}')">DM</button></td>
            </tr>`;
        });
    } catch (e) { console.error(e); }
}

// --- CONSTRUCTOR FUNCTIONS ---
async function loadNodes() {
    try {
        const response = await fetch('/api/nodes');
        allNodes = await response.json();
        renderNodesOnCanvas();
    } catch (e) { console.error(e); }
}

function renderNodesOnCanvas() {
    if (!editor) return;
    editor.clear();
    allNodes.forEach(node => {
        const isReminder = node.node_type === 'reminder';
        const html = `
            <div class="node-view">
                <div class="node-view-header">${node.id}</div>
                <div class="node-view-body">
                    <div class="node-view-title">${node.title}</div>
                    <div class="node-view-content">${node.content}</div>
                </div>
            </div>
        `;
        editor.addNode(node.id, 1, 1, node.x || 100, node.y || 100, isReminder ? 'reminder-node' : 'main-node', { id: node.id }, html);
    });

    allNodes.forEach(node => {
        if (node.buttons) {
            node.buttons.forEach(btn => {
                if (btn.next_node) editor.addConnection(node.id, btn.next_node, 'output_1', 'input_1');
            });
        }
        if (node.parent_node_id) {
            editor.addConnection(node.parent_node_id, node.id, 'output_1', 'input_1');
        }
    });
}

function openSidepanel(nodeId) {
    const node = allNodes.find(n => n.id === nodeId);
    if (!node) return;
    currentEditingNodeId = nodeId;
    document.getElementById('edit-node-id').value = node.id;
    document.getElementById('edit-node-title').value = node.title;
    document.getElementById('edit-node-content').value = node.content;
    document.getElementById('edit-funnel-stage').value = node.funnel_stage || 'none';
    
    const type = node.node_type || 'main';
    selectOption('node-type', type, type === 'main' ? 'Основной' : 'Дожим');
    document.getElementById('edit-node-delay').value = node.delay || '';
    renderEditButtons(node.buttons || []);
    document.getElementById('node-sidepanel').classList.add('active');
}

function closeSidepanel() { document.getElementById('node-sidepanel').classList.remove('active'); }

function renderEditButtons(buttons) {
    const list = document.getElementById('node-buttons-list');
    list.innerHTML = '';
    buttons.forEach((btn, idx) => {
        list.innerHTML += `
            <div class="button-edit-item" style="display:flex; gap:8px; margin-bottom:8px;">
                <input type="text" value="${btn.text}" onchange="updateButton(${idx}, 'text', this.value)" style="flex:1; background:#000; border:1px solid var(--border); color:white; padding:8px; border-radius:6px;">
                <select onchange="updateButton(${idx}, 'next_node', this.value)" style="background:#000; color:white; border:1px solid var(--border); padding:8px; border-radius:6px;">
                    <option value="">Link to...</option>
                    ${allNodes.map(n => `<option value="${n.id}" ${btn.next_node === n.id ? 'selected' : ''}>${n.id}</option>`).join('')}
                </select>
                <button onclick="removeButton(${idx})" style="background:none; border:none; color:#ff4444; cursor:pointer;">✕</button>
            </div>
        `;
    });
}

function updateButton(idx, field, value) {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) node.buttons[idx][field] = value;
}

function removeButton(idx) {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) { node.buttons.splice(idx, 1); renderEditButtons(node.buttons); }
}

function addNodeButton() {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) {
        if (!node.buttons) node.buttons = [];
        node.buttons.push({ text: "New Button", next_node: "" });
        renderEditButtons(node.buttons);
    }
}

async function saveNodeData() {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    const updatedData = {
        id: currentEditingNodeId,
        title: document.getElementById('edit-node-title').value,
        content: document.getElementById('edit-node-content').value,
        funnel_stage: document.getElementById('edit-funnel-stage').value,
        node_type: document.getElementById('node-type-val').getAttribute('data-val'),
        delay: document.getElementById('edit-node-delay').value,
        buttons: node.buttons
    };
    await fetch('/api/nodes', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(updatedData) });
    closeSidepanel(); loadNodes(); updateDashboard();
}

async function saveNodePosition(nodeId, x, y) {
    await fetch(`/api/nodes/${nodeId}/position`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ x, y }) });
}

// --- MODALS & HELPERS ---
function showPModal(title, text, confirmBtnText, onConfirm) {
    document.getElementById('p-modal-title').innerText = title;
    document.getElementById('p-modal-text').innerText = text;
    document.getElementById('p-modal-confirm').innerText = confirmBtnText;
    document.getElementById('p-modal-confirm').onclick = () => { onConfirm(); closePModal(); };
    document.getElementById('p-modal').classList.add('active');
}
function closePModal() { document.getElementById('p-modal').classList.remove('active'); }

function selectOption(idPrefix, val, label) {
    const valEl = document.getElementById(`${idPrefix}-val`);
    if (valEl) { valEl.innerText = label; valEl.setAttribute('data-val', val); }
    document.getElementById(`${idPrefix}-options`).classList.remove('show');
    if (idPrefix === 'node-type') document.getElementById('reminder-settings').style.display = (val === 'reminder') ? 'block' : 'none';
}
function toggleSelect(id) { document.getElementById(id.replace('-select', '-options')).classList.toggle('show'); }

function applyTranslations() {
    const t = translations[currentLang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.innerText = t[key];
    });
}

// --- OTHER ---
async function loadBroadcasts() {
    const r = await fetch('/api/broadcasts');
    const data = await r.json();
    const list = document.getElementById('plan-queue');
    if (!list) return;
    list.innerHTML = '';
    data.forEach(b => {
        list.innerHTML += `<div class="plan-item"><div class="plan-header"><span class="plan-type-pill">${b.type}</span></div><div class="plan-msg-text">${b.message_text}</div></div>`;
    });
}

async function togglePaid(userId) {
    if (!confirm("Change status?")) return;
    await fetch(`/api/users/${userId}/toggle_paid`, { method: 'POST' });
    loadUsers(); updateDashboard();
}

// Window Exports
window.showTab = showTab;
window.setLanguage = (l) => { currentLang = l; localStorage.setItem('lang', l); applyTranslations(); };
window.addNewNode = async () => { const id = prompt("ID:"); if(id) { await fetch('/api/nodes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, title:"New", content:"...", node_type:"main"})}); loadNodes(); } };
window.saveNodeData = saveNodeData;
window.closeSidepanel = closeSidepanel;
window.toggleSelect = toggleSelect;
window.selectOption = selectOption;
window.addNodeButton = addNodeButton;
window.removeButton = removeButton;
window.updateButton = updateButton;
window.closePModal = closePModal;
window.togglePaid = togglePaid;
window.deleteCurrentNode = async () => { if(confirm("Delete?")) { await fetch(`/api/nodes/${currentEditingNodeId}`, {method:'DELETE'}); closeSidepanel(); loadNodes(); } };
