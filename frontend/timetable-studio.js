// Production-ready Timetable Design Studio - Fully Dynamic
class TimetableDesignStudio {
    constructor() {
        this.activeTheme = 'elegant';
        this.activeLayout = 'table';
        this.timetableData = null;
        this.teachers = [];
        this.subjects = [];
        this.days = [];
        this.timeSlots = [];
        this.schedule = {};
        this.breaks = [];

        this.themes = {
            elegant: {
                headerGrad: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
                headerText: '#ffffff',
                primaryBg: '#1e293b',
                primaryText: '#ffffff',
                secondaryBg: '#f8fafc',
                accentColor: '#252647ff',
                tableBorder: '#e2e8f0',
                textColor: '#334155',
                breakBg: '#fef3c7',
                breakText: '#92400e'
            },
            corporate: {
                headerGrad: 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)',
                headerText: '#ffffff',
                primaryBg: '#1e3a8a',
                primaryText: '#ffffff',
                secondaryBg: '#eff6ff',
                accentColor: '#3b82f6',
                tableBorder: '#bfdbfe',
                textColor: '#1e40af',
                breakBg: '#dbeafe',
                breakText: '#1e40af'
            },
            modern: {
                headerGrad: 'linear-gradient(135deg, #18181b 0%, #27272a 100%)',
                headerText: '#ffffff',
                primaryBg: '#18181b',
                primaryText: '#ffffff',
                secondaryBg: '#f4f4f5',
                accentColor: '#71717a',
                tableBorder: '#e4e4e7',
                textColor: '#27272a',
                breakBg: '#e4e4e7',
                breakText: '#18181b'
            }
        };
    }

    loadTimetableData(timetableData, teachers, subjects) {
        this.timetableData = Array.isArray(timetableData) ? timetableData[0] : timetableData;
        this.teachers = teachers || [];
        this.subjects = subjects || [];

        // Extract dynamic data from backend
        this.days = this.timetableData.days || [];
        this.timeSlots = this.timetableData.periods || [];
        const entries = this.timetableData.entries || [];

        // Generate timings if not provided
        if (!this.timetableData.timings || Object.keys(this.timetableData.timings).length === 0) {
            console.log('No timings from backend, generating default timings');
            this.timetableData.timings = this.generateTimings(this.timeSlots);
        } else {
            console.log('Using timings from backend:', this.timetableData.timings);
            // Ensure timings keys match period slots (convert to strings if needed)
            const normalizedTimings = {};
            Object.keys(this.timetableData.timings).forEach(key => {
                normalizedTimings[String(key)] = this.timetableData.timings[key];
            });
            this.timetableData.timings = normalizedTimings;
        }

        // Identify breaks - improved logic
        this.breaks = [];
        const breaksByPeriod = {};

        entries.forEach(entry => {
            if (entry.is_break) {
                const period = entry.period;
                if (!breaksByPeriod[period]) {
                    breaksByPeriod[period] = {
                        period: period,
                        name: (entry.break_type || 'Break').toUpperCase(),
                        days: []
                    };
                }
                if (!breaksByPeriod[period].days.includes(entry.day)) {
                    breaksByPeriod[period].days.push(entry.day);
                }
            }
        });

        // Add all breaks that span all days
        Object.values(breaksByPeriod).forEach(brk => {
            if (brk.days.length === this.days.length) {
                this.breaks.push(brk);
            }
        });

        // Build schedule
        this.schedule = {};
        this.days.forEach(day => {
            this.schedule[day] = this.timeSlots.map(period => {
                const entry = entries.find(e => e.day === day && e.period === period);
                if (!entry) return { type: 'empty', value: '—' };
                if (entry.is_break) return { type: 'break', value: (entry.break_type || 'Break').toUpperCase() };

                const subject = this.subjects.find(s => s.id === entry.subject_id);
                const teacher = this.teachers.find(t => t.id === entry.teacher_id);

                return {
                    type: 'class',
                    subject: subject ? (subject.abbreviation || subject.code || subject.name).toUpperCase() : '—',
                    teacher: teacher ? (teacher.initials || teacher.name) : '',
                    hall: entry.hall || ''
                };
            });
        });

        this.render();
    }

    generateTimings(periods) {
        // Generate default timings based on periods
        // This is a fallback - the backend should provide accurate timings
        const timings = {};
        let startHour = 9;
        let startMin = 0;
        const periodDuration = 60; // 60 minutes per period (fallback default)

        periods.forEach((period, index) => {
            const endHour = startHour + Math.floor((startMin + periodDuration) / 60);
            const endMin = (startMin + periodDuration) % 60;

            timings[period] = `${String(startHour).padStart(2, '0')}:${String(startMin).padStart(2, '0')} - ${String(endHour).padStart(2, '0')}:${String(endMin).padStart(2, '0')}`;

            startHour = endHour;
            startMin = endMin;
        });

        return timings;
    }

    getTheme() {
        return this.themes[this.activeTheme];
    }

    setTheme(theme) {
        if (this.themes[theme]) {
            this.activeTheme = theme;
            this.render();
        }
    }

    setLayout(layout) {
        this.activeLayout = layout;
        this.render();
    }

    escapeHtml(unsafe) {
        if (!unsafe) return '';
        return String(unsafe)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    renderHeader() {
        const theme = this.getTheme();
        const tt = this.timetableData || {};
        const logoUrl = tt.logo_data_url || tt.logoDataUrl;

        // Extract section details from sections_meta if available
        let sectionName = tt.section || 'N/A';
        let lectureHall = 'N/A';
        let classTeacher = 'N/A';

        if (tt.sections_meta && Array.isArray(tt.sections_meta) && tt.sections_meta.length > 0) {
            const sectionData = tt.sections_meta[0];
            sectionName = sectionData.name || sectionName;
            lectureHall = sectionData.lectureHall || sectionData.lecture_hall || 'N/A';
            classTeacher = sectionData.classTeacher || sectionData.class_teacher || 'N/A';
        }

        return `
            <div style="background: ${theme.headerGrad}; padding: 3rem; border-radius: 16px 16px 0 0;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 2rem;">
                    <div style="display: flex; align-items: center; gap: 2rem; flex: 1;">
                        ${logoUrl ? `
                            <img src="${logoUrl}" alt="Logo" style="height: 140px; width: auto; max-width: 300px; object-fit: contain; background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 16px; padding: 1.5rem; border: 2px solid rgba(255,255,255,0.2);" />
                        ` : ''}
                        <div style="flex: 1;">
                            <p style="color: rgba(255,255,255,0.9); font-size: 1.5rem; margin: 0;">Academic Schedule</p>
                        </div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border: 2px solid rgba(255,255,255,0.2); border-radius: 12px; padding: 1rem 1.5rem; text-align: right;">
                        <p style="color: rgba(255,255,255,0.7); font-size: 0.75rem; margin: 0 0 0.25rem 0;">Effective From</p>
                        <p style="color: ${theme.headerText}; font-size: 1.125rem; margin: 0;">${this.escapeHtml(tt.wef_date || tt.wefDate || 'N/A')}</p>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem;">
                    ${this.renderInfoCard('Programme', tt.programme_name || tt.programmeName || 'N/A', theme)}
                    ${this.renderInfoCard('Semester', String(tt.semester || 'N/A'), theme)}
                    ${this.renderInfoCard('Term', tt.term_label || tt.termLabel || 'N/A', theme)}
                    ${this.renderInfoCard('Section', sectionName, theme)}
                    ${this.renderInfoCard('Lecture Hall', lectureHall, theme)}
                    ${this.renderInfoCard('Class Teacher', classTeacher, theme)}
                </div>
            </div>
        `;
    }

    renderInfoCard(label, value, theme) {
        return `
            <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border: 2px solid rgba(255,255,255,0.2); border-radius: 12px; padding: 1rem;">
                <p style="color: rgba(255,255,255,0.7); font-size: 0.75rem; margin: 0 0 0.25rem 0;">${label}</p>
                <p style="color: ${theme.headerText}; font-size: 0.875rem; margin: 0;">${this.escapeHtml(value)}</p>
            </div>
        `;
    }

    renderControlBar() {
        const theme = this.getTheme();
        return `
            <div style="background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 50; border-bottom: 1px solid #e5e7eb; margin-bottom: 2rem;">
                <div style="max-width: 1280px; margin: 0 auto; padding: 1rem 2rem;">
                    <div style="display: flex; flex-direction: column; gap: 1rem;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <h2 style="font-size: 1.5rem; font-weight: 300; color: #1f2937; margin: 0;">Timetable Design Studio</h2>
                            <button onclick="closeDesignStudio()" style="padding: 0.5rem 1rem; background: #6b7280; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem;">Back to Timetables</button>
                        </div>
                        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                            <span style="font-size: 0.875rem; font-weight: 600; color: #6b7280;">Themes:</span>
                            ${['elegant', 'corporate', 'modern'].map(t => `
                                <button class="theme-btn" data-theme="${t}" style="padding: 0.5rem 1.25rem; border-radius: 8px; font-size: 0.875rem; font-weight: 500; border: none; cursor: pointer; transition: all 0.2s; ${this.activeTheme === t ? `background: ${theme.primaryBg}; color: ${theme.primaryText}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);` : 'background: #e5e7eb; color: #374151;'}">${t.charAt(0).toUpperCase() + t.slice(1)}</button>
                            `).join('')}
                        </div>
                        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                            <span style="font-size: 0.875rem; font-weight: 600; color: #6b7280;">Layouts:</span>
                            ${[['table', 'Table'], ['card', 'Cards'], ['timeline', 'Timeline'], ['week', 'Week']].map(([key, label]) => `
                                <button class="layout-btn" data-layout="${key}" style="padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; font-weight: 500; border: none; cursor: pointer; transition: all 0.2s; ${this.activeLayout === key ? `background: ${theme.primaryBg}; color: ${theme.primaryText}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);` : 'background: #e5e7eb; color: #374151;'}">${label}</button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }



    renderTableView() {
        const theme = this.getTheme();
        const colWidth = `${100 / (this.timeSlots.length + 1)}%`;

        let html = `<div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; table-layout: fixed; min-width: 1000px;">
            <thead><tr>
                <th style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1.25rem; text-align: center; font-weight: 600; border-right: 1px solid ${theme.tableBorder}; width: ${colWidth};">
                    <div style="font-size: 0.875rem;">Day / Time</div>
                </th>`;

        this.timeSlots.forEach(slot => {
            // Try both string and number keys for timing lookup
            const timing = this.timetableData.timings ?
                (this.timetableData.timings[slot] || this.timetableData.timings[String(slot)]) : '';
            html += `<th style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1rem; font-size: 0.875rem; font-weight: 600; border-right: 1px solid ${theme.tableBorder}; width: ${colWidth}; text-align: center;">
                <div style="margin-bottom: 4px;">Period ${this.escapeHtml(slot)}</div>
                ${timing ? `<div style="font-size: 0.7rem; opacity: 0.8; font-weight: 400;">${this.escapeHtml(timing)}</div>` : ''}
            </th>`;
        });

        html += `</tr></thead><tbody>`;

        this.days.forEach((day, dayIndex) => {
            html += `<tr style="border-bottom: 1px solid ${theme.tableBorder};">`;
            html += `<td style="background: ${theme.secondaryBg}; padding: 1.25rem; font-weight: 600; color: ${theme.textColor}; border-right: 1px solid ${theme.tableBorder}; text-align: center;">${day}</td>`;

            this.timeSlots.forEach((slot, idx) => {
                const cellData = this.schedule[day]?.[idx] || { type: 'empty', value: '—' };
                // Use loose equality to handle string/number mismatch for periods
                const isBreak = this.breaks.some(b => b.period == slot);

                if (isBreak && dayIndex === 0) {
                    const breakInfo = this.breaks.find(b => b.period == slot);
                    html += `<td rowspan="${this.days.length}" style="background: ${theme.breakBg}; color: ${theme.breakText}; padding: 1rem; text-align: center; font-weight: 700; border-right: 1px solid ${theme.tableBorder}; vertical-align: middle; writing-mode: vertical-rl; text-orientation: upright; letter-spacing: 4px; font-size: 0.875rem;">${this.escapeHtml(breakInfo.name)}</td>`;
                } else if (!isBreak) {
                    html += `<td style="padding: 1rem; border-right: 1px solid ${theme.tableBorder}; text-align: center; vertical-align: middle;">
                        <div style="font-size: 0.875rem; font-weight: 600; color: ${theme.textColor};">${this.escapeHtml(cellData.subject || cellData.value)}</div>
                        ${cellData.teacher ? `<div style="font-size: 0.7rem; color: #6b7280; margin: 0.25rem 0 0 0;">${this.escapeHtml(cellData.teacher)}</div>` : ''}
                    </td>`;
                }
            });

            html += `</tr>`;
        });

        html += `</tbody></table></div>`;
        return html;
    }

    renderCardView() {
        const theme = this.getTheme();
        let html = `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">`;

        this.days.forEach(day => {
            html += `<div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid ${theme.tableBorder}; overflow: hidden;">
                <div style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1rem; text-align: center; font-weight: 600;">${day}</div>
                <div style="padding: 1rem;">`;

            this.timeSlots.forEach((slot, idx) => {
                const cellData = this.schedule[day]?.[idx] || { type: 'empty', value: '—' };
                const isBreak = cellData.type === 'break';

                html += `<div style="padding: 0.75rem; margin-bottom: 0.75rem; border-bottom: 1px solid ${theme.tableBorder}; ${isBreak ? `background: ${theme.breakBg}; border-radius: 8px;` : ''}">
                    <p style="font-size: 0.75rem; color: #6b7280; margin: 0 0 0.25rem 0;">${this.escapeHtml(slot)}</p>
                    <p style="font-size: 0.875rem; font-weight: 500; color: ${isBreak ? theme.breakText : theme.textColor}; margin: 0;">${this.escapeHtml(cellData.subject || cellData.value)}</p>
                    ${cellData.teacher ? `<p style="font-size: 0.75rem; color: #6b7280; margin: 0.25rem 0 0 0;">${this.escapeHtml(cellData.teacher)}</p>` : ''}
                </div>`;
            });

            html += `</div></div>`;
        });

        html += `</div>`;
        return html;
    }

    renderTimelineView() {
        const theme = this.getTheme();
        let html = `<div style="display: flex; flex-direction: column; gap: 2rem;">`;

        this.days.forEach(day => {
            html += `<div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid ${theme.tableBorder}; overflow: hidden;">
                <div style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1rem; font-weight: 600;">${day}</div>
                <div style="padding: 1.5rem;">`;

            this.timeSlots.forEach((slot, idx) => {
                const cellData = this.schedule[day]?.[idx] || { type: 'empty', value: '—' };
                const isBreak = cellData.type === 'break';

                html += `<div style="display: flex; gap: 1rem; align-items: start; padding-bottom: 1rem; border-bottom: 1px solid ${theme.tableBorder}; margin-bottom: 1rem;">
                    <div style="min-width: 100px;"><span style="font-size: 0.875rem; font-weight: 600; color: ${theme.accentColor};">${this.escapeHtml(slot)}</span></div>
                    <div style="flex: 1; ${isBreak ? `background: ${theme.breakBg}; padding: 0.5rem; border-radius: 8px;` : ''}">
                        <p style="font-size: 0.875rem; font-weight: 500; color: ${isBreak ? theme.breakText : theme.textColor}; margin: 0;">${this.escapeHtml(cellData.subject || cellData.value)}</p>
                        ${cellData.teacher ? `<p style="font-size: 0.75rem; color: #6b7280; margin: 0.25rem 0 0 0;">${this.escapeHtml(cellData.teacher)}</p>` : ''}
                    </div>
                </div>`;
            });

            html += `</div></div>`;
        });

        html += `</div>`;
        return html;
    }

    renderWeekView() {
        const theme = this.getTheme();
        let html = `<div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid ${theme.tableBorder}; overflow: hidden;">
            <div style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1.5rem;"><h3 style="margin: 0; font-size: 1.125rem; font-weight: 600;">Weekly Schedule</h3></div>
            <div style="padding: 1.5rem;"><div style="display: grid; grid-template-columns: repeat(${this.days.length}, 1fr); gap: 0.5rem;">`;

        this.days.forEach(day => {
            html += `<div style="background: ${theme.secondaryBg}; border-radius: 12px; padding: 1rem;">
                <div style="font-weight: 600; text-align: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 2px solid ${theme.accentColor};">${day}</div>
                <div style="max-height: 400px; overflow-y: auto;">`;

            this.timeSlots.forEach((slot, idx) => {
                const cellData = this.schedule[day]?.[idx] || { type: 'empty', value: '—' };
                const isBreak = cellData.type === 'break';

                html += `<div style="background: white; border: 1px solid ${theme.tableBorder}; border-radius: 6px; padding: 0.5rem; margin-bottom: 0.5rem; ${isBreak ? `background: ${theme.breakBg};` : ''}">
                    <p style="font-size: 0.625rem; color: #6b7280; margin: 0 0 0.25rem 0;">${this.escapeHtml(slot)}</p>
                    <p style="font-size: 0.75rem; font-weight: 500; color: ${isBreak ? theme.breakText : theme.textColor}; margin: 0;">${this.escapeHtml(cellData.subject || cellData.value)}</p>
                </div>`;
            });

            html += `</div></div>`;
        });

        html += `</div></div></div>`;
        return html;
    }

    renderLayout() {
        switch (this.activeLayout) {
            case 'table': return this.renderTableView();
            case 'card': return this.renderCardView();
            case 'timeline': return this.renderTimelineView();
            case 'week': return this.renderWeekView();
            default: return this.renderTableView();
        }
    }

    getUniqueItems() {
        const entries = this.timetableData.entries || [];
        const uniqueSubjects = new Map();
        const uniqueTeachers = new Map();

        entries.forEach(entry => {
            if (entry.is_break) return;

            if (entry.subject_id) {
                const subject = this.subjects.find(s => s.id === entry.subject_id);
                if (subject) uniqueSubjects.set(subject.id, subject);
            }

            // Teacher can be on entry or subject
            let teacherId = entry.teacher_id;
            if (!teacherId && entry.subject_id) {
                const subject = this.subjects.find(s => s.id === entry.subject_id);
                if (subject) teacherId = subject.teacher_id;
            }

            if (teacherId) {
                const teacher = this.teachers.find(t => t.id === teacherId);
                if (teacher) uniqueTeachers.set(teacher.id, teacher);
            }
        });

        return {
            subjects: Array.from(uniqueSubjects.values()),
            teachers: Array.from(uniqueTeachers.values())
        };
    }

    renderTeachingStaff() {
        const { teachers } = this.getUniqueItems();
        const theme = this.getTheme();

        if (teachers.length === 0) return '';

        let html = `
            <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid ${theme.tableBorder}; overflow: hidden;">
                <div style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1.5rem; border-bottom: 1px solid ${theme.tableBorder};">
                    <h3 style="margin: 0; font-size: 1.25rem; font-weight: 500; letter-spacing: -0.025em;">Teaching Faculty</h3>
                </div>
                <div style="padding: 1.5rem;">
                    <div style="display: grid; gap: 1rem;">
        `;

        teachers.forEach(teacher => {
            const displayName = teacher.title ? `${teacher.title} ${teacher.name}` : teacher.name;
            html += `
                <div style="display: flex; align-items: center; gap: 1rem; padding: 1rem; background: ${theme.secondaryBg}; border-radius: 12px; border: 1px solid ${theme.tableBorder}; min-height: 88px; box-sizing: border-box; transition: transform 0.2s; hover: {transform: translateY(-2px);}">
                    <div style="width: 48px; height: 48px; border-radius: 50%; background: ${theme.accentColor}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex-shrink: 0;">
                        ${teacher.initials || 'T'}
                    </div>
                    <p style="margin: 0; font-weight: 600; color: ${theme.textColor}; font-size: 1rem; line-height: 1.3;">${this.escapeHtml(displayName)}</p>
                </div>
            `;
        });

        html += `</div></div></div>`;
        return html;
    }

    renderCourseDetails() {
        const { subjects } = this.getUniqueItems();
        const theme = this.getTheme();

        if (subjects.length === 0) return '';

        let html = `
            <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid ${theme.tableBorder}; overflow: hidden;">
                <div style="background: ${theme.primaryBg}; color: ${theme.primaryText}; padding: 1.5rem; border-bottom: 1px solid ${theme.tableBorder};">
                    <h3 style="margin: 0; font-size: 1.25rem; font-weight: 500; letter-spacing: -0.025em;">Course Details</h3>
                </div>
                <div style="padding: 1.5rem;">
                    <div style="display: grid; gap: 1rem;">
        `;

        subjects.forEach(subject => {
            html += `
                <div style="display: flex; align-items: center; gap: 1rem; padding: 1rem; background: ${theme.secondaryBg}; border-radius: 12px; border: 1px solid ${theme.tableBorder}; min-height: 88px; box-sizing: border-box;">
                    <div style="width: 48px; height: 48px; border-radius: 12px; background: ${theme.accentColor}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.875rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex-shrink: 0;">
                        ${this.escapeHtml(subject.abbreviation || subject.code.substring(0, 3))}
                    </div>
                    
                    <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center;">
                        <h4 style="margin: 0 0 0.25rem 0; color: ${theme.textColor}; font-weight: 600; font-size: 1rem; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this.escapeHtml(subject.name)}</h4>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 0.75rem; color: #6b7280; font-weight: 500; background: white; padding: 0.125rem 0.5rem; border-radius: 4px; border: 1px solid ${theme.tableBorder};">${this.escapeHtml(subject.code)}</span>
                            <span style="font-size: 0.75rem; color: #6b7280;">${this.escapeHtml(subject.subject_type || subject.type || 'Theory')}</span>
                        </div>
                    </div>

                    <div style="flex-shrink: 0;">
                        <span style="font-size: 0.75rem; font-weight: 600; color: ${theme.textColor}; background: white; padding: 0.25rem 0.75rem; border-radius: 999px; border: 1px solid ${theme.tableBorder}; white-space: nowrap;">
                            ${subject.credits} Cr
                        </span>
                    </div>
                </div>
            `;
        });

        html += `</div></div></div>`;
        return html;
    }

    render() {
        const container = document.getElementById('designStudioContainer');
        if (!container) return;

        container.innerHTML = `
            <div style="min-height: 100vh; background: linear-gradient(to bottom right, #f9fafb, #f3f4f6);">
                ${this.renderControlBar()}
                <div style="padding: 3rem;">
                    <div style="max-width: 1280px; margin: 0 auto;">
                        <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e5e7eb; margin-bottom: 2rem;">
                            ${this.renderHeader()}
                        </div>
                        <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e5e7eb; padding: 2rem; margin-bottom: 2rem;">
                            ${this.renderLayout()}
                        </div>
                        
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 2rem;">
                            ${this.renderTeachingStaff()}
                            ${this.renderCourseDetails()}
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    attachEventListeners() {
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setTheme(e.currentTarget.dataset.theme));
        });

        document.querySelectorAll('.layout-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setLayout(e.currentTarget.dataset.layout));
        });
    }
}
