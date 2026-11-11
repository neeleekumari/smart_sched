// script.js (replace your current script.js with this exact content)
// -------------------------------------------
// Globals & initial state
// -------------------------------------------
let currentUser = null;
let currentSection = 'dashboard';
let teachersCache = [];
let subjectsCache = [];
let timetablesCache = [];
let sectionsCache = [];
let workloadConfig = null;
let selectedLayout = 'modern';
const API_BASE = 'http://localhost:5000';

// -------------------------------------------
// Utilities: auth headers and fetch wrapper
// -------------------------------------------
function authHeaders(json = false) {
    const h = {};
    const token = localStorage.getItem('authToken');
    if (token) h['Authorization'] = `Bearer ${token}`;
    if (json) h['Content-Type'] = 'application/json';
    return h;
}

function apiFetch(url, options = {}) {
    const base = options.headers || {};
    // merge auth headers last so caller can override if needed
    const headers = Object.assign({}, base, authHeaders(base['Content-Type'] === 'application/json'));
    return fetch(url, { ...options, headers });
}

// -------------------------------------------
// Flexible showToast (works with old & new call sites)
// showToast(type, message) OR showToast(message, duration)
// -------------------------------------------
function showToast() {
    const toast = document.getElementById('toast');
    if (!toast) return;
    // normalize args
    if (arguments.length === 1) {
        // showToast(message)
        toast.className = 'toast';
        toast.textContent = arguments[0];
    } else if (arguments.length === 2) {
        if (['success', 'error', 'warning', 'info'].includes(arguments[0])) {
            // showToast(type, message)
            const type = arguments[0];
            const message = arguments[1];
            toast.className = `toast ${type}`;
            toast.textContent = message;
        } else {
            // showToast(message, duration)
            toast.className = 'toast';
            toast.textContent = arguments[0];
        }
    } else {
        toast.className = 'toast';
        toast.textContent = 'Notification';
    }
    // show and auto-hide
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// -------------------------------------------
// Auth helpers
// -------------------------------------------
// Auto-login removed
async function loadAuthFromStorage() {
    try {
        const token = localStorage.getItem('authToken');
        const userJson = localStorage.getItem('authUser');
        if (!token) {
            updateAuthUI(false, null);
            return;
        }

        // Hide UI until verified
        updateAuthUI(false, null);

        try {
            const res = await fetch(`${API_BASE}/api/auth/verify`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                // Token invalid or expired
                localStorage.removeItem('authToken');
                localStorage.removeItem('authUser');
                updateAuthUI(false, null);
                return;
            }
            const data = await res.json().catch(() => ({}));
            const user = (data && data.user) ? data.user : (userJson ? JSON.parse(userJson) : null);
            if (user) {
                currentUser = user;
                localStorage.setItem('authUser', JSON.stringify(user));

                // Redirect teachers to their dashboard if they're on the admin page
                if (user.role === 'teacher') {
                    window.location.href = 'teacher-dashboard.html';
                    return;
                }

                updateAuthUI(true, user);
            } else {
                updateAuthUI(false, null);
            }
        } catch (err) {
            // network issues
            localStorage.removeItem('authToken');
            localStorage.removeItem('authUser');
            updateAuthUI(false, null);
        }
    } catch (e) {
        updateAuthUI(false, null);
    }
}

function setAuthState(user, token) {
    currentUser = user;
    if (user && token) {
        localStorage.setItem('authToken', token);
        localStorage.setItem('authUser', JSON.stringify(user));

        // Redirect teachers to their dashboard
        if (user.role === 'teacher') {
            window.location.href = 'teacher-dashboard.html';
            return;
        }

        updateAuthUI(true, user);
        try { showSection('dashboard'); } catch (e) { }
    } else {
        localStorage.removeItem('authToken');
        localStorage.removeItem('authUser');
        updateAuthUI(false, null);
    }
}

function updateAuthUI(isLoggedIn, user) {
    const guestArea = document.getElementById('guestArea');
    const userArea = document.getElementById('userArea');
    const userDisplay = document.getElementById('userDisplay');
    const loginSection = document.getElementById('login');
    const navbar = document.querySelector('.navbar');
    const main = document.querySelector('.main-content');
    const waveCanvas = document.getElementById('waveCanvas'); // Fluid wave (inside)
    const loginBg = document.getElementById('loginBackground'); // Cosmic bg (login)

    if (isLoggedIn) {
        if (guestArea) guestArea.style.display = 'none';
        if (userArea) userArea.style.display = 'flex';
        if (userDisplay) userDisplay.textContent = (user && (user.username || user.email)) ? (user.username || user.email) : 'User';
        if (loginSection) loginSection.style.display = 'none';
        if (navbar) navbar.style.display = '';
        if (main) main.style.display = '';

        // Backgrounds: Show Fluid Wave, Hide Login Cosmic
        if (waveCanvas) waveCanvas.style.display = 'block';
        if (loginBg) loginBg.style.display = 'none';
    } else {
        if (guestArea) guestArea.style.display = 'flex';
        if (userArea) userArea.style.display = 'none';
        if (userDisplay) userDisplay.textContent = '';
        if (loginSection) loginSection.style.display = 'flex';
        if (navbar) navbar.style.display = 'none';
        if (main) main.style.display = 'none';

        // Backgrounds: Hide Fluid Wave, Show Login Cosmic
        if (waveCanvas) waveCanvas.style.display = 'none';
        if (loginBg) loginBg.style.display = 'block';
    }
}

// -------------------------------------------
// Startup
// -------------------------------------------
function initializeApp() {
    // clear stale auth user if no token
    const token = localStorage.getItem('authToken');
    if (!token) localStorage.removeItem('authUser');

    initializeModals();
    initializeFileUploads();
    restoreLayoutPreference();
    loadAuthFromStorage().catch(() => { });
    setupEventListeners();

    // UI initializations
    initializeGenerateUI();
    initializeSemesterFilter();
    initializeGenerationModeToggle();
    loadWorkloadConfig().catch(() => { });
    updateDashboardStats().catch(() => { });
}

document.addEventListener('DOMContentLoaded', initializeApp);

// -------------------------------------------
// Event listeners (defensive attaches)
// -------------------------------------------
function setupEventListeners() {
    // Nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const section = this.getAttribute('data-section');
            if (section) showSection(section);
        });
    });

    // tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const tab = this.getAttribute('data-tab');
            if (tab) showTab(tab);
        });
    });

    // modal close
    const modal = document.getElementById('modal');
    if (modal) {
        const close = modal.querySelector('.close');
        if (close) close.addEventListener('click', closeModal);
        modal.addEventListener('click', function (e) { if (e.target === this) closeModal(); });
    }

    // login/register buttons in navbar
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) loginBtn.addEventListener('click', showLoginModal);
    const registerBtn = document.getElementById('registerBtn');
    if (registerBtn) registerBtn.addEventListener('click', showRegisterModal);
    if (logoutBtn) logoutBtn.addEventListener('click', function () { setAuthState(null, null); showToast('success', 'Logged out'); });
    const deleteAccountBtn = document.getElementById('deleteAccountBtn');
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', async function () {
            if (confirm('Are you sure you want to permanently delete your account? This action cannot be undone.')) {
                try {
                    const token = localStorage.getItem('authToken');
                    if (!token) return;

                    const res = await fetch(`${API_BASE}/api/auth/me`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });

                    if (res.ok) {
                        setAuthState(null, null);
                        showToast('success', 'Account deleted successfully.');
                    } else if (res.status === 401) {
                        setAuthState(null, null);
                        showToast('error', 'Session expired or invalid token. Please login again.');
                    } else {
                        const data = await res.json();
                        showToast('error', data.error || 'Failed to delete account');
                    }
                } catch (err) {
                    console.error(err);
                    showToast('error', 'An error occurred while deleting account.');
                }
            }

        });
    }

    // Administrator login form
    const adminLoginForm = document.getElementById('adminLoginForm');
    if (adminLoginForm) {
        adminLoginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            const email = formData.get('email');
            const password = formData.get('password');
            fetch(`${API_BASE}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, password: password })
            })
                .then(async res => {
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data.error || 'Login failed');
                    return data;
                })
                .then(data => {
                    if (data && data.token && data.user) {
                        // Prevent teachers from logging in via Admin portal
                        if (data.user.role === 'teacher') {
                            showToast('error', 'Access Denied: Teachers must use the Teacher Login portal');
                            return;
                        }
                        setAuthState(data.user, data.token);
                        showToast('success', 'Login successful');
                    } else throw new Error('Unexpected response');
                })
                .catch(err => showToast('error', err.message || 'Login failed'));
        });
    }

    // Teacher login/setup form
    // Teacher login form
    const teacherLoginForm = document.getElementById('teacherLoginForm');
    if (teacherLoginForm) {
        teacherLoginForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            const username = formData.get('username'); // Now using username/code field
            const password = formData.get('password');

            try {
                const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, password: password })
                });

                if (loginRes.ok) {
                    const data = await loginRes.json();
                    if (data && data.token && data.user) {
                        // Redirect teachers to their dashboard after login
                        if (data.user.role === 'teacher') {
                            setAuthState(data.user, data.token); // Save state
                            window.location.href = 'teacher-dashboard.html';
                            return;
                        } else {
                            showToast('error', 'This account is not authorized as a teacher.');
                            return;
                        }
                    }
                } else {
                    const errorData = await loginRes.json();
                    throw new Error(errorData.error || 'Invalid credentials');
                }
            } catch (err) {
                showToast('error', err.message || 'Login failed');
            }
        });
    }

    // Admin register button
    const adminRegisterBtn = document.getElementById('adminRegisterBtn');
    if (adminRegisterBtn) adminRegisterBtn.addEventListener('click', function () {
        window.location.href = 'admin-registration.html';
    });

    // addSection quick button
    const addSectionBtn = document.getElementById('addSectionBtn');
    if (addSectionBtn) addSectionBtn.addEventListener('click', addSectionRow);
}

// Toggle between admin and teacher login forms
function switchToAdmin() {
    const adminForm = document.getElementById('adminLoginForm');
    const teacherForm = document.getElementById('teacherLoginForm');
    const adminBtn = document.getElementById('adminToggleBtn');
    const teacherBtn = document.getElementById('teacherToggleBtn');

    if (adminForm) adminForm.style.display = 'block';
    if (teacherForm) teacherForm.style.display = 'none';

    if (adminBtn) {
        adminBtn.classList.remove('btn--secondary');
        adminBtn.classList.add('btn--primary');
    }
    if (teacherBtn) {
        teacherBtn.classList.remove('btn--primary');
        teacherBtn.classList.add('btn--secondary');
    }
}

function switchToTeacher() {
    const adminForm = document.getElementById('adminLoginForm');
    const teacherForm = document.getElementById('teacherLoginForm');
    const adminBtn = document.getElementById('adminToggleBtn');
    const teacherBtn = document.getElementById('teacherToggleBtn');

    if (adminForm) adminForm.style.display = 'none';
    if (teacherForm) teacherForm.style.display = 'block';

    if (adminBtn) {
        adminBtn.classList.remove('btn--primary');
        adminBtn.classList.add('btn--secondary');
    }
    if (teacherBtn) {
        teacherBtn.classList.remove('btn--secondary');
        teacherBtn.classList.add('btn--primary');
    }

    // Ensure we start with login form when switching tabs, hide register form
    const teacherRegForm = document.getElementById('teacherRegisterForm');
    if (teacherRegForm) teacherRegForm.style.display = 'none';
}

// New functions for toggling between Teacher Login and Register
function switchToTeacherRegister() {
    const loginForm = document.getElementById('teacherLoginForm');
    const registerForm = document.getElementById('teacherRegisterForm');
    if (loginForm) loginForm.style.display = 'none';
    if (registerForm) registerForm.style.display = 'block';
}

function switchToTeacherLogin() {
    const loginForm = document.getElementById('teacherLoginForm');
    const registerForm = document.getElementById('teacherRegisterForm');
    if (loginForm) loginForm.style.display = 'block';
    if (registerForm) registerForm.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    // ... existing code ...
    const teacherRegisterLink = document.getElementById('teacherRegisterLink');
    if (teacherRegisterLink) {
        teacherRegisterLink.addEventListener('click', (e) => {
            e.preventDefault();
            switchToTeacherRegister();
        });
    }

    const teacherBackToLogin = document.getElementById('teacherBackToLogin');
    if (teacherBackToLogin) {
        teacherBackToLogin.addEventListener('click', (e) => {
            e.preventDefault();
            switchToTeacherLogin();
        });
    }

    const teacherRegisterForm = document.getElementById('teacherRegisterForm');
    if (teacherRegisterForm) {
        teacherRegisterForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(teacherRegisterForm);
            const email = formData.get('email');
            const password = formData.get('password');
            const confirmPassword = formData.get('confirmPassword');
            const fullName = formData.get('full_name');
            const salutation = formData.get('salutation');

            if (password !== confirmPassword) {
                showToast('error', 'Passwords do not match');
                return;
            }

            try {
                const registerRes = await fetch(`${API_BASE}/api/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: email.split('@')[0],
                        email: email,
                        password: password,
                        full_name: fullName,
                        salutation: salutation,
                        role: 'teacher'
                    })
                });

                const registerData = await registerRes.json();

                if (registerRes.ok) {
                    const teacherCode = registerData.user.username;
                    alert(`Registration Successful!\n\nYour Teacher Code is: ${teacherCode}\n\nPlease save this code for future logins.`);
                    showToast('success', `Registration successful! Teacher Code: ${teacherCode}`);

                    // Auto login
                    const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username: teacherCode, password: password })
                    });

                    if (loginRes.ok) {
                        const loginData = await loginRes.json();
                        if (loginData.user.role === 'teacher') {
                            localStorage.setItem('token', loginData.token);
                            localStorage.setItem('user', JSON.stringify(loginData.user));
                            window.location.href = 'teacher-dashboard.html';
                        } else {
                            showToast('error', 'Authorized as ' + loginData.user.role + ', not teacher');
                        }
                    }
                } else {
                    const errorMsg = registerData.error || (registerData.errors ? registerData.errors.join(', ') : 'Registration failed');
                    showToast('error', errorMsg);
                }
            } catch (err) {
                showToast('error', err.message || 'Registration failed');
            }
        });
    }
});

// -------------------------------------------
// Navigation and tabs (safe guards)
// -------------------------------------------
function showSection(sectionName) {
    if (!sectionName) return;
    // nav links active toggle (guard)
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => link.classList.remove('active'));
    const selector = document.querySelector(`[data-section="${sectionName}"]`);
    if (selector) selector.classList.add('active');

    // sections
    document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
    const target = document.getElementById(sectionName);
    if (target) target.classList.add('active');

    // Explicitly hide Design Studio when switching to other sections
    const designStudioSection = document.getElementById('designStudio');
    if (designStudioSection && sectionName !== 'designStudio') {
        designStudioSection.style.display = 'none';
        designStudioSection.classList.remove('active');
    }

    currentSection = sectionName;

    // section-specific loads
    if (sectionName === 'dashboard') updateDashboardStats();
    if (sectionName === 'data') loadDataTables();
    if (sectionName === 'timetables') loadTimetables();
    if (sectionName === 'generate') loadSectionsForGeneration(); // Load sections for checkbox selection
}

function showTab(tabName) {
    if (!tabName) return;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    if (btn) btn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const content = document.getElementById(`${tabName}-tab`);
    if (content) content.classList.add('active');
}

// -------------------------------------------
// Modal helpers
// -------------------------------------------
function initializeModals() {
    // modal exists in HTML; nothing else needed
}

function showModal(title, content) {
    const modal = document.getElementById('modal');
    const modalBody = document.getElementById('modalBody');
    if (!modal || !modalBody) return;
    modalBody.innerHTML = `<h2 style="margin-bottom:1rem">${title}</h2>${content}`;
    modal.style.display = 'flex';
}

function closeModal() {
    const modal = document.getElementById('modal');
    if (modal) modal.style.display = 'none';
}

// -------------------------------------------
// Dashboard / Stats
// -------------------------------------------
async function updateDashboardStats() {
    try {
        console.log('Fetching dashboard stats from:', `${API_BASE}/api/stats`);
        const res = await apiFetch(`${API_BASE}/api/stats`);
        console.log('Stats response status:', res.status);
        if (!res.ok) throw new Error('Stats fetch failed');
        const data = await res.json();
        console.log('Stats data:', data);
        const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
        setText('teacherCount', data.teachers ?? 0);
        setText('subjectCount', data.subjects ?? 0);
        setText('sectionCount', data.sections ?? 0);
        setText('timetableCount', data.timetables ?? 0);
        console.log('Dashboard stats updated successfully');
    } catch (e) {
        console.error('Error updating dashboard stats:', e);
        // If backend unreachable, show zeroes but no crash
        ['teacherCount', 'subjectCount', 'sectionCount', 'timetableCount'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '0';
        });
    }
}

// -------------------------------------------
// Data tables: teachers, subjects, sections
// -------------------------------------------
async function loadDataTables() {
    // Clear caches before reloading to ensure fresh data
    console.log('Loading data tables - clearing caches');
    teachersCache = [];
    subjectsCache = [];
    sectionsCache = [];

    await Promise.all([
        loadTeachersTable(),
        loadSubjectsTable(),
        loadSectionsTable()
    ]);
}

async function loadTeachersTable() {
    const tbody = document.getElementById('teachersTableBody');
    if (!tbody) {
        console.error('teachersTableBody element not found');
        return;
    }
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2rem;color:#666;">Loading teachers...</td></tr>';
    try {
        console.log('Fetching teachers from:', `${API_BASE}/api/teachers`);
        const res = await apiFetch(`${API_BASE}/api/teachers`);
        console.log('Teachers response status:', res.status);
        if (!res.ok) throw new Error('Teachers fetch failed');
        teachersCache = await res.json();
        console.log('Teachers loaded:', teachersCache.length, 'teachers');
        if (!Array.isArray(teachersCache) || teachersCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:2rem;color:#666;">No teachers found.</td></tr>`;
            return;
        }
        tbody.innerHTML = ''; // Clear loading message
        teachersCache.forEach(teacher => {
            const row = document.createElement('tr');
            const displayName = teacher.title ? `${teacher.title} ${teacher.name}` : teacher.name;
            const code = teacher.teacher_code || '—';
            row.innerHTML = `
                <td style="font-family:monospace;font-weight:bold;color:#667eea">${code}</td>
                <td>${teacher.title || '—'}</td>
                <td>${teacher.name || ''}</td>
                <td>${teacher.email || '—'}</td>
                <td>${teacher.initials || generateInitials(teacher.name || '')}</td>
                <td>
                    <button class="btn btn-info" onclick="editTeacher(${teacher.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-warning" onclick="deleteTeacher(${teacher.id})"><i class="fas fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(row);
        });
        console.log('Teachers table rendered successfully');
    } catch (e) {
        console.error('Error loading teachers:', e);
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:2rem;color:#666;">Failed to load teachers: ${e.message}</td></tr>`;
        showToast('error', 'Failed to load teachers');
    }
}

async function loadSubjectsTable(semester = null) {
    const tbody = document.getElementById('subjectsTableBody');
    if (!tbody) {
        console.error('subjectsTableBody element not found');
        return;
    }
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:2rem;color:#666;">Loading subjects...</td></tr>';
    try {
        // Always refresh teachers cache when loading subjects to ensure consistency
        console.log('Refreshing teachers cache for subjects table');
        try {
            const tRes = await apiFetch(`${API_BASE}/api/teachers`);
            if (tRes.ok) {
                teachersCache = await tRes.json();
                console.log('Teachers cache refreshed:', teachersCache.length, 'teachers');
            }
        } catch (e) {
            console.error('Failed to refresh teachers cache:', e);
        }

        let url = `${API_BASE}/api/subjects`;
        if (semester) url += `?semester=${encodeURIComponent(semester)}`;
        console.log('Fetching subjects from:', url);
        const res = await apiFetch(url);
        console.log('Subjects response status:', res.status);
        if (!res.ok) throw new Error('Subjects fetch failed');
        subjectsCache = await res.json();
        console.log('Subjects loaded:', subjectsCache.length, 'subjects');
        if (!Array.isArray(subjectsCache) || subjectsCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:2rem;color:#666;">No subjects found.</td></tr>`;
            renderCoursesChips();
            return;
        }
        tbody.innerHTML = ''; // Clear loading message
        const tMap = Object.fromEntries((teachersCache || []).map(t => [t.id, t]));
        subjectsCache.forEach(subject => {
            // Get all assigned teachers
            const teacherIds = subject.teacher_ids || (subject.teacher_id ? [subject.teacher_id] : []);
            const teacherNames = teacherIds.map(tid => tMap[tid]?.name || tid).join(', ') || 'None';

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${subject.name || ''}</td>
                <td>${subject.code || ''}</td>
                <td>${subject.credits ?? ''}</td>
                <td>${subject.type || subject.subject_type || ''}</td>
                <td>${subject.semester || 'N/A'}</td>
                <td>${teacherNames}</td>
                <td>${subject.abbreviation || ''}</td>
                <td>
                    <button class="btn btn-info" onclick="editSubject(${subject.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-warning" onclick="deleteSubject(${subject.id})"><i class="fas fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(row);
        });
        console.log('Subjects table rendered successfully');
        renderCoursesChips();
    } catch (e) {
        console.error('Error loading subjects:', e);
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:2rem;color:#666;">Failed to load subjects: ${e.message}</td></tr>`;
        showToast('error', 'Failed to load subjects');
    }
}

async function loadSectionsTable() {
    const tbody = document.getElementById('sectionsTableBody');
    if (!tbody) {
        console.error('sectionsTableBody element not found');
        return;
    }
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:2rem;color:#666;">Loading sections...</td></tr>';
    try {
        // Get current semester filter
        const semesterFilter = document.getElementById('semesterFilter');
        const semester = semesterFilter ? semesterFilter.value : '';

        let url = `${API_BASE}/api/sections`;
        if (semester) {
            url += `?semester=${encodeURIComponent(semester)}`;
        }

        console.log('Fetching sections from:', url);
        const res = await apiFetch(url);
        console.log('Sections response status:', res.status);
        if (!res.ok) throw new Error('Sections fetch failed');
        sectionsCache = await res.json();
        console.log('Sections loaded:', sectionsCache.length, 'sections');

        // Always refresh teachers cache for consistency
        console.log('Refreshing teachers cache for sections table');
        try {
            const tRes = await apiFetch(`${API_BASE}/api/teachers`);
            if (tRes.ok) {
                teachersCache = await tRes.json();
                console.log('Teachers cache refreshed:', teachersCache.length, 'teachers');
            }
        } catch (e) {
            console.error('Failed to refresh teachers cache:', e);
        }

        const tMap = Object.fromEntries((teachersCache || []).map(t => [t.id, t]));
        if (!Array.isArray(sectionsCache) || sectionsCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2rem;color:#666;">No sections found.</td></tr>`;
            updateSectionCheckboxes();
            return;
        }
        tbody.innerHTML = ''; // Clear loading message
        sectionsCache.forEach(section => {
            const teacherName = (section.class_teacher_id || section.classTeacherId) ? (tMap[section.class_teacher_id || section.classTeacherId]?.name || 'Unknown') : 'None';
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${section.name || ''}</td>
                <td>${section.semester || 'N/A'}</td>
                <td>${section.programme || 'N/A'}</td>
                <td>${section.class_strength ?? section.classStrength ?? '-'}</td>
                <td>${section.lecture_hall || section.lectureHall || '-'}</td>
                <td>${teacherName}</td>
                <td>
                    <button class="btn btn-info" onclick="editSection(${section.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-warning" onclick="deleteSection(${section.id})"><i class="fas fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(row);
        });
        console.log('Sections table rendered successfully');
        updateSectionCheckboxes();
    } catch (e) {
        console.error('Error loading sections:', e);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2rem;color:#666;">Failed to load sections: ${e.message}</td></tr>`;
        showToast('error', 'Failed to load sections');
    }
}

// -------------------------------------------
// Add / Edit / Delete - teachers, subjects, sections
// (I kept your existing logic but ensured DOM safety & error messages)
// -------------------------------------------

function showAddModal(type) {
    let title = '';
    let content = '';
    switch (type) {
        case 'teacher':
            title = 'Add New Teacher';
            // Retrieve domains from currentUser
            const userDomains = (currentUser && currentUser.allowed_domains && currentUser.allowed_domains.length > 0)
                ? currentUser.allowed_domains
                : ((currentUser && currentUser.allowed_domain) ? [currentUser.allowed_domain] : []);

            let emailFieldHtml = '';

            if (userDomains.length > 0) {
                if (userDomains.length === 1) {
                    // Single domain case (Fixed)
                    const domain = userDomains[0];
                    emailFieldHtml = `
                    <div class="form-group">
                        <label>Teacher Email</label>
                        <input type="hidden" id="domainHidden" value="${domain}">
                        <div class="input-icon-wrapper" style="display: flex; align-items: stretch;">
                            <span class="input-icon" style="z-index: 2;"><i class="fas fa-envelope"></i></span>
                            <input type="text" name="email_prefix" class="form-input" style="flex: 1; border-radius: 12px 0 0 12px; border-right: none;" placeholder="e.g. kimchi_2020" required>
                            <div style="background: rgba(255, 255, 255, 0.1); border: 2px solid rgba(255, 255, 255, 0.06); border-left: none; border-radius: 0 12px 12px 0; padding: 0 1rem; display: flex; align-items: center; color: rgba(255, 255, 255, 0.7); font-weight: 500;">
                                ${domain}
                            </div>
                        </div>
                    </div>`;
                } else {
                    // Multiple domains case (Dropdown)
                    // Retrieve persistent selection or default to first
                    const savedDomain = localStorage.getItem('selectedTeacherDomain');
                    const defaultDomain = (savedDomain && userDomains.includes(savedDomain)) ? savedDomain : userDomains[0];

                    const options = userDomains.map(d => `<option value="${d}" ${d === defaultDomain ? 'selected' : ''}>${d}</option>`).join('');

                    emailFieldHtml = `
                    <div class="form-group">
                        <label>Teacher Email</label>
                        <div class="input-icon-wrapper" style="display: flex; align-items: stretch;">
                            <span class="input-icon" style="z-index: 2;"><i class="fas fa-envelope"></i></span>
                            <input type="text" name="email_prefix" class="form-input" style="flex: 1; border-radius: 12px 0 0 12px; border-right: none;" placeholder="username" required>
                            <select name="email_domain" id="domainSelect" class="form-input" style="width: auto; padding-left: 1rem; border-radius: 0 12px 12px 0; border-left: none; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); cursor: pointer; min-width: 150px;">
                                ${options}
                            </select>
                        </div>
                    </div>`;
                }
            } else {
                // No domain - Free Text
                emailFieldHtml = `<div class="form-group"><label>Teacher Email</label><input type="email" name="email" class="form-input" placeholder="e.g. teacher@university.edu" required></div>`;
            }

            content = `
                <form id="teacherForm">
                    <div class="form-group">
                        <label>Title</label>
                        <select name="title" class="form-input">
                            <option value="">Select</option>
                            <option value="Mr.">Mr.</option>
                            <option value="Mrs.">Mrs.</option>
                            <option value="Ms.">Ms.</option>
                            <option value="Dr.">Dr.</option>
                            <option value="Prof.">Prof.</option>
                        </select>
                    </div>
                    <div class="form-group"><label>Name</label><input type="text" name="name" class="form-input" required></div>
                    <div class="form-group"><label>Initials (3 letters)</label><input type="text" name="initials" class="form-input" maxlength="3" required></div>
                    ${emailFieldHtml}
                    <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                        <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Teacher</button>
                    </div>
                </form>
            `;
            break;
        case 'subject':
            title = 'Add New Subject';
            const currentSem = document.getElementById('semesterFilter')?.value || '';
            content = `
                <form id="subjectForm">
                    <div class="form-group">
                        <label>Semester</label>
                        <select name="semester" class="form-input" required>
                            <option value="">Select Semester</option>
                            <option value="1" ${currentSem === '1' ? 'selected' : ''}>Semester 1</option>
                            <option value="2" ${currentSem === '2' ? 'selected' : ''}>Semester 2</option>
                            <option value="3" ${currentSem === '3' ? 'selected' : ''}>Semester 3</option>
                            <option value="4" ${currentSem === '4' ? 'selected' : ''}>Semester 4</option>
                            <option value="5" ${currentSem === '5' ? 'selected' : ''}>Semester 5</option>
                            <option value="6" ${currentSem === '6' ? 'selected' : ''}>Semester 6</option>
                            <option value="7" ${currentSem === '7' ? 'selected' : ''}>Semester 7</option>
                            <option value="8" ${currentSem === '8' ? 'selected' : ''}>Semester 8</option>
                        </select>
                    </div>
                    <div class="form-group"><label>Name</label><input type="text" name="name" class="form-input" required></div>
                    <div class="form-group"><label>Code</label><input type="text" name="code" class="form-input" required></div>
                    <div class="form-group"><label>Credits</label><input type="number" name="credits" class="form-input" min="0" max="6" required></div>
                    <div class="form-group"><label>Type</label><select name="type" class="form-input"><option value="theory">Theory</option><option value="lab">Lab</option><option value="integrated">Integrated</option><option value="none">None</option></select></div>
                    <div class="form-group">
                        <label>Teachers (optional) - Hold Ctrl/Cmd to select multiple</label>
                        <select name="teachers" id="teachersSelect" class="form-input" multiple style="min-height: 120px;">
                            ${(teachersCache || []).map(t => `<option value="${t.id}">${t.name} (${t.initials || ''})</option>`).join('')}
                        </select>
                        <small style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-top: 0.25rem; display: block;">
                            <i class="fas fa-info-circle"></i> Select multiple teachers who can teach this subject
                        </small>
                    </div>
                    <div class="form-group"><label>Abbreviation</label><input type="text" name="abbreviation" class="form-input" maxlength="10"></div>
                    <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                        <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Subject</button>
                    </div>
                </form>
            `;
            break;
        default:
            title = 'Add';
            content = `<p>Unknown type</p>`;
    }

    showModal(title, content);
    setTimeout(() => {
        const form = document.getElementById(type + 'Form');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            handleFormSubmission(type, this);
        });
        if (type === 'teacher') {
            const nameInput = form.querySelector('input[name="name"]');
            const initialsInput = form.querySelector('input[name="initials"]');
            if (nameInput && initialsInput) {
                // Track manual edits
                initialsInput.addEventListener('input', () => {
                    initialsInput.setAttribute('data-modified', 'true');
                });

                // Auto-fill initials when typing name, unless manually modified
                nameInput.addEventListener('input', () => {
                    if (!initialsInput.getAttribute('data-modified')) {
                        initialsInput.value = generateInitials(nameInput.value || '');
                    }
                });
                // Initial auto-fill (only if empty)
                if (!initialsInput.value) {
                    initialsInput.value = generateInitials(nameInput.value || '');
                }
            }

            // Add listener for domain dropdown persistence
            const domainSelect = form.querySelector('#domainSelect');
            if (domainSelect) {
                domainSelect.addEventListener('change', function () {
                    localStorage.setItem('selectedTeacherDomain', this.value);
                });
            }
        }
    }, 50);
}

async function handleFormSubmission(type, form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    try {
        if (type === 'teacher') {
            const userDomains = (currentUser && currentUser.allowed_domains && currentUser.allowed_domains.length > 0)
                ? currentUser.allowed_domains
                : ((currentUser && currentUser.allowed_domain) ? [currentUser.allowed_domain] : []);

            let email = '';
            if (userDomains.length > 0) {
                // Prefix logic
                // If dropdown exists, use its value. If hidden input exists (single domain), use it.
                // Or reconstructed from logic:
                let domain = '';
                if (data.email_domain) {
                    domain = data.email_domain;
                } else if (userDomains.length === 1) {
                    domain = userDomains[0];
                }

                // Fallback for safety if somehow submission happened without dropdown value (shouldn't happen with required)
                if (!domain && userDomains.length > 0) domain = userDomains[0];

                email = `${data.email_prefix}${domain}`;
            } else {
                email = data.email || '';
            }

            const payload = {
                name: data.name,
                title: data.title || '',
                email: email
            };
            const initials = (data.initials || generateInitials(data.name || '')).toString().trim().toUpperCase().replace(/[^A-Z]/g, '');
            if (initials.length !== 3) { showToast('error', 'Teacher initials must be exactly 3 letters'); return; }
            payload.initials = initials;
            const res = await apiFetch(`${API_BASE}/api/teachers`, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
            if (!res.ok) {
                const e = await res.json().catch(() => ({})); throw new Error(e.error || 'Failed to create teacher');
            }
        } else if (type === 'subject') {
            const selectedSemester = data.semester || '';
            if (!selectedSemester) { showToast('error', 'Please select a semester'); return; }

            // Get selected teachers from multi-select
            const teachersSelect = document.getElementById('teachersSelect');
            const selectedTeachers = teachersSelect ? Array.from(teachersSelect.selectedOptions).map(opt => parseInt(opt.value)) : [];

            const payload = {
                name: data.name,
                code: data.code,
                credits: parseInt(data.credits || 0),
                subject_type: data.type || 'theory',
                teacher_id: selectedTeachers.length > 0 ? selectedTeachers[0] : null, // First teacher as primary
                teacher_ids: selectedTeachers, // All selected teachers
                abbreviation: data.abbreviation || undefined,
                semester: selectedSemester
            };
            const res = await apiFetch(`${API_BASE}/api/subjects`, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
            if (!res.ok) {
                const e = await res.json().catch(() => ({})); throw new Error(e.error || 'Failed to create subject');
            }
        }
        closeModal();

        // Clear caches before reloading to ensure fresh data
        console.log('Item created, clearing caches and reloading');
        teachersCache = [];
        subjectsCache = [];

        await loadDataTables();
        await updateDashboardStats();
        showToast('success', `${type.charAt(0).toUpperCase() + type.slice(1)} added successfully!`);
    } catch (err) {
        showToast('error', err.message || 'Failed to add');
    }
}

// Edit / Delete functions (kept your logic but ensured elements exist)
function editTeacher(id) {
    const teacher = (teachersCache || []).find(t => t.id === id);
    if (!teacher) { showToast('error', 'Teacher not found'); return; }
    showModal('Edit Teacher', `
        <form id="editTeacherForm">
            <input type="hidden" name="id" value="${teacher.id}">
            <div class="form-group">
                <label>Title</label>
                <select name="title" class="form-input">
                    <option value="">Select</option>
                    <option value="Mr." ${teacher.title === 'Mr.' ? 'selected' : ''}>Mr.</option>
                    <option value="Mrs." ${teacher.title === 'Mrs.' ? 'selected' : ''}>Mrs.</option>
                    <option value="Ms." ${teacher.title === 'Ms.' ? 'selected' : ''}>Ms.</option>
                    <option value="Dr." ${teacher.title === 'Dr.' ? 'selected' : ''}>Dr.</option>
                    <option value="Prof." ${teacher.title === 'Prof.' ? 'selected' : ''}>Prof.</option>
                </select>
            </div>
            <div class="form-group"><label>Name</label><input type="text" name="name" class="form-input" value="${teacher.name}" required></div>
            <div class="form-group"><label>Initials</label><input type="text" name="initials" class="form-input" value="${teacher.initials || generateInitials(teacher.name)}" maxlength="6"></div>
            <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Teacher</button>
            </div>
        </form>
    `);
    setTimeout(() => {
        const form = document.getElementById('editTeacherForm');
        if (!form) return;
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(this).entries());
            try {
                let payload = {
                    name: data.name,
                    title: data.title || '',
                    email: data.email
                };
                if (data.initials) {
                    const init = data.initials.toString().trim().toUpperCase().replace(/[^A-Z]/g, '');
                    if (init.length !== 3) { showToast('error', 'Initials must be 3 letters'); return; }
                    payload.initials = init;
                } else payload.initials = generateInitials(data.name || '');
                const res = await apiFetch(`${API_BASE}/api/teachers/${id}`, { method: 'PUT', headers: authHeaders(true), body: JSON.stringify(payload) });
                if (!res.ok) throw new Error('Failed to update teacher');

                console.log('Teacher updated successfully');
                closeModal();

                // Clear cache and reload
                teachersCache = [];
                await loadDataTables();
                showToast('success', 'Teacher updated');
            } catch (err) { showToast('error', err.message || 'Failed'); }
        });
    }, 50);
}

function editSubject(id) {
    const subject = (subjectsCache || []).find(s => s.id === id);
    if (!subject) { showToast('error', 'Subject not found'); return; }

    // Get assigned teacher IDs
    const assignedTeachers = subject.teacher_ids || (subject.teacher_id ? [subject.teacher_id] : []);

    showModal('Edit Subject', `
        <form id="editSubjectForm">
            <input type="hidden" name="id" value="${subject.id}">
            <div class="form-group"><label>Semester</label><input type="text" class="form-input" value="${subject.semester ? 'Semester ' + subject.semester : 'No semester'}" readonly></div>
            <div class="form-group"><label>Name</label><input type="text" name="name" class="form-input" value="${subject.name}" required></div>
            <div class="form-group"><label>Code</label><input type="text" name="code" class="form-input" value="${subject.code}" required></div>
            <div class="form-group"><label>Credits</label><input type="number" name="credits" class="form-input" value="${subject.credits !== undefined ? subject.credits : 1}" min="0" max="6" required></div>
            <div class="form-group">
                <label>Type</label>
                <select name="type" class="form-input">
                    <option value="theory" ${(subject.subject_type || subject.type) === 'theory' ? 'selected' : ''}>Theory</option>
                    <option value="lab" ${(subject.subject_type || subject.type) === 'lab' ? 'selected' : ''}>Lab</option>
                    <option value="integrated" ${(subject.subject_type || subject.type) === 'integrated' ? 'selected' : ''}>Integrated</option>
                    <option value="none" ${(subject.subject_type || subject.type) === 'none' ? 'selected' : ''}>None</option>
                </select>
            </div>
            <div class="form-group">
                <label>Teachers (Hold Ctrl/Cmd to select multiple)</label>
                <select name="teachers" id="editTeachersSelect" class="form-input" multiple style="min-height: 120px;">
                    ${(teachersCache || []).map(t => `<option value="${t.id}" ${assignedTeachers.includes(t.id) ? 'selected' : ''}>${t.name} (${t.initials || ''})</option>`).join('')}
                </select>
                <small style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-top: 0.25rem; display: block;">
                    <i class="fas fa-info-circle"></i> Select multiple teachers who can teach this subject
                </small>
            </div>
            <div class="form-group"><label>Abbreviation</label><input type="text" name="abbreviation" class="form-input" value="${subject.abbreviation || ''}" maxlength="10"></div>
            <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Subject</button>
            </div>
        </form>
    `);
    setTimeout(() => {
        const form = document.getElementById('editSubjectForm');
        if (!form) return;
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());

            try {
                // Get selected teachers from multi-select
                const teachersSelect = document.getElementById('editTeachersSelect');
                const selectedTeachers = teachersSelect ? Array.from(teachersSelect.selectedOptions).map(opt => parseInt(opt.value)) : [];

                const payload = {
                    name: data.name,
                    code: data.code,
                    credits: parseInt(data.credits !== undefined && data.credits !== '' ? data.credits : 0),
                    subject_type: data.type,
                    teacher_ids: selectedTeachers,  // Send array of teacher IDs
                    abbreviation: data.abbreviation || undefined,
                    semester: subject.semester
                };

                const res = await apiFetch(`${API_BASE}/api/subjects/${id}`, { method: 'PUT', headers: authHeaders(true), body: JSON.stringify(payload) });
                if (!res.ok) throw new Error('Failed to update subject');

                console.log('Subject updated successfully');
                closeModal();

                // Clear caches and reload
                subjectsCache = [];
                teachersCache = [];
                await loadDataTables();
                showToast('success', 'Subject updated');
            } catch (err) { showToast('error', err.message || 'Failed'); }
        });
    }, 50);
}

async function deleteTeacher(id) {
    if (!confirm('Delete this teacher?')) return;
    try {
        console.log('Deleting teacher:', id);
        const res = await apiFetch(`${API_BASE}/api/teachers/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete teacher');

        // Invalidate cache immediately
        teachersCache = teachersCache.filter(t => t.id !== id);
        console.log('Teacher deleted, cache updated');

        await loadDataTables();
        await updateDashboardStats();
        showToast('success', 'Teacher deleted');
    } catch (e) {
        console.error('Error deleting teacher:', e);
        showToast('error', e.message || 'Failed to delete');
    }
}

async function deleteSubject(id) {
    if (!confirm('Delete this subject?')) return;
    try {
        console.log('Deleting subject:', id);
        const res = await apiFetch(`${API_BASE}/api/subjects/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete subject');

        // Invalidate cache immediately
        subjectsCache = subjectsCache.filter(s => s.id !== id);
        console.log('Subject deleted, cache updated');

        await loadDataTables();
        await updateDashboardStats();
        showToast('success', 'Subject deleted');
    } catch (e) {
        console.error('Error deleting subject:', e);
        showToast('error', e.message || 'Failed to delete');
    }
}

// -------------------------------------------
// File upload helpers
// -------------------------------------------
function initializeFileUploads() {
    const teacherFile = document.getElementById('teacherFile');
    if (teacherFile) teacherFile.addEventListener('change', (e) => handleFileUpload('teacher', e.target.files[0]));
    const subjectFile = document.getElementById('subjectFile');
    if (subjectFile) subjectFile.addEventListener('change', (e) => handleFileUpload('subject', e.target.files[0]));
}
function handleFileUpload(type, file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            let data;
            if (file.name.endsWith('.json')) data = JSON.parse(e.target.result);
            else if (file.name.endsWith('.csv')) data = parseCSV(e.target.result);
            else { showToast('error', 'Unsupported file format'); return; }
            if (!Array.isArray(data)) { showToast('error', 'File must contain an array of objects'); return; }
            if (type === 'teacher') {
                teachersCache = teachersCache || [];
                const maxId = Math.max(0, ...teachersCache.map(t => t.id || 0));
                data.forEach((item, idx) => {
                    const id = maxId + idx + 1;
                    const name = item.name || item.fullname || item.name;
                    teachersCache.push({ id, name, initials: generateInitials(name || '') });
                });
                loadTeachersTable(); updateDashboardStats(); showToast('success', `${data.length} teachers imported`);
            } else if (type === 'subject') {
                subjectsCache = subjectsCache || [];
                const maxId = Math.max(0, ...subjectsCache.map(s => s.id || 0));
                data.forEach((item, idx) => {
                    const id = maxId + idx + 1;
                    subjectsCache.push({ id, name: item.name || '', code: item.code || '', credits: item.credits || 0, semester: item.semester || '' });
                });
                loadSubjectsTable(); updateDashboardStats(); showToast('success', `${data.length} subjects imported`);
            }
        } catch (err) {
            showToast('error', 'Error parsing file: ' + (err.message || ''));
        }
    };
    reader.readAsText(file);
}
function parseCSV(text) {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length === 0) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    const out = [];
    for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim());
        const obj = {};
        headers.forEach((h, idx) => obj[h] = values[idx] || '');
        out.push(obj);
    }
    return out;
}

// -------------------------------------------
// Sections quick add for Generate page
// -------------------------------------------
async function addSectionRow() {
    const container = document.getElementById('sectionsInputList');
    if (!container) return;

    // Load teachers if not already loaded
    if (!teachersCache || teachersCache.length === 0) {
        try {
            const res = await apiFetch(`${API_BASE}/api/teachers`);
            if (res.ok) {
                teachersCache = await res.json();
            }
        } catch (err) {
            console.error('Failed to load teachers:', err);
        }
    }

    const row = document.createElement('div');
    row.className = 'section-row';
    row.style.display = 'grid';
    row.style.gridTemplateColumns = '1fr 120px 1fr 140px 90px';
    row.style.gap = '8px';
    row.style.alignItems = 'center';

    const name = document.createElement('input');
    name.className = 'form-input';
    name.name = 'sectionName';
    name.placeholder = 'Section name (A)';

    const strength = document.createElement('input');
    strength.className = 'form-input';
    strength.type = 'number';
    strength.name = 'classStrength';
    strength.placeholder = 'Strength';
    strength.value = '68';

    const teacher = document.createElement('select');
    teacher.className = 'form-input';
    teacher.name = 'classTeacher';
    teacher.innerHTML = '<option value="">Select Teacher</option>' +
        (teachersCache || []).map(t => `<option value="${t.id}">${t.name} (${t.initials || ''})</option>`).join('');

    const hall = document.createElement('input');
    hall.className = 'form-input';
    hall.name = 'lectureHall';
    hall.placeholder = 'Lecture hall';

    const remove = document.createElement('button');
    remove.className = 'btn btn-warning';
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.addEventListener('click', () => row.remove());

    row.appendChild(name);
    row.appendChild(strength);
    row.appendChild(teacher);
    row.appendChild(hall);
    row.appendChild(remove);
    container.appendChild(row);
}

// -------------------------------------------
// Sections modal add / edit / delete (server-side persisted)
// -------------------------------------------
async function showAddSectionModal() {
    // Load teachers and subjects first if not already loaded
    if (!teachersCache || teachersCache.length === 0) {
        try {
            const res = await apiFetch(`${API_BASE}/api/teachers`);
            if (res.ok) {
                teachersCache = await res.json();
            }
        } catch (err) {
            console.error('Failed to load teachers:', err);
        }
    }

    if (!subjectsCache || subjectsCache.length === 0) {
        try {
            const res = await apiFetch(`${API_BASE}/api/subjects`);
            if (res.ok) {
                subjectsCache = await res.json();
            }
        } catch (err) {
            console.error('Failed to load subjects:', err);
        }
    }

    showModal('Add New Section', `
        <form id="sectionForm">
            <div class="form-group"><label>Section Name</label><input type="text" name="name" class="form-input" required></div>
            <div class="form-group"><label>Semester</label><select id="sectionSemesterSelect" name="semester" class="form-input"><option value="">Select Semester</option>${[1, 2, 3, 4, 5, 6, 7, 8].map(n => `<option value="${n}">Semester ${n}</option>`).join('')}</select></div>
            <div class="form-group"><label>Programme</label><input type="text" name="programme" class="form-input"></div>
            <div class="form-group"><label>Class Strength</label><input type="number" name="class_strength" class="form-input" value="30"></div>
            <div class="form-group"><label>Lecture Hall</label><input type="text" name="lecture_hall" class="form-input"></div>
            <div class="form-group"><label>Class Teacher</label><select id="classTeacherSelect" name="class_teacher_id" class="form-input"><option value="">Select Semester First</option></select></div>
            <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Section</button>
            </div>
        </form>
    `);
    setTimeout(() => {
        const form = document.getElementById('sectionForm');
        const semesterSelect = document.getElementById('sectionSemesterSelect');
        const teacherSelect = document.getElementById('classTeacherSelect');

        if (!form) return;

        // Filter teachers when semester changes
        if (semesterSelect && teacherSelect) {
            semesterSelect.addEventListener('change', function () {
                const selectedSemester = this.value;

                if (!selectedSemester) {
                    teacherSelect.innerHTML = '<option value="">Select Semester First</option>';
                    return;
                }

                // Get teachers who teach subjects in this semester
                const semesterSubjects = (subjectsCache || []).filter(s => s.semester == selectedSemester);
                const teacherIds = new Set(semesterSubjects.map(s => s.teacher_id).filter(id => id));
                const filteredTeachers = (teachersCache || []).filter(t => teacherIds.has(t.id));

                if (filteredTeachers.length === 0) {
                    teacherSelect.innerHTML = '<option value="">No teachers found for this semester</option>';
                } else {
                    teacherSelect.innerHTML = `<option value="">Select Teacher</option>${filteredTeachers.map(t => `<option value="${t.id}">${t.name} (${t.initials || ''})</option>`).join('')}`;
                }
            });
        }

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(this).entries());
            try {
                const payload = {
                    name: d.name,
                    semester: d.semester || null,
                    programme: d.programme || null,
                    class_strength: d.class_strength ? parseInt(d.class_strength) : 30,
                    lecture_hall: d.lecture_hall || null,
                    class_teacher_id: d.class_teacher_id ? parseInt(d.class_teacher_id) : null
                };
                const res = await apiFetch(`${API_BASE}/api/sections`, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
                if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || 'Failed'); }

                console.log('Section created successfully');
                closeModal();

                // Clear cache and reload
                sectionsCache = [];
                await loadDataTables();
                await updateDashboardStats();
                showToast('success', 'Section added');
            } catch (err) { showToast('error', err.message || 'Failed'); }
        });
    }, 50);
}

// Load sections as checkboxes for generation page
async function loadSectionsForGeneration() {
    const container = document.getElementById('sectionsCheckboxList');
    const noSectionsMsg = document.getElementById('noSectionsMessage');
    const hint = document.getElementById('sectionSelectionHint');

    if (!container) return;

    try {
        // Get current semester from generation form
        const semesterSelect = document.getElementById('semesterSelect');
        const semester = semesterSelect ? semesterSelect.value : '';

        // Load sections with semester filter
        let url = `${API_BASE}/api/sections`;
        if (semester) {
            url += `?semester=${encodeURIComponent(semester)}`;
        }

        const res = await apiFetch(url);
        if (!res.ok) throw new Error('Failed to load sections');
        sectionsCache = await res.json();

        if (!sectionsCache || sectionsCache.length === 0) {
            container.style.display = 'none';
            if (noSectionsMsg) noSectionsMsg.style.display = 'block';
            return;
        }

        container.style.display = 'grid';
        if (noSectionsMsg) noSectionsMsg.style.display = 'none';

        // Get generation mode
        const generationMode = document.querySelector('input[name="generationMode"]:checked')?.value || 'single';

        // Update hint based on mode
        if (hint) {
            hint.textContent = generationMode === 'single'
                ? 'Select ONE section for single timetable generation'
                : 'Select multiple sections for multi-timetable generation';
        }

        // Render checkboxes
        container.innerHTML = sectionsCache.map(section => `
            <label class="checkbox-card">
                <input type="checkbox" name="selectedSections" value="${section.id}" data-section-name="${section.name}">
                <div class="checkbox-content">
                    <i class="fas fa-users"></i>
                    <div>
                        <strong>${section.name}</strong>
                        <p>${section.semester ? `Semester ${section.semester}` : 'No semester'} • ${section.programme || 'No programme'}</p>
                        <p style="font-size: 0.75rem; margin-top: 0.25rem; opacity: 0.7;">
                            ${section.class_strength ? `${section.class_strength} students` : ''} 
                            ${section.lecture_hall ? `• ${section.lecture_hall}` : ''}
                        </p>
                    </div>
                </div>
            </label>
        `).join('');

        // Add event listeners for single-mode restriction
        if (generationMode === 'single') {
            const checkboxes = container.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function () {
                    if (this.checked) {
                        // Uncheck all others
                        checkboxes.forEach(cb => {
                            if (cb !== this) cb.checked = false;
                        });
                    }
                });
            });
        }

    } catch (e) {
        console.error('Failed to load sections:', e);
        if (container) {
            container.innerHTML = '<p style="color: rgba(255,255,255,0.5); text-align: center; padding: 2rem;">Failed to load sections</p>';
        }
    }
}

async function editSection(id) {
    const section = (sectionsCache || []).find(s => s.id === id);
    if (!section) { showToast('error', 'Section not found'); return; }

    // Load teachers and subjects first if not already loaded
    if (!teachersCache || teachersCache.length === 0) {
        try {
            const res = await apiFetch(`${API_BASE}/api/teachers`);
            if (res.ok) {
                teachersCache = await res.json();
            }
        } catch (err) {
            console.error('Failed to load teachers:', err);
        }
    }

    if (!subjectsCache || subjectsCache.length === 0) {
        try {
            const res = await apiFetch(`${API_BASE}/api/subjects`);
            if (res.ok) {
                subjectsCache = await res.json();
            }
        } catch (err) {
            console.error('Failed to load subjects:', err);
        }
    }

    // Filter teachers based on section's semester
    let teacherOptions = '';
    if (section.semester) {
        const semesterSubjects = (subjectsCache || []).filter(s => s.semester == section.semester);
        const teacherIds = new Set(semesterSubjects.map(s => s.teacher_id).filter(id => id));
        const filteredTeachers = (teachersCache || []).filter(t => teacherIds.has(t.id));
        teacherOptions = filteredTeachers.map(t => `<option value="${t.id}" ${t.id === (section.class_teacher_id || section.classTeacherId) ? 'selected' : ''}>${t.name} (${t.initials || ''})</option>`).join('');
    } else {
        teacherOptions = (teachersCache || []).map(t => `<option value="${t.id}" ${t.id === (section.class_teacher_id || section.classTeacherId) ? 'selected' : ''}>${t.name} (${t.initials || ''})</option>`).join('');
    }

    showModal('Edit Section', `
        <form id="editSectionForm">
            <input type="hidden" name="id" value="${section.id}">
            <div class="form-group"><label>Section Name</label><input type="text" name="name" class="form-input" value="${section.name}" required></div>
            <div class="form-group"><label>Semester</label><select id="editSectionSemesterSelect" name="semester" class="form-input"><option value="">No semester</option>${[1, 2, 3, 4, 5, 6, 7, 8].map(s => `<option value="${s}" ${section.semester == s ? 'selected' : ''}>Semester ${s}</option>`).join('')}</select></div>
            <div class="form-group"><label>Programme</label><input type="text" name="programme" class="form-input" value="${section.programme || ''}"></div>
            <div class="form-group"><label>Class Strength</label><input type="number" name="class_strength" class="form-input" value="${section.class_strength || 30}" min="1"></div>
            <div class="form-group"><label>Lecture Hall</label><input type="text" name="lecture_hall" class="form-input" value="${section.lecture_hall || ''}"></div>
            <div class="form-group"><label>Class Teacher</label><select id="editClassTeacherSelect" name="class_teacher_id" class="form-input"><option value="">Select Teacher</option>${teacherOptions}</select></div>
            <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1rem;">
                <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Section</button>
            </div>
        </form>
    `);
    setTimeout(() => {
        const form = document.getElementById('editSectionForm');
        const semesterSelect = document.getElementById('editSectionSemesterSelect');
        const teacherSelect = document.getElementById('editClassTeacherSelect');

        if (!form) return;

        // Filter teachers when semester changes
        if (semesterSelect && teacherSelect) {
            semesterSelect.addEventListener('change', function () {
                const selectedSemester = this.value;

                if (!selectedSemester) {
                    teacherSelect.innerHTML = '<option value="">Select Semester First</option>';
                    return;
                }

                // Get teachers who teach subjects in this semester
                const semesterSubjects = (subjectsCache || []).filter(s => s.semester == selectedSemester);
                const teacherIds = new Set(semesterSubjects.map(s => s.teacher_id).filter(id => id));
                const filteredTeachers = (teachersCache || []).filter(t => teacherIds.has(t.id));

                if (filteredTeachers.length === 0) {
                    teacherSelect.innerHTML = '<option value="">No teachers found for this semester</option>';
                } else {
                    teacherSelect.innerHTML = `<option value="">Select Teacher</option>${filteredTeachers.map(t => `<option value="${t.id}">${t.name} (${t.initials || ''})</option>`).join('')}`;
                }
            });
        }

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(this).entries());
            try {
                const payload = {
                    name: d.name,
                    semester: d.semester || null,
                    programme: d.programme || null,
                    class_strength: d.class_strength ? parseInt(d.class_strength) : 30,
                    lecture_hall: d.lecture_hall || null,
                    class_teacher_id: d.class_teacher_id ? parseInt(d.class_teacher_id) : null
                };
                const res = await apiFetch(`${API_BASE}/api/sections/${id}`, { method: 'PUT', headers: authHeaders(true), body: JSON.stringify(payload) });
                if (!res.ok) throw new Error('Failed to update section');

                console.log('Section updated successfully');
                closeModal();

                // Clear cache and reload
                sectionsCache = [];
                await loadDataTables();
                await updateDashboardStats();
                showToast('success', 'Section updated');
            } catch (err) { showToast('error', err.message || 'Failed'); }
        });
    }, 50);
}

async function deleteSection(id) {
    if (!confirm('Delete this section?')) return;
    try {
        console.log('Deleting section:', id);
        const res = await apiFetch(`${API_BASE}/api/sections/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete');

        // Invalidate cache immediately
        sectionsCache = sectionsCache.filter(s => s.id !== id);
        console.log('Section deleted, cache updated');

        await loadDataTables();
        await updateDashboardStats();
        showToast('success', 'Section deleted');
    } catch (e) {
        console.error('Error deleting section:', e);
        showToast('error', e.message || 'Failed');
    }
}

// -------------------------------------------
// Timetables: load / view / export / delete / regenerate
// -------------------------------------------
async function loadTimetables() {
    const grid = document.getElementById('timetablesGrid');
    if (!grid) return;

    // Only load if authenticated
    if (!localStorage.getItem('authToken')) {
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#666;"><h3>Please log in to view timetables</h3></div>`;
        return;
    }

    grid.innerHTML = '';
    try {
        const res = await apiFetch(`${API_BASE}/api/timetables`);
        if (!res.ok) {
            if (res.status === 401) {
                grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#666;"><h3>Session expired. Please log in again.</h3></div>`;
                return;
            }
            throw new Error('Timetables fetch failed');
        }
        timetablesCache = await res.json();
    } catch (e) {
        console.error('Error loading timetables:', e);
        timetablesCache = [];
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#666;"><h3>Error loading timetables</h3><p>${e.message}</p></div>`;
        return;
    }

    if (!Array.isArray(timetablesCache) || timetablesCache.length === 0) {
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#666;"><h3>No timetables generated yet</h3><button class="btn btn-primary" onclick="showSection('generate')">Generate Timetable</button></div>`;
        return;
    }
    timetablesCache.forEach(tt => {
        const card = document.createElement('div');
        card.className = 'timetable-card';
        card.innerHTML = `
            <div class="timetable-card-header">
                <h3>${tt.name}</h3>
                <div class="timetable-status ${tt.conflicts > 0 ? 'status-warning' : 'status-success'}">
                    ${tt.conflicts > 0 ? '<i class="fas fa-exclamation-triangle"></i>' : '<i class="fas fa-check-circle"></i>'}
                    ${tt.conflicts > 0 ? tt.conflicts + ' conflicts' : 'No conflicts'}
                </div>
            </div>
            <div class="timetable-meta">
                <div class="meta-item">
                    <i class="fas fa-calendar"></i>
                    <span>${new Date(tt.createdAt || tt.created_at).toLocaleDateString()}</span>
                </div>
                <div class="meta-item">
                    <i class="fas fa-clock"></i>
                    <span>${new Date(tt.createdAt || tt.created_at).toLocaleTimeString()}</span>
                </div>
            </div>
            <div class="timetable-actions">
                <button class="btn-action btn-view" onclick="viewTimetable(${tt.id})" title="View Timetable">
                    <i class="fas fa-eye"></i>
                    <span>View</span>
                </button>
                <div class="btn-group">
                    <button class="btn-action btn-export" onclick="exportTimetable('pdf', ${tt.id})" title="Export as PDF">
                        <i class="fas fa-file-pdf"></i>
                    </button>
                    <button class="btn-action btn-export" onclick="exportTimetable('excel', ${tt.id})" title="Export as Excel">
                        <i class="fas fa-file-excel"></i>
                    </button>
                    <button class="btn-action btn-export" onclick="exportTimetable('png', ${tt.id})" title="Export as PNG">
                        <i class="fas fa-image"></i>
                    </button>
                </div>
                <button class="btn-action btn-regen" onclick="regenerateTimetable(${tt.id})" title="Regenerate">
                    <i class="fas fa-sync"></i>
                </button>
                <button class="btn-action btn-delete" onclick="deleteTimetable(${tt.id})" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

async function regenerateTimetable(id) {
    if (!confirm('Regenerate will delete current timetable and create a new one. Proceed?')) return;
    try {
        const del = await apiFetch(`${API_BASE}/api/timetables/${id}`, { method: 'DELETE' });
        if (!del.ok) throw new Error('Failed to delete');
        loadTimetables(); updateDashboardStats();
        showToast('success', 'Timetable deleted. Generate a new one.');
        showSection('generate');
    } catch (e) { showToast('error', e.message || 'Failed'); }
}

async function deleteTimetable(id) {
    if (!confirm('Delete this timetable?')) return;
    try {
        const res = await apiFetch(`${API_BASE}/api/timetables/${id} `, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete');
        loadTimetables(); updateDashboardStats(); showToast('success', 'Deleted');
    } catch (e) { showToast('error', e.message || 'Failed'); }
}

async function exportTimetable(format, timetableId = null) {
    const id = timetableId || ((timetablesCache || [])[0]?.id);
    if (!id) { showToast('error', 'No timetable to export'); return; }

    try {
        showToast('info', `Preparing ${format.toUpperCase()} export...`);

        // Check if Design Studio is active and has the timetable loaded
        const designStudioSection = document.getElementById('designStudio');
        const isInDesignStudio = designStudioSection && designStudioSection.classList.contains('active');

        if (isInDesignStudio && window.timetableDesignStudio && window.timetableDesignStudio.timetableId === id) {
            // Export from Design Studio with pixel-perfect rendering
            await exportFromDesignStudio(format, id);
        } else {
            // First, load the timetable in Design Studio (hidden), then export
            showToast('info', 'Loading timetable for export...');

            // Temporarily view the timetable to render it
            const originalSection = document.querySelector('.section.active');
            await viewTimetable(id);

            // Wait for Design Studio to render
            await new Promise(resolve => setTimeout(resolve, 1000));

            // Now export from Design Studio
            if (window.timetableDesignStudio) {
                await exportFromDesignStudio(format, id);
            } else {
                throw new Error('Design Studio not available');
            }

            // Return to original section
            if (originalSection) {
                showSection(originalSection.id);
            }
        }

        showToast('success', `${format.toUpperCase()} exported successfully`);
    } catch (e) {
        console.error('Export error:', e);
        showToast('error', 'Export failed: ' + (e.message || ''));
    }
}

async function exportFromDesignStudio(format, timetableId) {
    try {
        // Get the Design Studio container
        const container = document.getElementById('designStudioContainer');
        if (!container) {
            throw new Error('Design Studio container not found');
        }

        // Get the full HTML content including styles
        const htmlContent = container.innerHTML;

        // Get timetable name
        const timetable = timetablesCache.find(tt => tt.id === timetableId);
        const timetableName = timetable ? timetable.name : 'timetable';

        // Collect all CSS from stylesheets
        let cssContent = '';
        try {
            cssContent = Array.from(document.styleSheets)
                .map(sheet => {
                    try {
                        return Array.from(sheet.cssRules || [])
                            .map(rule => rule.cssText)
                            .join('\n');
                    } catch (e) {
                        return '';
                    }
                })
                .join('\n');
        } catch (e) {
            console.warn('Could not extract all CSS:', e);
        }

        // Send to backend for export
        const res = await fetch(`${API_BASE}/api/export/timetable/studio`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({
                html: htmlContent,
                css: cssContent,
                format: format,
                name: timetableName
            })
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({}));
            throw new Error(error.error || 'Export failed');
        }

        // Download the file
        const blob = await res.blob();
        let filename = `${timetableName}.${format === 'excel' ? 'xlsx' : format}`;
        const cd = res.headers.get('Content-Disposition');
        if (cd) {
            const m = cd.match(/filename="?(.+?)"?$/i);
            if (m && m[1]) filename = m[1];
        }

        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();
        }, 1000);

    } catch (e) {
        console.error('Export from Design Studio error:', e);
        throw e;
    }
}



// -------------------------------------------
// Generate UI: populate subjects multi-select, logo upload etc.
// -------------------------------------------
function initializeGenerateUI() {
    const semesterSelect = document.getElementById('semesterSelect');
    const coursesMulti = document.getElementById('coursesMulti');
    const semesterFilter = document.getElementById('semesterFilter');
    const timetableNameInput = document.getElementById('timetableName');
    const programmeNameInput = document.getElementById('programmeName');
    const termLabelInput = document.getElementById('termLabel');

    // Auto-fill timetable name when other fields change
    function autoFillTimetableName() {
        if (!timetableNameInput) return;
        const programme = programmeNameInput?.value?.trim() || '';
        const semester = semesterSelect?.value || '';
        const term = termLabelInput?.value?.trim() || '';

        if (programme && semester && term) {
            const generationMode = document.querySelector('input[name="generationMode"]:checked')?.value || 'single';
            const baseName = `${programme} Sem ${semester} - ${term}`;
            const autoName = generationMode === 'multi' ? `${baseName}(Multi - Section)` : baseName;

            // Only auto-fill if user hasn't manually edited it
            if (!timetableNameInput.value || timetableNameInput.dataset.autoFilled === 'true') {
                timetableNameInput.value = autoName;
                timetableNameInput.dataset.autoFilled = 'true';
            }
        }
    }

    // Listen for changes to auto-fill name
    if (programmeNameInput) programmeNameInput.addEventListener('input', autoFillTimetableName);
    if (termLabelInput) termLabelInput.addEventListener('input', autoFillTimetableName);
    if (semesterSelect) semesterSelect.addEventListener('change', autoFillTimetableName);

    // Listen for generation mode changes
    const modeRadios = document.querySelectorAll('input[name="generationMode"]');
    modeRadios.forEach(radio => radio.addEventListener('change', autoFillTimetableName));

    // Mark as user-edited if manually changed
    if (timetableNameInput) {
        timetableNameInput.addEventListener('input', () => {
            if (timetableNameInput.value) {
                delete timetableNameInput.dataset.autoFilled;
            }
        });
    }

    async function fetchSubjectsForSemester(sem) {
        try {
            let url = `${API_BASE}/api/subjects`;
            if (sem) url += `?semester=${encodeURIComponent(sem)}`;
            const res = await apiFetch(url);
            if (res.ok) subjectsCache = await res.json();
        } catch (e) { }
        populateCoursesMulti();
        autoFillTimetableName(); // Update name when semester changes
    }
    function populateCoursesMulti() {
        if (!coursesMulti) return;
        const sem = (semesterSelect && semesterSelect.value) ? semesterSelect.value : '';
        const filtered = (subjectsCache || []).filter(s => !sem || String(s.semester) === String(sem));
        coursesMulti.innerHTML = '';
        if (filtered.length === 0) {
            const opt = document.createElement('option'); opt.value = ''; opt.disabled = true; opt.textContent = sem ? 'No subjects found for selected semester' : 'Select a semester to load subjects';
            coursesMulti.appendChild(opt); return;
        }
        filtered.forEach(s => {
            const opt = document.createElement('option'); opt.value = String(s.id); opt.textContent = `${s.name}(${s.code || ''})`; coursesMulti.appendChild(opt);
        });
    }
    if (semesterSelect) {
        semesterSelect.addEventListener('change', () => {
            fetchSubjectsForSemester(semesterSelect.value);
            loadSectionsForGeneration(); // Reload sections when semester changes
        });
    }
    if (semesterSelect && !semesterSelect.value && semesterFilter && semesterFilter.value) semesterSelect.value = semesterFilter.value;
    fetchSubjectsForSemester(semesterSelect ? semesterSelect.value : '');

    // logo handling
    const logoInput = document.getElementById('logoInput');
    const logoPreview = document.getElementById('logoPreview');
    const clearLogoBtn = document.getElementById('clearLogoBtn');
    if (logoPreview && logoInput) {
        logoPreview.addEventListener('click', () => logoInput.click());
        logoInput.addEventListener('change', () => {
            const file = logoInput.files && logoInput.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                logoPreview.innerHTML = `<img src="${reader.result}" alt="logo" style="max-width:100%;max-height:100%;border-radius:6px;" />`;
                if (clearLogoBtn) {
                    clearLogoBtn.classList.remove('hidden');
                    clearLogoBtn.style.display = 'block';
                }
                window._logoDataUrl = reader.result;
            };
            reader.readAsDataURL(file);
        });
    }
    if (clearLogoBtn) {
        clearLogoBtn.addEventListener('click', () => {
            if (logoInput) logoInput.value = '';
            if (logoPreview) logoPreview.innerHTML = '<div class="logo-preview-box"><i class="fas fa-image"></i><span>Click to upload logo</span><small>PNG, JPG up to 5MB</small></div>';
            clearLogoBtn.classList.add('hidden');
            clearLogoBtn.style.display = 'none';
            window._logoDataUrl = '';
        });
    }
}

// renderCoursesChips (kept as simple sync function)
function renderCoursesChips() {
    const coursesMulti = document.getElementById('coursesMulti');
    if (!coursesMulti) return;
    // trigger change in case other code listens to it
    coursesMulti.dispatchEvent(new Event('change'));
}

// -------------------------------------------
// Generation: enhanced generator that posts to backend
// -------------------------------------------
async function generateTimetableEnhanced() {
    const generationMode = document.querySelector('input[name="generationMode"]:checked')?.value || 'single';
    if (generationMode === 'ai') { showToast('error', 'AI Scheduler not available'); return; }

    const workloadConfigData = {
        multi_timetable_min_hours: parseInt(document.getElementById('multiMinHours')?.value || 16),
        multi_timetable_max_hours: parseInt(document.getElementById('multiMaxHours')?.value || 18),
        single_timetable_target_hours: parseInt(document.getElementById('singleTargetHours')?.value || 8),
        max_theory_subjects: parseInt(document.getElementById('maxTheorySubjects')?.value || 2),
        max_lab_subjects: parseInt(document.getElementById('maxLabSubjects')?.value || 1),
        require_rest_between_classes: document.getElementById('requireRestTime')?.checked !== false
    };

    let selectedSectionIds = [];
    let sectionsMetadata = [];

    // Get selected sections from checkboxes
    const selectedCheckboxes = document.querySelectorAll('input[name="selectedSections"]:checked');
    selectedSectionIds = Array.from(selectedCheckboxes).map(cb => cb.dataset.sectionName);

    // Get full section data from sectionsCache
    selectedCheckboxes.forEach(cb => {
        const sectionId = parseInt(cb.value);
        const section = sectionsCache.find(s => s.id === sectionId);
        if (section) {
            // Get teacher name if class_teacher_id exists
            const teacher = teachersCache.find(t => t.id === section.class_teacher_id);
            sectionsMetadata.push({
                name: section.name,
                classStrength: section.class_strength || 30,
                classTeacher: teacher ? teacher.name : '',
                class_teacher_id: section.class_teacher_id || null,
                lectureHall: section.lecture_hall || '',
                hall: section.lecture_hall || ''
            });
        }
    });

    // Validation
    if (generationMode === 'multi') {
        if (selectedSectionIds.length < 2) {
            showToast('error', 'Select at least two sections for multi-timetable generation');
            return;
        }
    } else {
        if (selectedSectionIds.length !== 1) {
            showToast('error', 'Select exactly one section for single timetable generation');
            return;
        }
    }

    const wefDate = document.getElementById('wefDate')?.value || '';
    const termLabel = document.getElementById('termLabel')?.value || '';
    const semester = document.getElementById('semesterSelect')?.value || '';
    const programmeName = document.getElementById('programmeName')?.value || '';
    const logoDataUrl = window._logoDataUrl || '';
    const coursesSelect = document.getElementById('coursesMulti');
    const selectedSubjects = coursesSelect ? Array.from(coursesSelect.selectedOptions).map(o => ({ id: parseInt(o.value), name: o.textContent })) : [];

    if (!semester) { showToast('error', 'Please select a semester'); return; }
    if (!termLabel) { showToast('error', 'Please enter term/session'); return; }
    if (!programmeName) { showToast('error', 'Please enter programme name'); return; }
    if (!wefDate) { showToast('error', 'Please select W.E.F. date'); return; }
    if (!selectedSubjects.length) { showToast('error', 'Please select at least one subject'); return; }

    // Get name from input or auto-generate
    let name = document.getElementById('timetableName')?.value?.trim() || '';
    if (!name) {
        const baseName = `${programmeName} Sem ${semester} - ${termLabel}`;
        name = generationMode === 'multi' ? `${baseName}(Multi - Section)` : baseName;
    }

    // Collect time configuration
    const startTime = document.getElementById('startTime')?.value || '09:00';
    const endTime = document.getElementById('endTime')?.value || '17:00';
    const numPeriods = parseInt(document.getElementById('numPeriods')?.value || 8);
    const numDays = 5; // Fixed to 5 days (Monday-Friday)

    // Collect break configuration
    const numBreaks = parseInt(document.getElementById('numBreaks')?.value || 0);
    const breaks = [];
    for (let i = 0; i < numBreaks; i++) {
        const breakName = document.getElementById(`breakName${i}`)?.value || `Break ${i + 1}`;
        const breakStart = document.getElementById(`breakStartTime${i}`)?.value || '';
        const breakDuration = parseInt(document.getElementById(`breakDuration${i}`)?.value || 15);

        if (breakStart) {
            breaks.push({
                name: breakName,
                start_time: breakStart,
                duration: breakDuration
            });
        }
    }

    const progressContainer = document.getElementById('generationProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    if (progressContainer) { progressContainer.style.display = 'block'; if (progressFill) progressFill.style.width = '10%'; if (progressText) progressText.textContent = 'Submitting to server...'; }

    try {
        const payload = {
            name,
            generation_mode: generationMode,
            section_ids: selectedSectionIds,
            workloadConfig: workloadConfigData,
            options: { find_multiple: false, solutions_count: 1 },
            meta: {
                wefDate,
                termLabel,
                semester,
                programmeName,
                logoDataUrl,
                subjects: selectedSubjects,
                sections: sectionsMetadata
            },
            time_config: {
                start_time: startTime,
                end_time: endTime,
                num_periods: numPeriods,
                num_days: numDays,
                breaks: breaks
            }
        };

        console.log('Sending timetable generation request:', payload);

        const res = await apiFetch(`${API_BASE}/api/timetables`, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            console.error('Generation error:', err);

            // Format error message
            let errorMsg = 'Generation failed';
            if (err.error) {
                if (Array.isArray(err.error)) {
                    errorMsg = err.error.join(', ');
                } else {
                    errorMsg = err.error;
                }
            }
            throw new Error(errorMsg);
        }
        const result = await res.json().catch(() => ({}));
        if (progressFill) progressFill.style.width = '100%';
        if (progressText) progressText.textContent = result.message || 'Generated';
        setTimeout(() => {
            if (progressContainer) progressContainer.style.display = 'none';
            updateDashboardStats();
            showSection('timetables'); // This already calls loadTimetables()
            showToast('success', result.message || 'Timetable generated');
        }, 900);
    } catch (e) {
        console.error('Generation error:', e);
        if (progressContainer) progressContainer.style.display = 'none';
        showToast('error', e.message || 'Failed to generate timetable');
    }
}

// -------------------------------------------
// Workload config load/save
// -------------------------------------------
async function loadWorkloadConfig() {
    try {
        const res = await apiFetch(`${API_BASE}/api/config/workload`);
        if (!res.ok) throw new Error('Config fetch failed');
        workloadConfig = await res.json();
        if (document.getElementById('multiMinHours')) {
            document.getElementById('multiMinHours').value = workloadConfig.multi_timetable_min_hours || 16;
            document.getElementById('multiMaxHours').value = workloadConfig.multi_timetable_max_hours || 18;
            document.getElementById('singleTargetHours').value = workloadConfig.single_timetable_target_hours || 8;
            document.getElementById('maxTheorySubjects').value = workloadConfig.max_theory_subjects || 2;
            document.getElementById('maxLabSubjects').value = workloadConfig.max_lab_subjects || 1;
            document.getElementById('requireRestTime').checked = workloadConfig.require_rest_between_classes !== false;
        }
    } catch (e) {
        workloadConfig = {
            multi_timetable_min_hours: 16, multi_timetable_max_hours: 18, single_timetable_target_hours: 8,
            max_theory_subjects: 2, max_lab_subjects: 1, require_rest_between_classes: true
        };
    }
}
async function saveWorkloadConfig() {
    try {
        const config = {
            multi_timetable_min_hours: parseInt(document.getElementById('multiMinHours').value),
            multi_timetable_max_hours: parseInt(document.getElementById('multiMaxHours').value),
            single_timetable_target_hours: parseInt(document.getElementById('singleTargetHours').value),
            max_theory_subjects: parseInt(document.getElementById('maxTheorySubjects').value),
            max_lab_subjects: parseInt(document.getElementById('maxLabSubjects').value),
            require_rest_between_classes: document.getElementById('requireRestTime').checked
        };
        const res = await apiFetch(`${API_BASE}/api/config/workload`, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(config) });
        if (!res.ok) throw new Error('Failed to save');
        workloadConfig = config; showToast('success', 'Workload config saved');
    } catch (e) { showToast('error', e.message || 'Failed to save'); }
}

// -------------------------------------------
// Semester filter helpers
// -------------------------------------------
function initializeSemesterFilter() {
    const semesterFilter = document.getElementById('semesterFilter');
    if (!semesterFilter) return;
    semesterFilter.addEventListener('change', function () {
        const selectedSemester = this.value;
        filterDataBySemester(selectedSemester);
    });
}
function filterDataBySemester(semester) {
    if (semester) {
        loadSubjectsTable(semester);
        loadSectionsTable(); // Reload sections with semester filter
        updateSemesterIndicator(semester);
    } else {
        loadSubjectsTable();
        loadSectionsTable(); // Reload all sections
        updateSemesterIndicator(null);
    }
}
function updateSemesterIndicator(semester) {
    const indicator = document.getElementById('semesterIndicator');
    if (!indicator) return;
    if (semester) { indicator.style.display = 'block'; indicator.textContent = `Currently viewing: Semester ${semester}`; }
    else indicator.style.display = 'none';
}

// -------------------------------------------
// Generation mode toggle
// -------------------------------------------
function initializeGenerationModeToggle() {
    const modeRadios = document.querySelectorAll('input[name="generationMode"]');
    const sectionSelectionCard = document.getElementById('sectionSelectionCard');

    // Load sections for generation on mode change
    modeRadios.forEach(radio => {
        radio.addEventListener('change', function () {
            loadSectionsForGeneration(); // Reload with new mode

            if (sectionSelectionCard) {
                if (this.value === 'multi') {
                    sectionSelectionCard.style.display = 'block';
                    loadSectionsForSelection();
                } else {
                    sectionSelectionCard.style.display = 'none';
                }
            }
        });
    });

    // Initial load
    loadSectionsForGeneration();
}

// -------------------------------------------
// Section checkboxes for multi generation
// -------------------------------------------
function updateSectionCheckboxes() {
    const container = document.getElementById('sectionCheckboxes');
    const warningDiv = document.getElementById('noSectionsWarning');
    if (!container) return;
    container.innerHTML = '';
    if (!sectionsCache || sectionsCache.length === 0) {
        container.style.display = 'none';
        if (warningDiv) warningDiv.style.display = 'block';
        return;
    }
    container.style.display = 'grid';
    if (warningDiv) warningDiv.style.display = 'none';
    sectionsCache.forEach(section => {
        const label = document.createElement('label');
        label.className = 'checkbox-label';
        label.innerHTML = `< input type = "checkbox" class= "section-checkbox" value = "${section.id}" > <span>${section.name} ${section.semester ? `(Semester ${section.semester})` : ''}</span>`;
        container.appendChild(label);
    });
}
async function loadSectionsForSelection() {
    try {
        // Get current semester from generation form
        const semesterSelect = document.getElementById('semesterSelect');
        const semester = semesterSelect ? semesterSelect.value : '';

        let url = `${API_BASE}/api/sections`;
        if (semester) {
            url += `?semester=${encodeURIComponent(semester)}`;
        }

        const res = await apiFetch(url);
        if (res.ok) sectionsCache = await res.json();
        updateSectionCheckboxes();
    } catch (e) { /* ignore */ }
}

// -------------------------------------------
// Layout selection modal & helpers
// -------------------------------------------
function restoreLayoutPreference() {
    const saved = localStorage.getItem('selectedLayout');
    if (saved) selectedLayout = saved;
    const ind = document.getElementById('currentLayoutIndicator');
    if (ind) ind.textContent = selectedLayout.charAt(0).toUpperCase() + selectedLayout.slice(1);
}
function openLayoutModal() {
    const el = document.getElementById('layoutModal');
    if (!el) return;
    el.style.display = 'block';
    document.body.style.overflow = 'hidden';
}
function closeLayoutModal() {
    const el = document.getElementById('layoutModal');
    if (!el) return;
    el.style.display = 'none';
    document.body.style.overflow = 'auto';
}
function selectLayout(layoutType) {
    selectedLayout = layoutType;
    localStorage.setItem('selectedLayout', layoutType);
    document.querySelectorAll('.layout-option').forEach(o => o.classList.remove('selected'));
    const chosen = document.querySelector(`[data - layout="${layoutType}"]`);
    if (chosen) chosen.classList.add('selected');
    const indicator = document.getElementById('currentLayoutIndicator');
    if (indicator) indicator.textContent = layoutType.charAt(0).toUpperCase() + layoutType.slice(1);
    showToast('success', `${layoutType} layout selected`);
    setTimeout(() => closeLayoutModal(), 600);
}

// -------------------------------------------
// Helper: generate initials
// -------------------------------------------
function generateInitials(name) {
    if (!name) return '';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    let letters = '';

    if (parts.length === 1) {
        // Single name: take first 3 letters (e.g., "Rashmi" -> "RAS")
        letters = parts[0].slice(0, 3);
    } else if (parts.length === 2) {
        // Two names: intelligently extract 3 letters
        const first = parts[0];
        const second = parts[1];

        if (second.length === 1) {
            // Last name is single letter (e.g., "Rashmi J" -> "RSJ")
            // Take first letter + stressed consonant + last initial
            const vowels = 'aeiouAEIOU';
            let stressedLetter = '';

            // Find first consonant after position 0 (skip vowels for better pronunciation)
            for (let i = 1; i < first.length; i++) {
                if (!vowels.includes(first[i])) {
                    stressedLetter = first[i];
                    break;
                }
            }

            // Fallback to second letter if no consonant found
            if (!stressedLetter && first.length > 1) {
                stressedLetter = first[1];
            }

            letters = first[0] + stressedLetter + second[0];
        } else {
            // Both names have multiple letters (e.g., "John Smith" -> "JSM")
            letters = first[0] + second[0] + (second[1] || '');
        }
    } else {
        // Three or more names: take first letter of each (e.g., "A B C" -> "ABC")
        letters = parts.map(p => p[0]).join('');

        // If still less than 3 letters, pad from last name
        if (letters.length < 3) {
            const last = parts[parts.length - 1];
            letters += last.slice(1, 1 + (3 - letters.length));
        }
    }

    return (letters || '').toUpperCase().slice(0, 3);
}

// -------------------------------------------
// Expose some functions to window for HTML onclicks
// -------------------------------------------
window.showSection = showSection;
window.showAddModal = showAddModal;
window.editTeacher = editTeacher;
window.editSubject = editSubject;
window.editSection = editSection;
window.deleteSection = deleteSection;
window.deleteTeacher = deleteTeacher;
window.deleteSubject = deleteSubject;
window.generateTimetable = generateTimetableEnhanced;
window.validateData = async function () { try { const res = await apiFetch(`${API_BASE}/api/validate`); const data = await res.json().catch(() => ({})); if (data.valid) showToast('success', 'Data validation passed'); else showToast('warning', 'Data validation issues: ' + (data.issues || []).join(', ')); } catch (e) { showToast('error', 'Validation failed'); } };
window.viewTimetable = viewTimetable;
window.regenerateTimetable = regenerateTimetable;
window.deleteTimetable = deleteTimetable;
window.exportTimetable = exportTimetable;
window.showLoginModal = showLoginModal;
window.showRegisterModal = showRegisterModal;
window.openLayoutModal = openLayoutModal;
window.closeLayoutModal = closeLayoutModal;
window.selectLayout = selectLayout;
window.saveWorkloadConfig = saveWorkloadConfig;
window.generateTimetableEnhanced = generateTimetableEnhanced;

// -------------------------------------------
// Login/Register modal implementations (kept simple & safe)
// -------------------------------------------
function showLoginModal() {
    // Don't show modal - user should use the main login page
    // Just close any open modals and ensure login page is visible
    closeModal();
    return;
}

function showRegisterModal() {
    showModal('Register', `
        <form id="registerForm">
            <div class="form-group">
                <label>Salutation</label>
                <select name="salutation" class="form-input" style="height: 48px;">
                    <option value="">Select...</option>
                    <option value="Mr.">Mr.</option>
                    <option value="Ms.">Ms.</option>
                    <option value="Mrs.">Mrs.</option>
                    <option value="Dr.">Dr.</option>
                    <option value="Prof.">Prof.</option>
                </select>
            </div>
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" name="name" class="form-input" placeholder="Enter your full name" required>
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email" class="form-input" placeholder="your.email@example.com" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" class="form-input" placeholder="Create a strong password" required>
            </div>
            <div class="form-group">
                <label>Confirm Password</label>
                <input type="password" name="confirmPassword" class="form-input" placeholder="Re-enter your password" required>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:1rem;margin-top:1.5rem;">
                <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Register</button>
            </div>
        </form>
        `);
    setTimeout(() => {
        const form = document.getElementById('registerForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(this).entries());
            if (d.password !== d.confirmPassword) { showToast('error', 'Passwords do not match'); return; }
            const baseFromName = (d.name || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
            const baseFromEmail = (d.email || '').split('@')[0].toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
            const base = baseFromName || baseFromEmail || 'user';
            const rand = Math.random().toString(36).slice(2, 6);
            const username = `${base}_${rand}`;
            fetch(`${API_BASE}/api/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, email: d.email, password: d.password, full_name: d.name, role: 'teacher', salutation: d.salutation }) })
                .then(async res => { const data = await res.json().catch(() => ({})); if (!res.ok) { const msg = Array.isArray(data.error) ? data.error.join(', ') : (data.error || 'Registration failed'); throw new Error(msg); } return data; })
                .then(() => { showToast('success', 'Registration successful. Please login.'); closeModal(); showLoginModal(); })
                .catch(err => showToast('error', err.message || 'Registration failed'));
        });
    }, 50);
}
// -------------------------------------------
// Timetable Design Studio Integration
// -------------------------------------------
async function viewTimetable(id) {
    try {
        // Ensure caches are loaded
        if (!teachersCache || teachersCache.length === 0) {
            try { const tRes = await apiFetch(`${API_BASE}/api/teachers`); if (tRes.ok) teachersCache = await tRes.json(); } catch (e) { }
        }
        if (!subjectsCache || subjectsCache.length === 0) {
            try { const sRes = await apiFetch(`${API_BASE}/api/subjects`); if (sRes.ok) subjectsCache = await sRes.json(); } catch (e) { }
        }

        const res = await apiFetch(`${API_BASE}/api/timetables/${id}/entries`);
        if (!res.ok) { showToast('error', 'Failed to load timetable details'); return; }
        const timetableData = await res.json();

        // Open Design Studio instead of modal
        openDesignStudio(timetableData, teachersCache, subjectsCache);

    } catch (e) {
        showToast('error', 'Failed to load timetable: ' + (e.message || ''));
    }
}

function openDesignStudio(timetableData, teachers, subjects) {
    // Hide other sections
    document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));

    // Show Design Studio section
    const designStudioSection = document.getElementById('designStudio');
    if (designStudioSection) {
        designStudioSection.style.display = 'block';
        designStudioSection.classList.add('active');
    }

    // Initialize or update Design Studio
    if (!window.timetableDesignStudio) {
        window.timetableDesignStudio = new TimetableDesignStudio();
    }

    // Load data
    window.timetableDesignStudio.loadTimetableData(timetableData, teachers, subjects);
}

function closeDesignStudio() {
    const designStudioSection = document.getElementById('designStudio');
    if (designStudioSection) {
        designStudioSection.style.display = 'none';
        designStudioSection.classList.remove('active');
    }
    showSection('timetables');
}

// TimetableDesignStudio class is loaded from timetable-studio.js

