/* EventSphere dashboard frontend */

(() => {
  'use strict';

  let csrfToken = '';
  let currentUser = null;

  const $ = (id) => document.getElementById(id);

  // ==========================================
  // EVENTSPHERE CUSTOM DIALOGS
  // Replaces browser alert(), prompt() and confirm().
  // ==========================================

  function installEventSphereDialogs() {
    if (document.getElementById('es-dialog-styles')) return;

    const style = document.createElement('style');
    style.id = 'es-dialog-styles';

    style.textContent = `
      .es-dialog-backdrop {
        position: fixed;
        inset: 0;
        z-index: 100000;
        background: rgba(15,23,42,.58);
        backdrop-filter: blur(5px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 18px;
        animation: esDialogFade .18s ease;
      }

      .es-dialog {
        width: min(100%,460px);
        background: #fff;
        border: 1px solid #e8edf5;
        border-radius: 20px;
        padding: 27px;
        box-shadow: 0 24px 80px rgba(15,23,42,.25);
        font-family: inherit;
        animation: esDialogUp .22s ease;
        max-height: 90vh;
        overflow: auto;
      }

      .es-dialog-icon {
        width: 52px;
        height: 52px;
        border-radius: 16px;
        display: grid;
        place-items: center;
        font-size: 25px;
        font-weight: 800;
        margin-bottom: 17px;
      }

      .es-dialog-icon.success {
        background: #dcfce7;
        color: #15803d;
      }

      .es-dialog-icon.error {
        background: #fee2e2;
        color: #b91c1c;
      }

      .es-dialog-icon.warning {
        background: #fef3c7;
        color: #b45309;
      }

      .es-dialog-icon.info {
        background: #dbeafe;
        color: #1d4ed8;
      }

      .es-dialog-title {
        font-size: 21px;
        line-height: 1.3;
        font-weight: 750;
        color: #172033;
        margin: 0 0 9px;
      }

      .es-dialog-message {
        font-size: 14px;
        line-height: 1.7;
        color: #64748b;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        margin: 0 0 20px;
      }

      .es-dialog-detail {
        padding: 12px 14px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        color: #475569;
        font-size: 13px;
        line-height: 1.6;
        margin: -5px 0 20px;
        overflow-wrap: anywhere;
      }

      .es-dialog-label {
        display: block;
        font-size: 13px;
        font-weight: 650;
        color: #475569;
        margin: 0 0 8px;
      }

      .es-dialog-input {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #cbd5e1;
        border-radius: 11px;
        padding: 12px 13px;
        font: inherit;
        font-size: 14px;
        color: #172033;
        outline: none;
        margin-bottom: 20px;
        background: #fff;
      }

      .es-dialog-input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59,130,246,.13);
      }

      .es-dialog-actions {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
        flex-wrap: wrap;
      }

      .es-dialog-btn {
        border: 0;
        border-radius: 10px;
        padding: 11px 17px;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
        transition: background .15s, transform .15s;
        min-width: 92px;
      }

      .es-dialog-btn:hover {
        transform: translateY(-1px);
      }

      .es-dialog-btn.primary {
        background: #2563eb;
        color: #fff;
      }

      .es-dialog-btn.primary:hover {
        background: #1d4ed8;
      }

      .es-dialog-btn.success {
        background: #16a34a;
        color: #fff;
      }

      .es-dialog-btn.success:hover {
        background: #15803d;
      }

      .es-dialog-btn.danger {
        background: #dc2626;
        color: #fff;
      }

      .es-dialog-btn.danger:hover {
        background: #b91c1c;
      }

      .es-dialog-btn.secondary {
        background: #f1f5f9;
        color: #475569;
      }

      .es-dialog-btn.secondary:hover {
        background: #e2e8f0;
      }

      @keyframes esDialogFade {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      @keyframes esDialogUp {
        from {
          opacity: 0;
          transform: translateY(12px) scale(.98);
        }
        to {
          opacity: 1;
          transform: translateY(0) scale(1);
        }
      }

      @media(max-width:480px) {
        .es-dialog {
          padding: 22px;
          border-radius: 17px;
        }

        .es-dialog-actions {
          flex-direction: column-reverse;
        }

        .es-dialog-btn {
          width: 100%;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function dialogBase({
    title,
    message,
    type = 'info',
    icon = 'ℹ',
    detail = ''
  }) {
    installEventSphereDialogs();

    const backdrop = document.createElement('div');
    backdrop.className = 'es-dialog-backdrop';

    const panel = document.createElement('section');
    panel.className = 'es-dialog';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');

    const iconEl = document.createElement('div');
    iconEl.className = `es-dialog-icon ${type}`;
    iconEl.textContent = icon;

    const heading = document.createElement('h2');
    heading.className = 'es-dialog-title';
    heading.textContent = title;

    const body = document.createElement('p');
    body.className = 'es-dialog-message';
    body.textContent = String(message ?? '');

    panel.append(iconEl, heading, body);

    if (detail) {
      const detailEl = document.createElement('div');
      detailEl.className = 'es-dialog-detail';
      detailEl.textContent = detail;
      panel.appendChild(detailEl);
    }

    backdrop.appendChild(panel);
    document.body.appendChild(backdrop);

    return { backdrop, panel };
  }

  function showAppAlert(message) {
    let title = 'Notification';
    let type = 'info';
    let icon = 'ℹ';
    let text = String(message ?? '');
    let detail = '';

    try {
      const parsed = JSON.parse(text);

      if (parsed && typeof parsed === 'object') {
        const info = parsed.detail ?? parsed.message ?? parsed;

        if (typeof info === 'string') {
          text = info;
        } else if (info && typeof info === 'object') {
          text = info.message ||
            info.reason?.reason ||
            info.reason ||
            'The request could not be completed.';

          if (typeof text !== 'string') {
            text = JSON.stringify(text);
          }

          const extra =
            info.reason && typeof info.reason === 'object'
              ? info.reason
              : null;

          if (extra) {
            detail = extra.reason || JSON.stringify(extra);
          } else if (info.conflicting_event_title) {
            detail = `Conflicting event: ${info.conflicting_event_title}`;
          }
        }
      }
    } catch (_) {
      // Ordinary text message.
    }

    const lower = text.toLowerCase();

    if (/success|created|published|accepted|approved|checked in/.test(lower)) {
      title = 'Completed successfully';
      type = 'success';
      icon = '✓';
    } else if (
      /refus|reject|unavailable|failed|error|invalid|exceed|not found|already/.test(lower) ||
      detail
    ) {
      title = 'Request could not be completed';
      type = 'error';
      icon = '×';
    } else if (/cancel|expired|warning|attention/.test(lower)) {
      title = 'Please note';
      type = 'warning';
      icon = '!';
    }

    const { backdrop, panel } = dialogBase({
      title,
      message: text,
      type,
      icon,
      detail
    });

    const actions = document.createElement('div');
    actions.className = 'es-dialog-actions';

    const ok = document.createElement('button');
    ok.className = `es-dialog-btn ${
      type === 'success'
        ? 'success'
        : type === 'error'
          ? 'danger'
          : 'primary'
    }`;
    ok.textContent = 'Got it';

    const close = () => {
      backdrop.remove();
      document.removeEventListener('keydown', onKey);
    };

    const onKey = e => {
      if (e.key === 'Escape' || e.key === 'Enter') close();
    };

    ok.addEventListener('click', close);

    backdrop.addEventListener('click', e => {
      if (e.target === backdrop) close();
    });

    document.addEventListener('keydown', onKey);

    actions.appendChild(ok);
    panel.appendChild(actions);
    ok.focus();
  }

  function showAppPrompt(message, defaultValue = '') {
    return new Promise(resolve => {
      const { backdrop, panel } = dialogBase({
        title: 'Enter details',
        message,
        type: 'info',
        icon: '✎'
      });

      const input = document.createElement('input');
      input.className = 'es-dialog-input';
      input.type = 'text';
      input.value = defaultValue ?? '';
      input.setAttribute('aria-label', message);

      const actions = document.createElement('div');
      actions.className = 'es-dialog-actions';

      const cancel = document.createElement('button');
      cancel.className = 'es-dialog-btn secondary';
      cancel.textContent = 'Cancel';

      const save = document.createElement('button');
      save.className = 'es-dialog-btn primary';
      save.textContent = 'Continue';

      let finished = false;

      const close = value => {
        if (finished) return;
        finished = true;
        backdrop.remove();
        document.removeEventListener('keydown', onKey);
        resolve(value);
      };

      const onKey = e => {
        if (e.key === 'Escape') close(null);
        if (e.key === 'Enter') close(input.value);
      };

      cancel.addEventListener('click', () => close(null));
      save.addEventListener('click', () => close(input.value));

      backdrop.addEventListener('click', e => {
        if (e.target === backdrop) close(null);
      });

      document.addEventListener('keydown', onKey);

      actions.append(cancel, save);
      panel.append(input, actions);

      input.focus();
      input.select();
    });
  }

  function showAppConfirm(message, options = {}) {
    return new Promise(resolve => {
      const { backdrop, panel } = dialogBase({
        title: options.title || 'Please confirm',
        message,
        type: 'warning',
        icon: '!'
      });

      const actions = document.createElement('div');
      actions.className = 'es-dialog-actions';

      const cancel = document.createElement('button');
      cancel.className = 'es-dialog-btn secondary';
      cancel.textContent = 'Go back';

      const confirm = document.createElement('button');
      confirm.className = `es-dialog-btn ${
        options.danger ? 'danger' : 'primary'
      }`;
      confirm.textContent = options.confirmText || 'Confirm';

      let finished = false;

      const close = value => {
        if (finished) return;
        finished = true;
        backdrop.remove();
        document.removeEventListener('keydown', onKey);
        resolve(value);
      };

      const onKey = e => {
        if (e.key === 'Escape') close(false);
        if (e.key === 'Enter') close(true);
      };

      cancel.addEventListener('click', () => close(false));
      confirm.addEventListener('click', () => close(true));

      backdrop.addEventListener('click', e => {
        if (e.target === backdrop) close(false);
      });

      document.addEventListener('keydown', onKey);

      actions.append(cancel, confirm);
      panel.appendChild(actions);
      confirm.focus();
    });
  }

  // Keep existing alert(message) calls using EventSphere styling.
  window.alert = showAppAlert;

  function show(id, value) {
    const el = $(id);
    if (!el) return;

    el.textContent = typeof value === 'string'
      ? value
      : JSON.stringify(value, null, 2);
  }

  function displayError(id, error) {
    show(id, error?.message || String(error));
  }

  function formValues(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function toIso(value) {
    const date = new Date(value);

    if (!value || Number.isNaN(date.getTime())) {
      throw new Error('Please enter a valid date and time.');
    }

    return date.toISOString();
  }

  function safeText(value) {
    return value === null || value === undefined || value === ''
      ? '—'
      : String(value);
  }

  async function request(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { ...(options.headers || {}) };

    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    if (method !== 'GET') {
      headers['X-CSRF-Token'] = csrfToken;
    }

    const response = await fetch(path, {
      ...options,
      method,
      headers,
      credentials: 'same-origin'
    });

    const raw = await response.text();
    let data = {};

    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { detail: raw };
    }

    if (!response.ok) {
      let detail = data.detail ?? data.message ??
        `Request failed (${response.status})`;

      if (typeof detail !== 'string') {
        detail = JSON.stringify(detail);
      }

      throw new Error(detail);
    }

    return data;
  }

  const post = (path, payload) =>
    request(path, {
      method: 'POST',
      body: JSON.stringify(payload)
    });

  const put = (path, payload) =>
    request(path, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });

  function agentResult(label, result) {
    show(
      'agentResult',
      `${label}\n${JSON.stringify(result, null, 2)}`
    );
  }

  function button(label, handler, className = '') {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = `btn ${className}`.trim();
    el.textContent = label;
    el.addEventListener('click', handler);
    return el;
  }

  function renderTable(id, headings, rows) {
    const host = $(id);
    if (!host) return;

    host.replaceChildren();

    if (!rows.length) {
      host.textContent = 'No records found.';
      return;
    }

    const wrap = document.createElement('div');
    wrap.className = 'tablewrap';

    const table = document.createElement('table');
    table.className = 'table';

    const thead = document.createElement('thead');
    const header = document.createElement('tr');

    headings.forEach(text => {
      const th = document.createElement('th');
      th.textContent = text;
      header.append(th);
    });

    thead.append(header);
    table.append(thead);

    const tbody = document.createElement('tbody');

    rows.forEach(row => {
      const tr = document.createElement('tr');

      row.forEach(value => {
        const td = document.createElement('td');

        if (value instanceof Node) {
          td.append(value);
        } else {
          td.textContent = safeText(value);
        }

        tr.append(td);
      });

      tbody.append(tr);
    });

    table.append(tbody);
    wrap.append(table);
    host.append(wrap);
  }

  function actionGroup(actions) {
    const span = document.createElement('span');

    actions.forEach(a => {
      span.append(
        button(a.label, a.run, a.className || '')
      );
    });

    return span;
  }

  async function refreshCsrf() {
    const result = await request('/api/auth/csrf');
    csrfToken = result.csrf_token;

    if (!csrfToken) {
      throw new Error(
        'Security token was not returned by the server.'
      );
    }
  }


  // ==========================================
  // NAVIGATION
  // ==========================================

  function setupNavigation() {
    document.querySelectorAll('[data-tab]').forEach(navButton => {
      navButton.addEventListener('click', async () => {
        document.querySelectorAll('.section').forEach(section => {
          section.classList.remove('active');
        });

        document.querySelectorAll('[data-tab]').forEach(item => {
          item.classList.remove('active');
        });

        $(`s-${navButton.dataset.tab}`)?.classList.add('active');
        navButton.classList.add('active');

        await loadTab(navButton.dataset.tab);
      });
    });
  }

  async function loadTab(tab) {
    const loaders = {
      events: loadEvents,
      venues: loadVenues,
      bookings: loadBookings,
      tickets: loadTickets,
      waitlist: loadWaitlist,
      myhire: loadMyHire,
      hireadmin: loadPendingHire,
      checkin: loadEventsForCheckin,
      stats: loadStats,
      agents: loadAgentData,
      notifications: loadNotifications
    };

    if (loaders[tab]) {
      await loaders[tab]();
    }
  }

  // ==========================================
  // INITIALIZATION
  // ==========================================

  async function init() {
    try {
      await refreshCsrf();

      currentUser = await request('/api/auth/me');

      const accessPath = {
        admin: '/api/admin/access-check',
        staff: '/api/staff/access-check',
        attendee: '/api/attendee/access-check'
      }[currentUser.role];

      if (!accessPath) {
        throw new Error('Your account has an unsupported role.');
      }

      await request(accessPath);

      $('fullname').textContent = currentUser.full_name;
      $('role').textContent = currentUser.role;
      $('statRole').textContent = currentUser.role;
      $('statEmail').textContent = currentUser.email;

      $('title').textContent =
        `${currentUser.role[0].toUpperCase()}${currentUser.role.slice(1)} Dashboard`;

      const navId = {
        admin: 'adminNav',
        staff: 'staffNav',
        attendee: 'attendeeNav'
      }[currentUser.role];

      $(navId)?.classList.remove('hidden');

      if (currentUser.role === 'admin') {
        $('eventCreateCard')?.classList.remove('hidden');
      }

      setupNavigation();
      bindFormsAndButtons();

      await loadVenues();
      await loadEvents();

      if (currentUser.role === 'admin') {
        await Promise.all([
          loadStats(),
          loadAgentData(),
          loadPendingHire()
        ]);
      }

      if (currentUser.role === 'attendee') {
        await Promise.all([
          loadBookings(),
          loadTickets(),
          loadWaitlist(),
          loadMyHire()
        ]);
      }

      await loadNotifications();

    } catch (error) {
      alert(error.message || 'Please log in to continue.');
      location.href = '/login';
    }
  }

  // ==========================================
  // BUTTON AND FORM EVENTS
  // ==========================================

  function bindFormsAndButtons() {
    if ($('logout')) {
      $('logout').onclick = async () => {
        try {
          await post('/api/auth/logout', {});
        } finally {
          location.href = '/login';
        }
      };
    }

    const bindings = {
      loadEvents,
      loadVenues,
      loadBookings,
      loadTickets,
      loadWaitlist,
      loadMyHire,
      loadPendingHire,
      loadStats,
      loadAgentMessages,
      loadAgentStates,
      loadNotifications
    };

    Object.entries(bindings).forEach(([id, fn]) => {
      if ($(id)) $(id).onclick = fn;
    });

    if ($('eventForm')) $('eventForm').onsubmit = createEvent;
    if ($('venueForm')) $('venueForm').onsubmit = createVenue;
    if ($('waitForm')) $('waitForm').onsubmit = joinWaitlist;
    if ($('hireForm')) $('hireForm').onsubmit = createHire;
    if ($('checkinForm')) $('checkinForm').onsubmit = checkin;

     if ($('startQrScanner')) {
  $('startQrScanner').onclick = startQrScanner;
}

if ($('stopQrScanner')) {
  $('stopQrScanner').onclick = stopQrScanner;
}
  }

 

  // ==========================================
  // EVENTS
  // ==========================================

  async function loadEvents() {
    try {
      const events = await request('/api/events/');
      const host = $('events');
      if (!host) return;

      host.replaceChildren();

      const visible = currentUser.role === 'attendee'
        ? events.filter(e => e.status === 'published')
        : events;

      if (!visible.length) {
        host.textContent = 'No events found.';
        return;
      }

      visible.forEach(event => {
        const card = document.createElement('article');
        card.className = 'card';

        const heading = document.createElement('h3');
        heading.textContent = `${event.title} (#${event.id})`;

        const info = document.createElement('p');
        info.textContent =
          `${event.category} · Venue #${event.venue_id} · ${event.status} · ${new Date(event.start_time).toLocaleString()}`;

        const description = document.createElement('p');
        description.textContent = event.description || '';

        card.append(heading, info, description);

        if (
          currentUser.role === 'attendee' &&
          event.status === 'published'
        ) {
          card.append(
            button('Book tickets', () => bookEvent(event.id))
          );
        }

        if (
          currentUser.role === 'admin' &&
          event.status === 'draft'
        ) {
          card.append(actionGroup([
            {
              label: 'Edit draft',
              run: () => editEvent(event)
            },
            {
              label: 'Publish (VenueAgent)',
              run: () => publishEvent(event.id)
            }
          ]));
        }

        if (
          currentUser.role === 'admin' &&
          event.status !== 'cancelled'
        ) {
          card.append(
            button(
              'Cancel event + refunds',
              () => cancelEvent(event.id),
              'red'
            )
          );
        }

        host.append(card);
      });

    } catch (error) {
      displayError('events', error);
    }
  }

  // ==========================================
  // BOOK EVENT
  // ==========================================

  async function bookEvent(eventId) {
    try {
      const details = await request(`/api/events/${eventId}`);
      const categories = details.ticket_categories || [];

      if (!categories.length) {
        throw new Error('This event has no ticket categories.');
      }

      const choices = categories.map(c =>
        `${c.id}: ${c.name} — Rs. ${c.price} — available ${Math.max(0, c.quantity - c.sold_quantity)}`
      ).join('\n');

      const categoryInput = await showAppPrompt(
        `Choose ticket category ID:\n${choices}`,
        String(categories[0].id)
      );

      if (categoryInput === null) return;

      const categoryId = Number(categoryInput);
      const category = categories.find(c => c.id === categoryId);

      if (!category) {
        throw new Error('Invalid ticket category ID.');
      }

      const available = category.quantity - category.sold_quantity;

      const quantityInput = await showAppPrompt(
        `Enter ticket quantity (1–6).\nAvailable tickets: ${available}`,
        '1'
      );

      if (quantityInput === null) return;

      const quantity = Number(quantityInput);

      if (
        !Number.isInteger(quantity) ||
        quantity < 1 ||
        quantity > 6
      ) {
        throw new Error('Quantity must be between 1 and 6.');
      }

      if (quantity > available) {
        throw new Error(`Only ${available} tickets are currently available.`);
      }

      const result = await post('/api/bookings/', {
        event_id: eventId,
        ticket_category_id: categoryId,
        quantity
      });

      agentResult('BookingAgent and TicketAgent response', result);

      alert(
        `Booking successful. Booking ID: ${result.booking?.id ?? result.booking_id ?? '—'}`
      );

      await Promise.all([
        loadBookings(),
        loadTickets(),
        loadNotifications()
      ]);

    } catch (error) {
      alert(error.message);
    }
  }

  // ==========================================
  // PUBLISH EVENT
  // ==========================================

  async function publishEvent(id) {
    const confirmed = await showAppConfirm(
      'VenueAgent will check the venue availability and turnaround buffer before publishing this event.',
      {
        title: 'Publish event?',
        confirmText: 'Check availability'
      }
    );

    if (!confirmed) return;

    try {
      const result = await post(`/api/events/${id}/publish`, {});

      agentResult('VenueAgent event approval', result);

      alert('Event published successfully.');

      await Promise.all([
        loadEvents(),
        loadAgentData()
      ]);

    } catch (error) {
      agentResult('VenueAgent decision', {
        error: error.message
      });

      alert(error.message);

      await loadAgentData();
    }
  }

  // ==========================================
  // EDIT EVENT
  // ==========================================

  async function editEvent(event) {
    try {
      const title = await showAppPrompt(
        'Event title',
        event.title
      );

      if (title === null) return;

      const category = await showAppPrompt(
        'Event category',
        event.category
      );

      if (category === null) return;

      const description = await showAppPrompt(
        'Event description',
        event.description || ''
      );

      if (description === null) return;

      const result = await put(`/api/events/${event.id}`, {
        title,
        category,
        description
      });

      agentResult('Draft event updated', result);

      alert('Draft event updated successfully.');

      await loadEvents();

    } catch (error) {
      alert(error.message);
    }
  }

  // ==========================================
  // CREATE EVENT
  // ==========================================

  async function createEvent(event) {
    event.preventDefault();

    try {
      const d = formValues(event.target);

      const payload = {
        title: d.title.trim(),
        category: d.category.trim(),
        venue_id: Number(d.venue_id),
        start_time: toIso(d.start_time),
        end_time: toIso(d.end_time),
        description: d.description || '',
        status: 'draft',
        ticket_categories: [{
          name: d.ticket_name.trim(),
          price: Number(d.ticket_price),
          quantity: Number(d.ticket_quantity)
        }]
      };

      const result = await post('/api/events/', payload);

      agentResult('Event created as draft', result);

      event.target.reset();

      await loadEvents();

      alert(
        'Draft created successfully. Select Publish to request VenueAgent approval.'
      );

    } catch (error) {
      alert(error.message);
    }
  }


  async function loadVenues() {
    try {
      const venues = await request('/api/venues/');

      renderTable(
        'venues',
        ['ID', 'Venue', 'Location', 'Capacity', 'Hourly rate', 'Private hire', 'Actions'],
        venues.map(v => [
          v.id,
          v.name,
          v.location,
          v.capacity,
          v.hourly_hire_rate,
          v.open_for_private_hire ? 'Yes' : 'No',
          currentUser.role === 'admin'
            ? button('Edit', () => editVenue(v))
            : '—'
        ])
      );

      ['eventVenue', 'hireVenue'].forEach(id => {
        const select = $(id);
        if (!select) return;

        select.replaceChildren(new Option('Select venue', ''));

        venues.forEach(v => {
          select.add(
            new Option(`${v.name} — ${v.location}`, v.id)
          );
        });
      });

    } catch (error) {
      displayError('venues', error);
    }
  }

  async function createVenue(event) {
    event.preventDefault();

    try {
      const d = formValues(event.target);

      const payload = {
        name: d.name.trim(),
        location: d.location.trim(),
        capacity: Number(d.capacity),
        description: d.description || null,
        image: d.image || null,
        hourly_hire_rate: Number(d.hourly_hire_rate),
        open_for_private_hire:
          event.target.elements.open_for_private_hire.checked
      };

      const result = await post('/api/venues/', payload);

      agentResult('Venue created', result);
      event.target.reset();
      await loadVenues();

      alert('Venue created.');

    } catch (error) {
      alert(error.message);
    }
  }

  async function editVenue(venue) {
    try {
      const name = await showAppPrompt('Venue name', venue.name);
      if (name === null) return;

      const location = await showAppPrompt('Venue location', venue.location);
      if (location === null) return;

      const capacityAnswer = await showAppPrompt('Venue capacity', String(venue.capacity));
      if (capacityAnswer === null) return;
      const capacity = Number(capacityAnswer);

      if (!capacity) return;

      const rateAnswer = await showAppPrompt('Hourly hire rate', String(venue.hourly_hire_rate));
      if (rateAnswer === null) return;
      const rate = Number(rateAnswer);

      const result = await put(`/api/venues/${venue.id}`, {
        name,
        location,
        capacity,
        hourly_hire_rate: rate
      });

      agentResult('Venue updated', result);
      await loadVenues();

    } catch (error) {
      alert(error.message);
    }
  }

  /* BOOKINGS */

  async function loadBookings() {
    try {
      const data = await request('/api/bookings/my-bookings');

      renderTable(
        'bookings',
        ['Booking', 'Event', 'Category', 'Qty', 'Total', 'Status', 'Action'],
        (data.bookings || []).map(b => [
          b.booking_id,
          b.event_id,
          b.ticket_category_id,
          b.quantity,
          `Rs. ${b.total_amount}`,
          b.status,
          b.status === 'confirmed'
            ? button(
                'Cancel booking',
                () => cancelBooking(b.booking_id),
                'red'
              )
            : '—'
        ])
      );

    } catch (error) {
      displayError('bookings', error);
    }
  }

  async function cancelBooking(id) {
    if (!await showAppConfirm(
      'Are you sure you want to cancel this booking? The system will calculate the applicable refund.',
      { title: 'Cancel booking', confirmText: 'Yes, cancel booking', danger: true }
    )) return;

    try {
      const result = await post(
        `/api/cancellations/booking/${id}`,
        {}
      );

      agentResult(
        'Booking cancellation and WaitlistAgent response',
        result
      );

      await Promise.all([
        loadBookings(),
        loadTickets(),
        loadWaitlist()
      ]);

    } catch (error) {
      alert(error.message);
    }
  }

  async function cancelEvent(id) {
    if (!await showAppConfirm(
      'Cancel this event? The system will process refunds for confirmed bookings.',
      { title: 'Cancel event', confirmText: 'Yes, cancel event', danger: true }
    )) return;

    try {
      const result = await post(
        `/api/cancellations/event/${id}`,
        {}
      );

      agentResult('Event cancellation and refunds', result);
      await loadEvents();

    } catch (error) {
      alert(error.message);
    }
  }

  /* TICKETS */

  async function loadTickets() {
    try {
      const data = await request('/api/bookings/my-tickets');

      const rows = (data.tickets || []).map(ticket => {
        const image = document.createElement('img');

        image.src = ticket.qr_code;
        image.alt = 'Ticket QR code';
        image.width = 100;
        image.loading = 'lazy';

        return [
          ticket.ticket_id,
          ticket.booking_id,
          ticket.event_id,
          ticket.ticket_code,
          ticket.status,
          ticket.checked_in ? 'Yes' : 'No',
          image
        ];
      });

      renderTable(
        'tickets',
        ['Ticket', 'Booking', 'Event', 'Ticket code', 'Status', 'Checked in', 'QR code'],
        rows
      );

    } catch (error) {
      displayError('tickets', error);
    }
  }

  /* WAITLIST */

  async function joinWaitlist(event) {
    event.preventDefault();

    try {
      const d = formValues(event.target);

      const result = await post(
        `/api/waitlist/join?event_id=${Number(d.event_id)}&ticket_category_id=${Number(d.ticket_category_id)}`,
        {}
      );

      agentResult('Waitlist join result', result);
      event.target.reset();

      await loadWaitlist();

      alert(result.message || 'Waitlist request submitted.');

    } catch (error) {
      alert(error.message);
    }
  }

  async function loadWaitlist() {
    try {
      const entries = await request('/api/waitlist/my-entries');

      renderTable(
        'waitlist',
        ['ID', 'Event', 'Ticket category', 'Status', 'Offer expires', 'Actions'],
        (Array.isArray(entries) ? entries : []).map(entry => {
          let actions = '—';

          if (entry.status === 'offered') {
            actions = actionGroup([
              {
                label: 'Accept offer',
                run: async () => {
                  try {
                    const result = await post(
                      `/api/waitlist/${entry.id}/accept`,
                      {}
                    );

                    agentResult(
                      'WaitlistAgent offer accepted and TicketAgent response',
                      result
                    );

                    await Promise.all([
                      loadWaitlist(),
                      loadBookings(),
                      loadTickets()
                    ]);

                  } catch (e) {
                    alert(e.message);
                  }
                }
              },
              {
                label: 'Decline',
                className: 'gray',
                run: async () => {
                  try {
                    const result = await post(
                      `/api/waitlist/${entry.id}/decline`,
                      {}
                    );

                    agentResult(
                      'WaitlistAgent offer declined',
                      result
                    );

                    await loadWaitlist();

                  } catch (e) {
                    alert(e.message);
                  }
                }
              }
            ]);
          }

          return [
            entry.id,
            entry.event_id,
            entry.ticket_category_id,
            entry.status,
            entry.hold_expires_at,
            actions
          ];
        })
      );

    } catch (error) {
      displayError('waitlist', error);
    }
  }

  /* PRIVATE VENUE HIRE */

  async function createHire(event) {
    event.preventDefault();

    try {
      const d = formValues(event.target);

      const payload = {
        venue_id: Number(d.venue_id),
        start_time: toIso(d.start_time),
        end_time: toIso(d.end_time),
        purpose: d.purpose.trim(),
        guest_count: Number(d.guest_count)
      };

      const result = await post(
        '/api/venue-hire/requests',
        payload
      );

      show('hireResult', result);

      agentResult(
        'VenueAgent private-hire decision',
        result
      );

      event.target.reset();
      await loadMyHire();

    } catch (error) {
      show('hireResult', error.message);
    }
  }

  async function loadMyHire() {
    try {
      const data = await request('/api/venue-hire/my-requests');

      renderTable(
        'myhire',
        ['Request', 'Venue', 'Start', 'End', 'Purpose', 'Guests', 'Quoted price', 'Status'],
        (data.requests || []).map(r => [
          r.id,
          r.venue_id,
          r.start_time,
          r.end_time,
          r.purpose,
          r.guest_count,
          `Rs. ${r.quoted_price}`,
          r.status
        ])
      );

    } catch (error) {
      displayError('myhire', error);
    }
  }

  async function loadPendingHire() {
    try {
      const data = await request(
        '/api/venue-hire/admin/pending'
      );

      renderTable(
        'pendingHire',
        ['Request', 'User', 'Venue', 'Start', 'End', 'Purpose', 'Guests', 'Price', 'Decision'],
        (data.requests || []).map(r => [
          r.id,
          r.user_id,
          r.venue_id,
          r.start_time,
          r.end_time,
          r.purpose,
          r.guest_count,
          `Rs. ${r.quoted_price}`,
          actionGroup([
            {
              label: 'Approve',
              run: () => decideHire(r.id, 'approved')
            },
            {
              label: 'Reject',
              className: 'red',
              run: () => decideHire(r.id, 'rejected')
            }
          ])
        ])
      );

    } catch (error) {
      displayError('pendingHire', error);
    }
  }

  async function decideHire(id, decision) {
    try {
      const result = await post(
        `/api/venue-hire/admin/${id}/decision`,
        {
          decision,
          admin_note: 'Decision made in EventSphere dashboard'
        }
      );

      agentResult('Admin venue-hire decision', result);
      await loadPendingHire();

    } catch (error) {
      alert(error.message);
    }
  }


  async function loadEventsForCheckin() {
    try {
      const events = await request('/api/events/');
      const select = $('checkinEvent');

      if (select) {
        select.replaceChildren(
          new Option('Select event', '')
        );

        events
          .filter(e => e.status === 'published')
          .forEach(e => {
            select.add(
              new Option(`${e.title} (#${e.id})`, e.id)
            );
          });
      }

    } catch (error) {
      displayError('checkinResult', error);
    }
  }

  
function displayCheckinResult(result) {
    const container = $('checkinResult');
    if (!container) return;

    const accepted = result?.decision === 'AGREE';
    const reason = result?.details?.reason ||
        result?.details?.message ||
        'The ticket could not be accepted.';

    container.replaceChildren();
    container.className = `out checkin-result ${accepted ? 'success' : 'error'}`;

    const icon = document.createElement('div');
    icon.className = 'checkin-result-icon';
    icon.textContent = accepted ? '✓' : '×';
    icon.setAttribute('aria-hidden', 'true');

    const status = document.createElement('span');
    status.className = 'checkin-result-status';
    status.textContent = accepted ? 'ADMITTED' : 'REFUSED';

    const title = document.createElement('h3');
    title.textContent = accepted
        ? 'Attendee Successfully Admitted'
        : 'Admission Not Allowed';

    const message = document.createElement('p');
    message.className = 'checkin-result-message';
    message.textContent = accepted
        ? 'The ticket has been verified successfully. The attendee may enter the event.'
        : reason;

    const note = document.createElement('p');
    note.className = 'checkin-result-note';
    note.textContent = accepted
        ? 'This ticket has been checked in successfully.'
        : 'Please check the ticket and event check-in time.';

    const reference = document.createElement('small');
    reference.textContent = `Reference ID: ${result?.conversation_id || 'N/A'}`;

    container.append(icon, status, title, message, note, reference);
}

function displayCheckinError(message) {
    displayCheckinResult({
        decision: 'REFUSE',
        details: { reason: String(message || 'Unable to process the check-in request.') }
    });
}

/* QR CAMERA SCANNER */

let qrScanner = null;
let qrScanProcessing = false;


// Send scanned ticket code to CheckinAgent
async function submitScannedTicket(ticketCode) {

    const eventId = $('checkinEvent').value;

    if (!eventId) {
        displayCheckinError('Please select an event first.');
        return;
    }

    try {

        $('checkinTicketCode').value = ticketCode;

        const result = await post('/api/checkin/scan', {
            event_id: Number(eventId),
            ticket_code: ticketCode.trim()
        });

        displayCheckinResult(result);

        agentResult('CheckinAgent QR admission decision', result);

    } catch (error) {

        displayCheckinError(error.message);

    }
}


// Start camera
async function startQrScanner() {

    if (qrScanner) {
        return;
    }

    if (typeof Html5Qrcode === 'undefined') {
        show('checkinResult', 'QR scanner library could not load. Check your internet connection.');
        return;
    }

    try {

        qrScanner = new Html5Qrcode('qr-reader');

        await qrScanner.start(
            { facingMode: 'environment' },
            {
                fps: 10,
                qrbox: { width: 250, height: 250 }
            },

            async (decodedText) => {

                if (qrScanProcessing) return;

                qrScanProcessing = true;

                try {

                    // QR code contains the unique ticket code
                    await stopQrScanner();

                    await submitScannedTicket(decodedText.trim());

                } finally {

                    qrScanProcessing = false;

                }

            },

            () => {}

        );

        show('checkinResult', 'Camera started. Point it at the ticket QR code.');

    } catch (error) {

        qrScanner = null;

        show(
            'checkinResult',
            'Unable to access camera. Allow camera permission and try again. ' + error
        );

    }
}


// Stop camera
async function stopQrScanner() {

    if (qrScanner) {

        try {

            if (qrScanner.isScanning) {
                await qrScanner.stop();
            }

            await qrScanner.clear();

        } catch (error) {

            console.error('Scanner stop error:', error);

        }

        qrScanner = null;
    }
}


// Manual ticket-code submission
async function checkin(event) {

    event.preventDefault();

    const ticketCode = $('checkinTicketCode').value.trim();

    await submitScannedTicket(ticketCode);
}


  /* STATISTICS */

  function formatStatLabel(key) {
    return key
      .replaceAll('_', ' ')
      .replace(/\b\w/g, letter => letter.toUpperCase());
  }

  function renderCapacityEntries(value) {
    if (Array.isArray(value)) {
      return value;
    }

    if (value && typeof value === 'object') {
      return Object.entries(value).map(([name, details]) => {
        if (details && typeof details === 'object') {
          return {
            event_name: name,
            ...details
          };
        }

        return {
          event_name: name,
          details
        };
      });
    }

    if (typeof value !== 'string') {
      return [];
    }

    const entries = [];
    const pattern =
      /([^:\n]+?):\s*(\d+)\s*tickets?\s*sold\s*\/\s*(\d+)\s*venue capacity/gi;

    let match;

    while ((match = pattern.exec(value)) !== null) {
      entries.push({
        event_name: match[1].trim(),
        tickets_sold: Number(match[2]),
        venue_capacity: Number(match[3])
      });
    }

    if (!entries.length) {
      return value
        .split(/\n+/)
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
          const parts = line.split(':');

          return {
            event_name: parts.shift()?.trim() || 'Event',
            details: parts.join(':').trim()
          };
        });
    }

    return entries;
  }

  function createCapacityRow(entry, index) {
    const card = document.createElement('article');
    card.className = 'stat-list-row';

    const title = document.createElement('div');
    title.className = 'stat-event-name';

    const detail = document.createElement('div');
    detail.className = 'stat-event-detail';

    let sold = 0;
    let capacity = 0;

    if (typeof entry === 'string') {
      const match = entry.match(
        /^(.*?):\s*(\d+)\s*tickets?\s*sold\s*\/\s*(\d+)\s*venue capacity/i
      );

      if (match) {
        title.textContent = match[1].trim();
        sold = Number(match[2]);
        capacity = Number(match[3]);
      } else {
        const parts = entry.split(':');
        title.textContent =
          parts.shift()?.trim() || `Event ${index + 1}`;
        detail.textContent = parts.join(':').trim();
      }

    } else {
      title.textContent =
        entry.event_name ||
        entry.event ||
        entry.title ||
        entry.name ||
        `Event ${entry.event_id || index + 1}`;

      sold = Number(
        entry.tickets_sold ??
        entry.sold_tickets ??
        entry.ticket_sold ??
        entry.sold ??
        0
      );

      capacity = Number(
        entry.venue_capacity ??
        entry.capacity ??
        entry.total_capacity ??
        0
      );

      if (!Number.isFinite(sold)) sold = 0;
      if (!Number.isFinite(capacity)) capacity = 0;

      if (!capacity && entry.details !== undefined) {
        detail.textContent = String(entry.details);
      }
    }

    card.append(title);

    if (capacity > 0) {
      sold = Math.max(0, sold);

      const percentage = Math.min(
        100,
        (sold / capacity) * 100
      );

      const values = document.createElement('div');
      values.className = 'capacity-values';

      const soldText = document.createElement('span');
      soldText.textContent = `${sold} tickets sold`;

      const totalText = document.createElement('strong');
      totalText.textContent = `${capacity} venue capacity`;

      values.append(soldText, totalText);

      const track = document.createElement('div');
      track.className = 'capacity-track';

      const fill = document.createElement('div');
      fill.className = 'capacity-fill';
      fill.style.width = `${percentage}%`;

      if (percentage >= 100) {
        fill.classList.add('is-full');
      }

      track.append(fill);

      const remaining = document.createElement('div');
      remaining.className = 'stat-event-detail';
      remaining.textContent =
        `${Math.max(0, capacity - sold)} places remaining`;

      card.append(values, track, remaining);

    } else if (detail.textContent) {
      card.append(detail);
    } else {
      detail.textContent = 'Capacity information unavailable.';
      card.append(detail);
    }

    return card;
  }


  async function loadStats() {
    try {
      const data = await request(
        '/api/admin/dashboard/stats'
      );

      const host = $('stats');
      if (!host) return;

      host.replaceChildren();

      const entries = Object.entries(data || {});

      const capacityEntries = entries.filter(([key]) =>
        /capacity..*event|event..*capacity|per.?event/i.test(key)
      );

      const countEntries = entries.filter(([key, value]) =>
        !/capacity..*event|event..*capacity|per.?event/i.test(key) &&
        (
          typeof value === 'number' ||
          (
            typeof value === 'string' &&
            value.trim() !== '' &&
            Number.isFinite(Number(value))
          )
        )
      );

      /* Count cards */

      const grid = document.createElement('div');
      grid.className = 'statistics-grid';

      countEntries.forEach(([key, value]) => {
        const card = document.createElement('article');
        card.className = 'statistics-count-card';

        const icon = document.createElement('div');
        icon.className = 'statistics-count-icon';

        icon.textContent =
          /revenue|income|amount/i.test(key) ? '💰' :
          /ticket|booking/i.test(key) ? '🎟️' :
          /check.?in/i.test(key) ? '✓' :
          /venue/i.test(key) ? '🏛️' :
          /event/i.test(key) ? '📅' : '📊';

        const label = document.createElement('div');
        label.className = 'statistics-count-label';
        label.textContent = formatStatLabel(key);

        const number = document.createElement('div');
        number.className = 'statistics-count-number';

        number.textContent = Number(value).toLocaleString();

        card.append(icon, label, number);
        grid.append(card);
      });

      if (countEntries.length) {
        host.append(grid);
      }

      /* Capacity cards */

      capacityEntries.forEach(([key, value]) => {
        const section = document.createElement('section');
        section.className = 'capacity-section';

        const heading = document.createElement('h3');
        heading.className = 'capacity-heading';
        heading.textContent = formatStatLabel(key);

        const list = document.createElement('div');
        list.className = 'stat-list';

        const events = renderCapacityEntries(value);

        if (!events.length) {
          const empty = document.createElement('p');
          empty.className = 'stat-empty';
          empty.textContent =
            'No event capacity data available.';

          list.append(empty);
        } else {
          events.forEach((entry, index) => {
            list.append(
              createCapacityRow(entry, index)
            );
          });
        }

        section.append(heading, list);
        host.append(section);
      });

      if (!countEntries.length && !capacityEntries.length) {
        host.textContent = 'No statistics available.';
      }

    } catch (error) {
      displayError('stats', error);
    }
  }

  /* AGENT MESSAGE HISTORY */

  function jsonContentCell(value) {
    const pre = document.createElement('pre');
    pre.className = 'agent-json';

    try {
      const parsed = typeof value === 'string'
        ? JSON.parse(value)
        : value;

      pre.textContent = JSON.stringify(
        parsed ?? {},
        null,
        2
      );

    } catch {
      pre.textContent = String(value ?? '—');
    }

    return pre;
  }

  async function loadAgentMessages() {
    try {
      const data = await request(
        '/api/admin/agent-messages?limit=200'
      );

      const messages = (data.messages || [])
        .slice()
        .sort((a, b) => Number(b.id || 0) - Number(a.id || 0));

      const rows = messages.map(m => [
        m.id,
        m.sender,
        m.receiver,
        m.performative,
        m.conversation_id,
        m.created_at
      ]);

      renderTable(
        'agentMessages',
        [
          'ID',
          'Sender',
          'Receiver',
          'Performative',
          'Conversation ID',
          'Created'
        ],
        rows
      );

    } catch (error) {
      displayError('agentMessages', error);
    }
  }

  /* AGENT ACTIVITY */

  function formatAgentDateTime(value) {
    if (!value) return 'Not available';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  }

  async function loadAgentStates() {
    try {
      const data = await request('/api/admin/agent-states');

      const host = $('agentStates');
      if (!host) return;

      host.replaceChildren();

      const states = data.states || [];

      if (!states.length) {
        host.textContent = 'No agent states found.';
        return;
      }

      const grid = document.createElement('div');
      grid.className = 'agent-state-grid';

      states.forEach(state => {
        const card = document.createElement('article');
        card.className = 'agent-state-card';

        const header = document.createElement('div');
        header.className = 'agent-state-header';

        const name = document.createElement('h3');
        name.className = 'agent-state-name';
        name.textContent = state.agent_name || 'Agent';

        const badge = document.createElement('span');
        badge.className = 'agent-state-status';
        badge.textContent = 'State saved';

        header.append(name, badge);

        const values = document.createElement('div');
        values.className = 'agent-state-values';

        let stateData = state.state_data;

        if (typeof stateData === 'string') {
          try {
            stateData = JSON.parse(stateData);
          } catch {
            stateData = { details: stateData };
          }
        }

        if (
          stateData &&
          typeof stateData === 'object' &&
          !Array.isArray(stateData)
        ) {
          Object.entries(stateData).forEach(([key, value]) => {
            const item = document.createElement('div');
            item.className = 'agent-state-item';

            const label = document.createElement('span');
            label.className = 'agent-state-label';
            label.textContent = formatStatLabel(key);

            const number = document.createElement('strong');
            number.className = 'agent-state-value';

            const isDateField = /last_expiry_check/i.test(key);

            number.textContent =
              value === null || value === undefined
                ? '—'
                : isDateField
                  ? formatAgentDateTime(value)
                  : typeof value === 'object'
                    ? JSON.stringify(value)
                    : String(value);

            if (isDateField) {
              number.classList.add('agent-state-date');
            }

            item.append(label, number);
            values.append(item);
          });

        } else {
          const item = document.createElement('div');
          item.className = 'agent-state-item';
          item.textContent = String(stateData ?? 'No state data');

          values.append(item);
        }

        const footer = document.createElement('div');
        footer.className = 'agent-state-footer';

        const updated = document.createElement('span');
        updated.textContent =
          `Last updated: ${formatAgentDateTime(state.updated_at)}`;

        footer.append(updated);

        card.append(header, values, footer);
        grid.append(card);
      });

      host.append(grid);

    } catch (error) {
      displayError('agentStates', error);
    }
  }


  /* LOAD ALL AGENT DATA */

  async function loadAgentData() {
    await Promise.all([
      loadAgentMessages(),
      loadAgentStates()
    ]);
  }

  /* NOTIFICATIONS */

  async function loadNotifications() {
    try {
      const data = await request('/api/notifications');

      renderTable(
        'notifications',
        ['ID', 'Title', 'Message', 'Status', 'Created', 'Action'],
        (data.notifications || []).map(n => [
          n.id,
          n.title,
          n.message,
          n.is_read ? 'Read' : 'Unread',
          n.created_at,
          n.is_read
            ? '—'
            : button(
                'Mark as read',
                async () => {
                  try {
                    await post(
                      `/api/notifications/${n.id}/read`,
                      {}
                    );

                    await loadNotifications();

                  } catch (e) {
                    alert(e.message);
                  }
                }
              )
        ])
      );

    } catch (error) {
      displayError('notifications', error);
    }
  }

  /* START APPLICATION */

  document.addEventListener('DOMContentLoaded', init);

})();
