let funnelChart;
let currentEditingNodeId = null, allNodes = [];
let isDraggingNode = false, isPanning = false;
let dragNode = null, dragOffset = { x: 0, y: 0 };
let canvasOffset = { x: 0, y: 0 }, panStart = { x: 0, y: 0 }, zoom = 1;

async function updateDashboard() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
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
                if (i < stages.length - 1) { const drop = s.val ? Math.round((stages[i+1].val / s.val) * 100) : 0; container.innerHTML += `<div class="funnel-sep" data-drop="${drop}% CR"></div>`; }
            });

            const ctx = document.getElementById('funnelChart').getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(167, 139, 250, 0.2)');
            gradient.addColorStop(1, 'rgba(167, 139, 250, 0)');

            if (funnelChart) {
                funnelChart.data.labels = stages.map(s => s.label);
                funnelChart.data.datasets[0].data = stages.map(s => s.val);
                funnelChart.update('none');
            } else {
                funnelChart = new Chart(ctx, { 
                    type: 'line', 
                    data: { 
                        labels: stages.map(s => s.label), 
                        datasets: [{ 
                            data: stages.map(s => s.val), 
                            borderColor: '#a78bfa', 
                            borderWidth: 3, 
                            fill: true, 
                            backgroundColor: gradient,
                            tension: 0.4,
                            pointRadius: 4,
                            pointBackgroundColor: '#a78bfa',
                            pointBorderColor: '#000',
                            pointBorderWidth: 2,
                            pointHoverRadius: 7
                        }] 
                    }, 
                    options: { 
                        responsive: true, maintainAspectRatio: false, 
                        scales: { 
                            x: { 
                                grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                                ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 10 } }
                            }, 
                            y: { 
                                beginAtZero: true,
                                grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                                ticks: { 
                                    color: 'rgba(255,255,255,0.4)', 
                                    font: { size: 10 },
                                    padding: 10,
                                    callback: function(value) {
                                        if (value >= 1000) return (value / 1000).toFixed(1) + 'k';
                                        return value;
                                    }
                                }
                            } 
                        }, 
                        plugins: { 
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: '#131316',
                                titleColor: '#fff',
                                bodyColor: '#a78bfa',
                                borderColor: 'rgba(255,255,255,0.1)',
                                borderWidth: 1,
                                padding: 12,
                                displayColors: false,
                                callbacks: {
                                    label: function(context) {
                                        return `Count: ${context.parsed.y}`;
                                    }
                                }
                            }
                        } 
                    } 
                });
            }
        }
    } catch (e) { console.error(e); }
}

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.getElementById(tabId + '-tab').classList.add('active');
    
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = Array.from(document.querySelectorAll('.nav-btn')).find(btn => btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(tabId));
    if (activeBtn) activeBtn.classList.add('active');

    if (tabId === 'constructor') loadNodes();
    if (tabId === 'overview') updateDashboard();
    if (tabId === 'clients') loadUsers();
    if (tabId === 'planner') loadPlannerQueue();
    if (tabId === 'logs') loadLogsUsers();
}

async function loadUsers() {
    const r = await fetch('/api/users');
    const users = await r.json();
    const tb = document.querySelector('#usersTable tbody');
    if (!tb) return;
    tb.innerHTML = '';
    users.forEach(u => {
        const username = u.username || u.telegram_id;
        tb.innerHTML += `<tr>
            <td>@${username}</td>
            <td>${u.email || '—'}</td>
            <td><span class="badge ${u.is_paid ? 'paid' : 'pending'}">${u.is_paid ? 'PAID' : 'FREE'}</span></td>
            <td><button class="dm-btn" onclick="openDM('${u.telegram_id}', '${username}')">DM</button></td>
        </tr>`;
    });
}

let currentDMUserId = null;
function openDM(userId, username) {
    currentDMUserId = userId;
    document.getElementById('dm-username').innerText = `@${username}`;
    document.getElementById('dm-modal').style.display = 'flex';
    document.getElementById('dm-text').value = '';
}

function closeDM() {
    document.getElementById('dm-modal').style.display = 'none';
}

async function sendDM() {
    const text = document.getElementById('dm-text').value;
    if (!text || !currentDMUserId) return;

    try {
        const r = await fetch('/api/send_direct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentDMUserId, message: text })
        });
        if (r.ok) {
            alert('Message sent!');
            closeDM();
        } else {
            alert('Failed to send message.');
        }
    } catch (e) {
        console.error(e);
        alert('Error sending message.');
    }
}

async function loadPlannerQueue() {
    const r = await fetch('/api/planner/list');
    const jobs = await r.json();
    const list = document.getElementById('plan-queue');
    if (!list) return;
    
    if (jobs.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                <p>No scheduled messages in queue</p>
            </div>
        `;
        return;
    }
    list.innerHTML = '';
    
    jobs.forEach(j => {
        const utcDate = j.send_at.includes('Z') ? j.send_at : j.send_at + 'Z';
        const date = new Date(utcDate).toLocaleString();
        
        list.innerHTML += `<div class="plan-item">
            <div class="plan-header">
                <span class="plan-type-pill">${j.filter_type.toUpperCase()}</span>
                <div class="plan-meta-actions">
                    <span class="plan-timestamp">${date}</span>
                    <button onclick="deletePlan(${j.id})" class="delete-btn" title="Delete">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="plan-body">
                <div class="plan-msg-text">${j.message}</div>
            </div>
        </div>`;
    });
}

function toggleCustomSelect(id) {
    const el = document.getElementById(id);
    const all = document.querySelectorAll('.select-options');
    all.forEach(s => { if(s.id !== id) s.style.display = 'none'; });
    el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

function selectOption(hiddenId, val, label) {
    document.getElementById(hiddenId).value = val;
    document.getElementById(`${hiddenId}-selected`).querySelector('span').innerText = label;
    const opts = document.getElementById(`${hiddenId}-select`).querySelectorAll('.select-option');
    opts.forEach(o => o.classList.remove('selected'));
    
    // Toggle fields for Planner
    if (hiddenId === 'plan-type') {
        document.getElementById('once-fields').style.display = val === 'once' ? 'block' : 'none';
        document.getElementById('weekly-fields').style.display = val === 'weekly' ? 'block' : 'none';
    }
}

async function submitPlan() {
    const message = document.getElementById('plan-msg').value;
    const filter_type = document.getElementById('plan-filter').value;
    const type = document.getElementById('plan-type').value;
    
    if(!message) return alert("Please enter message");

    let payload = {
        message,
        filter_type,
        is_recurring: type === 'weekly',
        send_at: null,
        recurrence: null
    };

    if (type === 'once') {
        const dateStr = document.getElementById('plan-date-picker').value; // DD.MM.YYYY
        const timeStr = document.getElementById('plan-time-picker').value; // HH:MM
        if (!dateStr || !timeStr) return alert("Please select date and time");
        
        // Convert DD.MM.YYYY to YYYY-MM-DD for reliable parsing
        const [d, m, y] = dateStr.split('.');
        payload.send_at = new Date(`${y}-${m}-${d}T${timeStr}:00`).toISOString();
    } else {
        const time = document.getElementById('plan-time-freq').value;
        const checkedDays = Array.from(document.querySelectorAll('.day-picker input:checked')).map(i => parseInt(i.value));
        if (!checkedDays.length) return alert("Please select at least one day");
        payload.recurrence = { days: checkedDays, time: time };
        payload.end_at = document.getElementById('plan-end').value || null;
    }

    try {
        const r = await fetch('/api/planner', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if(r.ok) {
            alert("Broadcast scheduled!");
            document.getElementById('plan-msg').value = '';
            loadPlannerQueue();
        } else {
            const err = await r.json();
            alert(`Error: ${err.detail || 'Unknown error'}`);
        }
    } catch(e) { 
        console.error(e); 
        alert("System error. Check logs.");
    }
}

async function deletePlan(id) {
    if(!confirm("Delete this broadcast?")) return;
    await fetch(`/api/planner/${id}`, { method: 'DELETE' });
    loadPlannerQueue();
}

// --- LOGS SYSTEM ---
let allLogUsers = [];

async function loadLogsUsers() {
    const r = await fetch('/api/users');
    allLogUsers = await r.json();
    renderLogUsers(allLogUsers);
}

function renderLogUsers(users) {
    const list = document.getElementById('log-user-list');
    if (!list) return;
    list.innerHTML = '';
    users.forEach(u => {
        const statusTag = u.is_paid 
            ? '<span class="user-status-tag status-paid">PAID</span>' 
            : '<span class="user-status-tag status-free">FREE</span>';
        list.innerHTML += `
            <div class="log-user-item" onclick="viewUserLogs(${u.telegram_id}, '${u.username || 'Anonymous'}')">
                <strong>
                    ${u.username ? '@' + u.username : 'User ' + u.telegram_id}
                    ${statusTag}
                </strong>
                <span>ID: ${u.telegram_id}</span>
            </div>
        `;
    });
}

let currentUserLogs = [];

async function viewUserLogs(userId, username) {
    document.querySelectorAll('.log-user-item').forEach(el => el.classList.remove('active'));
    if (event && event.currentTarget) event.currentTarget.classList.add('active');
    
    document.getElementById('log-header').querySelector('h3').innerText = `Activity for @${username}`;
    document.getElementById('log-filter-container').style.display = 'flex';
    
    const r = await fetch(`/api/logs/${userId}`);
    currentUserLogs = await r.json();
    renderTimeline(currentUserLogs);
}

function renderTimeline(logs) {
    const timeline = document.getElementById('log-timeline');
    timeline.innerHTML = '';
    
    if (logs.length === 0) {
        timeline.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                <p>No activity logs found for this period</p>
            </div>
        `;
        return;
    }

    logs.forEach(l => {
        const dateObj = new Date(l.created_at + 'Z');
        const date = dateObj.toLocaleString();
        let dataStr = '';
        let tagClass = 'tag-action';
        let tagText = 'Action';

        if (l.event_name === 'message_received') {
            tagClass = 'tag-msg';
            tagText = 'Message';
            dataStr = `<div class="timeline-data">${l.data.text}</div>`;
        } else if (l.event_name.startsWith('node_')) {
            tagClass = 'tag-step';
            tagText = 'Step';
            dataStr = `<div class="timeline-data">Entered: ${l.event_name.replace('node_', '')}</div>`;
        } else if (l.event_name.includes('payment_success')) {
            tagClass = 'tag-pay';
            tagText = 'Payment';
        } else if (l.event_name.includes('payment') || l.event_name.includes('pay')) {
            tagClass = 'tag-action';
            tagText = 'Billing';
        }

        if (l.data && !dataStr) {
            dataStr = `<div class="timeline-data">${JSON.stringify(l.data)}</div>`;
        }
        
        timeline.innerHTML += `
            <div class="timeline-item">
                <div class="timeline-date">${date}</div>
                <div class="timeline-event">
                    <span class="log-tag ${tagClass}">${tagText}</span>
                    ${l.event_name.toUpperCase().replace('_', ' ')}
                </div>
                ${dataStr}
            </div>
        `;
    });
}

function applyLogDateFilter() {
    const selectedDate = document.getElementById('log-date-filter').value;
    if (!selectedDate) {
        renderTimeline(currentUserLogs);
        return;
    }
    const filtered = currentUserLogs.filter(l => {
        const eventDate = new Date(l.created_at + 'Z').toISOString().split('T')[0];
        return eventDate === selectedDate;
    });
    renderTimeline(filtered);
}

function clearLogDateFilter() {
    document.getElementById('log-date-filter').value = '';
    renderTimeline(currentUserLogs);
}

// --- CONSTRUCTOR CORE ---
async function loadNodes() {
    try {
        const response = await fetch('/api/nodes');
        allNodes = await response.json();
        renderCanvas();
        initCanvasControls();
    } catch(e) { console.error("Load failed", e); }
}

function renderCanvas() {
    const nodesLayer = document.getElementById('flow-nodes');
    if(!nodesLayer) return;
    nodesLayer.innerHTML = '';
    
    allNodes.forEach(node => {
        const div = document.createElement('div');
        div.className = `flow-node ${currentEditingNodeId === node.id ? 'active' : ''}`;
        div.id = `node-${node.id}`;
        div.style.left = `${node.x}px`;
        div.style.top = `${node.y}px`;
        div.style.position = 'absolute';
        
        div.innerHTML = `
            <div class="node-input-port" onmouseup="onDropPort(event, '${node.id}')"></div>
            <div class="node-header">
                <span class="node-id">#${node.id}</span>
            </div>
            <div class="node-body">
                <div class="node-title">${node.title || 'unnamed'}</div>
                <div class="node-btns">
                    ${(node.buttons || []).map((b, i) => `
                        <div class="node-btn" id="btn-${node.id}-${i}">
                            <span>${b.text}</span>
                            <div class="node-output-port" onmousedown="onStartConnect(event, '${node.id}', ${i})"></div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        div.onmousedown = (e) => {
            if (e.target.closest('.node-output-port') || e.target.closest('.node-input-port')) return;
            startDraggingNode(e, node);
        };
        div.onclick = (e) => { if(!isDraggingNode) editNode(node.id); };
        nodesLayer.appendChild(div);
    });
    try { drawConnections(); } catch(e) {}
}

function drawConnections() {
    const s = document.getElementById('flow-svg'); if (!s) return;
    const canvas = document.getElementById('flow-canvas');
    const cr = canvas.getBoundingClientRect();
    
    // Maintain defs (arrows)
    const defs = s.querySelector('defs');
    s.innerHTML = '';
    if(defs) s.appendChild(defs);
    
    allNodes.forEach(node => {
        (node.buttons || []).forEach((btn, i) => {
            if (btn.next_node) {
                const targetNode = allNodes.find(n => n.id === btn.next_node);
                if (targetNode) {
                    const port = document.querySelector(`#btn-${node.id}-${i} .node-output-port`);
                    const targetEl = document.getElementById(`node-${targetNode.id}`);
                    if (port && targetEl) {
                        const pr = port.getBoundingClientRect();
                        const tr = targetEl.querySelector('.node-input-port').getBoundingClientRect();
                        
                        // Corrected: Subtract canvas client rect and DIVIDE by zoom 
                        // to get coordinates in the 10000x10000 space
                        const x1 = (pr.left + pr.width/2 - cr.left) / zoom;
                        const y1 = (pr.top + pr.height/2 - cr.top) / zoom;
                        const x2 = (tr.left + tr.width/2 - cr.left) / zoom;
                        const y2 = (tr.top + tr.height/2 - cr.top) / zoom;
                        
                        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                        // Smoother Bezier curve
                        const dx = Math.abs(x1 - x2) / 2;
                        path.setAttribute("d", `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
                        path.setAttribute("stroke", "rgba(255, 255, 255, 0.3)");
                        path.setAttribute("stroke-width", "2");
                        path.setAttribute("fill", "none");
                        path.setAttribute("marker-end", "url(#arrowhead)");
                        s.appendChild(path);
                    }
                }
            }
        });
    });
}

function initCanvasControls() {
    const tab = document.getElementById('constructor-tab');
    const canvas = document.getElementById('flow-canvas');
    if (!tab || !canvas) return;
    
    tab.onmousedown = (e) => {
        if (e.target.closest('.flow-node') || e.target.closest('.side-panel')) return;
        isPanning = true;
        panStart.x = e.clientX - canvasOffset.x;
        panStart.y = e.clientY - canvasOffset.y;
    };
    window.onmousemove = (e) => {
        if (isPanning) {
            canvasOffset.x = e.clientX - panStart.x;
            canvasOffset.y = e.clientY - panStart.y;
            canvas.style.transform = `translate(${canvasOffset.x}px, ${canvasOffset.y}px) scale(${zoom})`;
        }
    };
    window.onmouseup = () => { isPanning = false; };
}

function startDraggingNode(e, node) {
    isDraggingNode = true;
    const el = document.getElementById(`node-${node.id}`);
    const canvas = document.getElementById('flow-canvas');
    const cr = canvas.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    
    dragOffset.x = (e.clientX - rect.left) / zoom;
    dragOffset.y = (e.clientY - rect.top) / zoom;
    
    let ticking = false;
    const onMove = (me) => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                node.x = (me.clientX - cr.left)/zoom - dragOffset.x;
                node.y = (me.clientY - cr.top)/zoom - dragOffset.y;
                el.style.left = `${node.x}px`;
                el.style.top = `${node.y}px`;
                drawConnections();
                ticking = false;
            });
            ticking = true;
        }
    };
    const onUp = async () => {
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
        await fetch(`/api/nodes/${node.id}/position`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: Math.round(node.x), y: Math.round(node.y)})
        });
        setTimeout(() => isDraggingNode = false, 100);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
}

function editNode(id) {
    currentEditingNodeId = id;
    const node = allNodes.find(n => n.id === id);
    if (!node) return;
    
    document.getElementById('edit-node-id').innerText = `@${node.id}`;
    document.getElementById('edit-node-title').value = node.title || '';
    document.getElementById('edit-node-content').value = node.content || '';
    
    const list = document.getElementById('buttons-list');
    list.innerHTML = '';
    (node.buttons || []).forEach((b, i) => {
        list.innerHTML += `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); padding:16px; border-radius:12px; margin-bottom:12px;">
                <div class="form-group">
                    <label style="font-size:9px;">Button Text</label>
                    <input type="text" value="${b.text}" onchange="updateBtnText(${i}, this.value)" style="width:100%; background:none; border:none; color:white; border-bottom:1px solid var(--border); padding:8px 0;">
                </div>
                <div class="form-group" style="margin-top:12px;">
                    <label style="font-size:9px;">Next Block</label>
                    <select onchange="updateBtnLink(${i}, this.value)" style="width:100%; background:#000; color:white; border:1px solid var(--border); border-radius:8px; padding:8px;">
                        <option value="">None</option>
                        ${allNodes.map(n => `<option value="${n.id}" ${b.next_node === n.id ? 'selected' : ''}>#${n.id} ${n.title}</option>`).join('')}
                    </select>
                </div>
                <button onclick="removeBtn(${i})" style="margin-top:12px; background:none; border:none; color:#ff4444; font-size:10px; cursor:pointer;">✕ Remove Button</button>
            </div>
        `;
    });
    
    // Populate Follow-up fields
    document.getElementById('edit-follow-up-delay').value = node.follow_up_delay || '';
    const fuSelect = document.getElementById('edit-follow-up-node');
    fuSelect.innerHTML = '<option value="">Disabled</option>' + 
        allNodes.map(n => `<option value="${n.id}" ${node.follow_up_node === n.id ? 'selected' : ''}>#${n.id} ${n.title}</option>`).join('');
    
    document.getElementById('node-editor').style.display = 'block';
    renderCanvas();
}

function updateBtnText(idx, val) {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) node.buttons[idx].text = val;
}

function updateBtnLink(idx, val) {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) {
        node.buttons[idx].next_node = val || null;
        renderCanvas();
    }
}

function removeBtn(idx) {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) {
        node.buttons.splice(idx, 1);
        editNode(currentEditingNodeId);
    }
}

function addButton() {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (node) {
        if (!node.buttons) node.buttons = [];
        node.buttons.push({ text: "New Button", next_node: null });
        editNode(currentEditingNodeId);
    }
}

// Drag & Drop Connections Logic
window.onStartConnect = (e, nodeId, btnIndex) => {
    e.stopPropagation();
    connectingFrom = { nodeId, btnIndex };
    window.addEventListener('mousemove', onDragConnection);
    window.addEventListener('mouseup', onStopConnect);
};

function onDragConnection(e) {
    if (!connectingFrom) return;
    const s = document.getElementById('flow-svg');
    const cr = document.getElementById('flow-canvas').getBoundingClientRect();
    const port = document.querySelector(`#btn-${connectingFrom.nodeId}-${connectingFrom.btnIndex} .node-output-port`);
    if (!port) return;
    
    const pr = port.getBoundingClientRect();
    const x1 = (pr.left + pr.width/2 - cr.left)/zoom, y1 = (pr.top + pr.height/2 - cr.top)/zoom;
    const x2 = (e.clientX - cr.left)/zoom, y2 = (e.clientY - cr.top)/zoom;
    
    let line = document.getElementById('drag-line');
    if(!line) {
        line = document.createElementNS("http://www.w3.org/2000/svg", "path");
        line.id = 'drag-line';
        line.setAttribute("stroke", "var(--warning)");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("fill", "none");
        line.setAttribute("stroke-dasharray", "5,5");
        s.appendChild(line);
    }
    line.setAttribute("d", `M ${x1} ${y1} C ${x1 + 50} ${y1}, ${x2 - 50} ${y2}, ${x2} ${y2}`);
}

async function onDropPort(e, targetNodeId) {
    if (connectingFrom && connectingFrom.nodeId !== targetNodeId) {
        console.log("Connecting", connectingFrom.nodeId, "to", targetNodeId);
        const node = allNodes.find(n => n.id === connectingFrom.nodeId);
        if (node && node.buttons[connectingFrom.btnIndex]) {
            node.buttons[connectingFrom.btnIndex].next_node = targetNodeId;
            await fetch(`/api/nodes/${node.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(node)
            });
            connectingFrom = null; // Clear before reload
            loadNodes();
        }
    }
}

function onStopConnect() {
    // Small delay to allow onDropPort to fire first
    setTimeout(() => {
        connectingFrom = null;
        const line = document.getElementById('drag-line');
        if(line) line.remove();
        window.removeEventListener('mousemove', onDragConnection);
        window.removeEventListener('mouseup', onStopConnect);
    }, 50);
}

function closeEditor() {
    document.getElementById('node-editor').style.display = 'none';
    currentEditingNodeId = null;
    renderCanvas();
}

async function saveNode() {
    const node = allNodes.find(n => n.id === currentEditingNodeId);
    if (!node) return;
    node.title = document.getElementById('edit-node-title').value;
    node.content = document.getElementById('edit-node-content').value;
    node.follow_up_delay = parseInt(document.getElementById('edit-follow-up-delay').value) || null;
    node.follow_up_node = document.getElementById('edit-follow-up-node').value || null;

    await fetch(`/api/nodes/${node.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(node)
    });
    closeEditor();
    loadNodes();
}

async function createNewNode() {
    const id = prompt("Node ID (unique):");
    if (!id) return;
    await fetch('/api/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, title: "New Node", content: "Content here...", buttons: [], x: 500, y: 300 })
    });
    loadNodes();
}

const translations = {
    ru: {
        nav_overview: "Обзор", nav_clients: "Clients", nav_planner: "Рассылки", nav_constructor: "Конструктор", nav_logs: "Активность",
        stat_volume: "Выручка", stat_users: "Пользователи", stat_conv: "Конверсия",
        funnel_title: "Воронка продаж", crm_title: "База клиентов", crm_search: "Поиск по базе...",
        table_user: "Клиент", table_email: "Email", table_status: "Статус",
        btn_save: "Сохранить", btn_add_node: "Создать блок",
        stage_starts: "Входы", stage_engagement: "Интерес", stage_leads: "Лиды", stage_payments: "Оплата", stage_success: "Успех"
    },
    en: {
        nav_overview: "Overview", nav_clients: "Clients", nav_planner: "Planner", nav_constructor: "Constructor", nav_logs: "Logs",
        stat_volume: "Volume", stat_users: "Total Users", stat_conv: "Conversion",
        funnel_title: "Conversion Funnel", crm_title: "Customer Base", crm_search: "Search...",
        table_user: "User", table_email: "Email", table_status: "Status",
        btn_save: "Save Stage", btn_add_node: "Create Node",
        stage_starts: "Starts", stage_engagement: "Engagement", stage_leads: "Leads", stage_payments: "Payments", stage_success: "Success"
    }
};

let currentLang = localStorage.getItem('lang') || 'ru';

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    applyTranslations();
    
    // UI feedback
    document.querySelectorAll('.lang-switcher button').forEach(b => b.classList.remove('active'));
    document.getElementById(`lang-${lang}`).classList.add('active');
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[currentLang][key]) el.innerText = translations[currentLang][key];
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (translations[currentLang][key]) el.placeholder = translations[currentLang][key];
    });
}

// Global Window Hooks
window.showTab = showTab;
window.setLanguage = setLanguage;
window.closeEditor = closeEditor;
window.saveNode = saveNode;
window.createNewNode = createNewNode;
window.onStartConnect = onStartConnect;
window.onDropPort = onDropPort;
window.addButton = addButton;
window.removeBtn = removeBtn;
window.updateBtnText = updateBtnText;
window.updateBtnLink = updateBtnLink;
window.openDM = openDM;
window.closeDM = closeDM;
window.sendDM = sendDM;
window.toggleCustomSelect = toggleCustomSelect;
window.selectOption = selectOption;
window.submitPlan = submitPlan;
window.deletePlan = deletePlan;
window.viewUserLogs = viewUserLogs;
window.applyLogDateFilter = applyLogDateFilter;
window.clearLogDateFilter = clearLogDateFilter;
window.filterLogUsers = (q) => {
    const query = q.toLowerCase();
    const filtered = allLogUsers.filter(u => 
        (u.username && u.username.toLowerCase().includes(query)) || 
        u.telegram_id.toString().includes(query)
    );
    renderLogUsers(filtered);
};

window.resetData = async () => {
    if (!confirm("ВНИМАНИЕ! Это полностью удалит всех клиентов и всю статистику. Это действие необратимо. Продолжить?")) return;
    
    try {
        const r = await fetch('/api/danger/reset', { method: 'POST' });
        if (r.ok) {
            alert("Данные успешно очищены");
            location.reload();
        } else {
            alert("Ошибка при очистке");
        }
    } catch (e) {
        console.error(e);
        alert("Системная ошибка");
    }
};

// Init
setLanguage(currentLang);
showTab('overview');
setInterval(updateDashboard, 5000);

// Flatpickr Initialization (Date only)
flatpickr("#plan-date-picker", {
    dateFormat: "d.m.Y",
    minDate: "today",
    disableMobile: "true"
});

flatpickr("#plan-end", {
    dateFormat: "d.m.Y",
    minDate: "today",
    disableMobile: "true"
});

// Time Masking Logic (Manual entry)
function setupTimeMask(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', (e) => {
        let v = e.target.value.replace(/[^0-9]/g, '');
        if (v.length > 4) v = v.substring(0, 4);
        if (v.length > 2) v = v.substring(0, 2) + ':' + v.substring(2);
        e.target.value = v;
    });
}

setupTimeMask('plan-time-picker');
setupTimeMask('plan-time-freq');
