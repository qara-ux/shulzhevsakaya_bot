let funnelChart, editor;
let currentEditingNodeId = null, allNodes = [];
let currentLang = localStorage.getItem('lang') || 'ru';
let logsUsers = [];
let fp; // Flatpickr instance

const translations = {
    ru: {
        nav_overview: "Обзор", nav_clients: "Клиенты", nav_planner: "Рассылки", nav_constructor: "Конструктор", nav_logs: "Активность",
        stat_volume: "Выручка", stat_users: "Пользователи", stat_conv: "Конверсия",
        funnel_title: "Воронка продаж", crm_title: "База клиентов", funnel_growth: "Аналитика роста",
        table_user: "Клиент", table_email: "Email", table_status: "Статус",
        btn_save: "Применить", btn_add_node: "Создать блок", btn_delete: "Удалить блок",
        node_editor: "Настройки блока"
    },
    en: {
        nav_overview: "Overview", nav_clients: "Clients", nav_planner: "Planner", nav_constructor: "Constructor", nav_logs: "Logs",
        stat_volume: "Volume", stat_users: "Total Users", stat_conv: "Conversion",
        funnel_title: "Conversion Funnel", crm_title: "Customer Intelligence", funnel_growth: "Growth Analytics",
        table_user: "User", table_email: "Email", table_status: "Status",
        btn_save: "Apply", btn_add_node: "Create Block", btn_delete: "Delete Block",
        node_editor: "Node Settings"
    }
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    initDrawflow();
    updateDashboard();
    loadUsers();
    loadNodes();
    loadBroadcasts();
    loadLogsUsers();
    applyTranslations();
    
    // Init Flatpickr
    fp = flatpickr("#plan-date", {
        enableTime: true,
        dateFormat: "Y-m-d H:i",
        theme: "dark"
    });

    // Audience selection
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
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
}

// --- OVERVIEW & CHART ---
async function updateDashboard() {
    try {
        const r = await fetch('/api/stats');
        const data = await r.json();
        document.getElementById('revenue').innerText = `${data.revenue.toLocaleString()}₽`;
        document.getElementById('total_users').innerText = data.total_users;
        document.getElementById('conversion').innerText = `${data.conversion_rate || 0}%`;
        
        renderPremiumChart(data.funnel);
        renderVisualFunnel(data.funnel);
    } catch (e) { console.error(e); }
}

function renderPremiumChart(funnel) {
    const ctx = document.getElementById('funnelChart');
    if (!ctx) return;
    if (funnelChart) funnelChart.destroy();
    
    const labels = ["Starts", "Engagement", "Leads", "Payments", "Success"];
    const values = [funnel.starts, funnel.engagement, funnel.leads, funnel.payments, funnel.success];

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(168, 85, 247, 0.4)');
    gradient.addColorStop(1, 'rgba(168, 85, 247, 0)');

    funnelChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Activity',
                data: values,
                borderColor: '#a855f7',
                backgroundColor: gradient,
                borderWidth: 4,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#fff',
                pointBorderColor: '#a855f7',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#131316',
                    titleFont: { size: 14, weight: 'bold', family: 'Outfit' },
                    bodyFont: { size: 13, family: 'Inter' },
                    padding: 12,
                    displayColors: false,
                    borderWidth: 1,
                    borderColor: 'rgba(255,255,255,0.1)'
                }
            },
            scales: {
                y: { display: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888', font: { family: 'Inter' } } },
                x: { grid: { display: false }, ticks: { color: '#888', font: { family: 'Inter', weight: 'bold' } } }
            }
        }
    });
}

function renderVisualFunnel(funnel) {
    const container = document.getElementById('visual-funnel');
    if (!container) return;
    const stages = [
        { name: "Starts", val: funnel.starts },
        { name: "Engagement", val: funnel.engagement },
        { name: "Leads", val: funnel.leads },
        { name: "Payments", val: funnel.payments },
        { name: "Success", val: funnel.success }
    ];
    container.innerHTML = '';
    const maxVal = Math.max(...stages.map(s => s.val)) || 1;
    stages.forEach((s, i) => {
        const width = (s.val / maxVal) * 100;
        container.innerHTML += `
            <div class="funnel-stage-v2">
                <div class="stage-bar-v2" style="width: ${width}%"></div>
                <span class="stage-title">${s.name}</span>
                <span class="stage-val-v2">${s.val}</span>
            </div>
        `;
        if (i < stages.length - 1) {
            const drop = s.val ? Math.round((stages[i+1].val / s.val) * 100) : 0;
            container.innerHTML += `<div class="funnel-sep-v2">${drop}% CR</div>`;
        }
    });
}

// --- PLANNER ---
async function submitAdvancedPlan() {
    const msg = document.getElementById('plan-msg').value;
    const date = document.getElementById('plan-date').value;
    const filter = document.querySelector('.seg-btn.active').getAttribute('data-filter');
    
    if (!msg) return alert("Message cannot be empty");
    
    await fetch('/api/broadcasts', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ message: msg, send_at: date, filter_type: filter })
    });
    
    document.getElementById('plan-msg').value = '';
    loadBroadcasts();
}

async function loadBroadcasts() {
    const r = await fetch('/api/broadcasts');
    const data = await r.json();
    const list = document.getElementById('plan-queue');
    if (!list) return;
    document.getElementById('queue-count').innerText = `${data.length} messages`;
    list.innerHTML = '';
    data.forEach(b => {
        list.innerHTML += `
            <div class="queue-item">
                <div class="queue-info">
                    <h4>${b.message.substring(0, 50)}...</h4>
                    <div class="queue-meta">
                        <span>🎯 ${b.filter_type.toUpperCase()}</span>
                        <span>⏰ ${b.send_at ? new Date(b.send_at).toLocaleString() : 'ASAP'}</span>
                    </div>
                </div>
                <span class="badge ${b.is_sent ? 'paid' : 'pending'}">${b.is_sent ? 'SENT' : 'PENDING'}</span>
            </div>
        `;
    });
}

// --- LOGS ---
async function loadLogsUsers() {
    const r = await fetch('/api/users');
    logsUsers = await r.json();
    renderLogsSidebar(logsUsers);
}

function renderLogsSidebar(users) {
    const list = document.getElementById('log-user-list');
    if (!list) return;
    list.innerHTML = '';
    users.forEach(u => {
        list.innerHTML += `
            <div class="log-user-row" onclick="selectLogUser('${u.telegram_id}')" id="row-${u.telegram_id}">
                <strong>@${u.username || u.telegram_id}</strong>
                <span>${u.email || 'No email'}</span>
            </div>
        `;
    });
}

async function selectLogUser(id) {
    document.querySelectorAll('.log-user-row').forEach(r => r.classList.remove('active'));
    document.getElementById(`row-${id}`).classList.add('active');
    
    const user = logsUsers.find(u => u.telegram_id == id);
    document.getElementById('selected-user-name').innerText = `@${user.username || user.telegram_id}`;
    document.getElementById('selected-user-id').innerText = `ID: ${user.telegram_id}`;
    
    const r = await fetch(`/api/users/${id}/logs`);
    const logs = await r.json();
    const timeline = document.getElementById('log-timeline');
    timeline.innerHTML = '';
    if (logs.length === 0) {
        timeline.innerHTML = '<div class="empty-state-v2">No actions found</div>';
        return;
    }
    logs.forEach(l => {
        timeline.innerHTML += `
            <div class="timeline-card">
                <div class="timeline-date">${new Date(l.created_at).toLocaleString()}</div>
                <div class="timeline-event">${l.event_name.toUpperCase()}</div>
                <div class="timeline-data">${JSON.stringify(l.data)}</div>
            </div>
        `;
    });
}

// --- CONSTRUCTOR ---
async function loadNodes() {
    const r = await fetch('/api/nodes');
    allNodes = await r.json();
    renderNodesOnCanvas();
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

    // Draw connections with a small delay to ensure nodes are rendered
    setTimeout(() => {
        allNodes.forEach(node => {
            if (node.buttons) {
                node.buttons.forEach(btn => {
                    if (btn.next_node) {
                        try { editor.addConnection(node.id, btn.next_node, 'output_1', 'input_1'); } catch(e){}
                    }
                });
            }
            if (node.parent_node_id) {
                try { editor.addConnection(node.parent_node_id, node.id, 'output_1', 'input_1'); } catch(e){}
            }
        });
    }, 200);
}

function openSidepanel(nodeId) {
    const node = allNodes.find(n => n.id === nodeId);
    if (!node) return;
    currentEditingNodeId = nodeId;
    document.getElementById('edit-node-id').value = node.id;
    document.getElementById('edit-node-title').value = node.title;
    document.getElementById('edit-node-content').value = node.content;
    document.getElementById('edit-funnel-stage').value = node.funnel_stage || 'none';
    
    setNodeType(node.node_type || 'main');
    document.getElementById('edit-node-delay').value = node.delay || '';
    renderEditButtons(node.buttons || []);
    document.getElementById('node-sidepanel').classList.add('active');
}

function setNodeType(type) {
    document.querySelectorAll('.toggle-opt').forEach(b => b.classList.remove('active'));
    if (type === 'main') document.getElementById('opt-main').classList.add('active');
    else document.getElementById('opt-rem').classList.add('active');
    
    document.getElementById('edit-node-type').value = type;
    document.getElementById('reminder-extra').style.display = (type === 'reminder') ? 'block' : 'none';
}

function renderEditButtons(buttons) {
    const list = document.getElementById('node-buttons-list');
    list.innerHTML = '';
    buttons.forEach((btn, idx) => {
        list.innerHTML += `
            <div class="button-edit-item" style="display:flex; gap:8px; margin-bottom:12px;">
                <input type="text" value="${btn.text}" onchange="updateBtn(${idx}, 'text', this.value)" style="flex:1;">
                <select onchange="updateBtn(${idx}, 'next_node', this.value)" class="premium-select" style="width:140px;">
                    <option value="">No link</option>
                    ${allNodes.map(n => `<option value="${n.id}" ${btn.next_node === n.id ? 'selected' : ''}>${n.id}</option>`).join('')}
                </select>
                <button onclick="removeBtn(${idx})" class="close-btn-v2" style="width:36px; height:36px; padding:0;">✕</button>
            </div>
        `;
    });
}

window.updateBtn = (idx, field, val) => {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) node.buttons[idx][field] = val;
};

window.removeBtn = (idx) => {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) { node.buttons.splice(idx, 1); renderEditButtons(node.buttons); }
};

window.addNodeButton = () => {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (!node.buttons) node.buttons = [];
    node.buttons.push({ text: "New Button", next_node: "" });
    renderEditButtons(node.buttons);
};

async function saveNodeData() {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    const updated = {
        id: currentEditingNodeId,
        title: document.getElementById('edit-node-title').value,
        content: document.getElementById('edit-node-content').value,
        funnel_stage: document.getElementById('edit-funnel-stage').value,
        node_type: document.getElementById('edit-node-type').value,
        delay: document.getElementById('edit-node-delay').value,
        buttons: node.buttons
    };
    await fetch('/api/nodes', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(updated) });
    closeSidepanel(); loadNodes(); updateDashboard();
}

// --- CLIENTS ---
async function loadUsers() {
    const r = await fetch('/api/users');
    const users = await r.json();
    const tb = document.querySelector('#usersTable tbody');
    if (!tb) return;
    tb.innerHTML = '';
    users.forEach(u => {
        tb.innerHTML += `
            <tr>
                <td><strong>@${u.username || u.telegram_id}</strong></td>
                <td>${u.email || '—'}</td>
                <td><span class="badge ${u.is_paid ? 'paid' : 'pending'}" onclick="togglePaid('${u.telegram_id}')" style="cursor:pointer">${u.is_paid ? 'PAID' : 'FREE'}</span></td>
                <td style="text-align: right;"><button class="dm-btn" onclick="openDM('${u.telegram_id}', '@${u.username || u.telegram_id}')">MESSAGE</button></td>
            </tr>
        `;
    });
}

// --- GLOBAL EXPORTS ---
window.showTab = showTab;
window.setLanguage = (l) => { currentLang = l; localStorage.setItem('lang', l); applyTranslations(); };
window.selectLogUser = selectLogUser;
window.refreshLogs = () => { if(currentEditingNodeId) selectLogUser(currentEditingNodeId); };
window.setNodeType = setNodeType;
window.closeSidepanel = () => document.getElementById('node-sidepanel').classList.remove('active');
window.saveNodeData = saveNodeData;
window.addNewNode = async () => { 
    const id = prompt("Node Identifier (no spaces):"); 
    if(id) { 
        await fetch('/api/nodes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, title:"New Step", content:"...", node_type:"main"})}); 
        loadNodes(); 
    } 
};
window.deleteCurrentNode = async () => { if(confirm("Delete this block?")) { await fetch(`/api/nodes/${currentEditingNodeId}`, {method:'DELETE'}); window.closeSidepanel(); loadNodes(); } };
window.submitAdvancedPlan = submitAdvancedPlan;

function applyTranslations() {
    const t = translations[currentLang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.innerText = t[key];
    });
}
