/* EventSphere dashboard frontend. Uses the existing FastAPI routes only. */
(() => {
  'use strict';

  let csrfToken = '';
  let currentUser = null;
  const $ = (id) => document.getElementById(id);
  const jsonHeaders = () => ({ 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken });

  function show(id, value) {
    const el = $(id);
    if (!el) return;
    el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  }
  function displayError(id, error) { show(id, error?.message || String(error)); }
  function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }
  function toIso(value) {
    const date = new Date(value);
    if (!value || Number.isNaN(date.getTime())) throw new Error('Please enter a valid date and time.');
    return date.toISOString();
  }
  function safeText(value) { return value === null || value === undefined || value === '' ? '—' : String(value); }

  async function request(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken;
    const response = await fetch(path, { ...options, method, headers, credentials: 'same-origin' });
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch { data = { detail: raw }; }
    if (!response.ok) {
      let detail = data.detail ?? data.message ?? `Request failed (${response.status})`;
      if (typeof detail !== 'string') detail = JSON.stringify(detail);
      throw new Error(detail);
    }
    return data;
  }
  const post = (path, payload) => request(path, { method: 'POST', body: JSON.stringify(payload) });
  const put = (path, payload) => request(path, { method: 'PUT', body: JSON.stringify(payload) });

  function agentResult(label, result) {
    show('agentResult', `${label}\n${JSON.stringify(result, null, 2)}`);
  }
  function button(label, handler, className = '') {
    const el = document.createElement('button');
    el.type = 'button'; el.className = `btn ${className}`.trim(); el.textContent = label;
    el.addEventListener('click', handler); return el;
  }
  function renderTable(id, headings, rows) {
    const host = $(id); if (!host) return;
    host.replaceChildren();
    if (!rows.length) { host.textContent = 'No records found.'; return; }
    const wrap = document.createElement('div'); wrap.className = 'tablewrap';
    const table = document.createElement('table'); table.className = 'table';
    const thead = document.createElement('thead'); const header = document.createElement('tr');
    headings.forEach(text => { const th = document.createElement('th'); th.textContent = text; header.append(th); });
    thead.append(header); table.append(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(row => { const tr = document.createElement('tr'); row.forEach(value => {
      const td = document.createElement('td');
      if (value instanceof Node) td.append(value); else td.textContent = safeText(value);
      tr.append(td);
    }); tbody.append(tr); });
    table.append(tbody); wrap.append(table); host.append(wrap);
  }
  function actionGroup(actions) { const span = document.createElement('span'); actions.forEach(a => span.append(button(a.label, a.run, a.className || ''))); return span; }

  async function refreshCsrf() {
    const result = await request('/api/auth/csrf');
    csrfToken = result.csrf_token;
    if (!csrfToken) throw new Error('Security token was not returned by the server.');
  }

  function setupNavigation() {
    document.querySelectorAll('[data-tab]').forEach(navButton => {
      navButton.addEventListener('click', async () => {
        document.querySelectorAll('.section').forEach(section => section.classList.remove('active'));
        document.querySelectorAll('[data-tab]').forEach(item => item.classList.remove('active'));
        $(`s-${navButton.dataset.tab}`)?.classList.add('active');
        navButton.classList.add('active');
        await loadTab(navButton.dataset.tab);
      });
    });
  }

  async function loadTab(tab) {
    const loaders = {
      events: loadEvents, venues: loadVenues, bookings: loadBookings, tickets: loadTickets,
      waitlist: loadWaitlist, myhire: loadMyHire, hireadmin: loadPendingHire,
      checkin: loadEventsForCheckin, stats: loadStats, agents: loadAgentData,
      notifications: loadNotifications
    };
    if (loaders[tab]) await loaders[tab]();
  }

  async function init() {
    try {
      await refreshCsrf();
      currentUser = await request('/api/auth/me');
      const accessPath = { admin: '/api/admin/access-check', staff: '/api/staff/access-check', attendee: '/api/attendee/access-check' }[currentUser.role];
      await request(accessPath);
      $('fullname').textContent = currentUser.full_name;
      $('role').textContent = currentUser.role;
      $('statRole').textContent = currentUser.role;
      $('statEmail').textContent = currentUser.email;
      $('title').textContent = `${currentUser.role[0].toUpperCase()}${currentUser.role.slice(1)} Dashboard`;
      const navId = { admin: 'adminNav', staff: 'staffNav', attendee: 'attendeeNav' }[currentUser.role];
      if (!navId) throw new Error('Your account has an unsupported role.');
      $(navId)?.classList.remove('hidden');
      if (currentUser.role === 'admin') $('eventCreateCard')?.classList.remove('hidden');
      setupNavigation(); bindFormsAndButtons();
      await loadVenues();
      await loadEvents();
      if (currentUser.role === 'admin') await Promise.all([loadStats(), loadAgentData(), loadPendingHire()]);
      if (currentUser.role === 'attendee') await Promise.all([loadBookings(), loadTickets(), loadWaitlist(), loadMyHire()]);
      await loadNotifications();
    } catch (error) {
      alert(error.message || 'Please log in to continue.');
      location.href = '/login';
    }
  }

  function bindFormsAndButtons() {
    $('logout').onclick = async () => { try { await post('/api/auth/logout', {}); } finally { location.href = '/login'; } };
    const bindings = {
      loadEvents: loadEvents, loadVenues: loadVenues, loadBookings: loadBookings,
      loadTickets: loadTickets, loadWaitlist: loadWaitlist, loadMyHire: loadMyHire,
      loadPendingHire: loadPendingHire, loadStats: loadStats,
      loadAgentMessages: loadAgentMessages, loadAgentStates: loadAgentStates,
      loadNotifications: loadNotifications
    };
    Object.entries(bindings).forEach(([id, fn]) => { if ($(id)) $(id).onclick = fn; });
    if ($('eventForm')) $('eventForm').onsubmit = createEvent;
    if ($('venueForm')) $('venueForm').onsubmit = createVenue;
    if ($('waitForm')) $('waitForm').onsubmit = joinWaitlist;
    if ($('hireForm')) $('hireForm').onsubmit = createHire;
    if ($('checkinForm')) $('checkinForm').onsubmit = checkin;
  }

  async function loadEvents() {
    try {
      const events = await request('/api/events/');
      const host = $('events'); if (!host) return;
      host.replaceChildren();
      const visible = currentUser.role === 'attendee' ? events.filter(e => e.status === 'published') : events;
      if (!visible.length) { host.textContent = 'No events found.'; return; }
      visible.forEach(event => {
        const card = document.createElement('article'); card.className = 'card';
        const heading = document.createElement('h3'); heading.textContent = `${event.title} (#${event.id})`;
        const info = document.createElement('p'); info.textContent = `${event.category} · Venue #${event.venue_id} · ${event.status} · ${new Date(event.start_time).toLocaleString()}`;
        const description = document.createElement('p'); description.textContent = event.description || '';
        card.append(heading, info, description);
        if (currentUser.role === 'attendee' && event.status === 'published') card.append(button('Book tickets', () => bookEvent(event.id)));
        if (currentUser.role === 'admin' && event.status === 'draft') card.append(actionGroup([
          { label: 'Edit draft', run: () => editEvent(event) },
          { label: 'Publish (VenueAgent)', run: () => publishEvent(event.id) }
        ]));
        if (currentUser.role === 'admin' && event.status !== 'cancelled') card.append(button('Cancel event + refunds', () => cancelEvent(event.id), 'red'));
        host.append(card);
      });
    } catch (error) { displayError('events', error); }
  }

  async function bookEvent(eventId) {
    try {
      const details = await request(`/api/events/${eventId}`);
      const categories = details.ticket_categories || [];
      if (!categories.length) throw new Error('This event has no ticket categories.');
      const choices = categories.map(c => `${c.id}: ${c.name} — Rs. ${c.price} — available ${Math.max(0, c.quantity - c.sold_quantity)}`).join('\n');
      const categoryId = Number(prompt(`Choose ticket category ID:\n${choices}`));
      if (!categoryId) return;
      const category = categories.find(c => c.id === categoryId);
      if (!category) throw new Error('Invalid ticket category ID.');
      const available = category.quantity - category.sold_quantity;
      const quantity = Number(prompt('Quantity (1–6)', '1'));
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > 6) throw new Error('Quantity must be between 1 and 6.');
      if (quantity > available) throw new Error(`Only ${available} tickets are currently available.`);
      const result = await post('/api/bookings/', { event_id: eventId, ticket_category_id: categoryId, quantity });
      agentResult('BookingAgent and TicketAgent response', result);
      alert(`Booking successful. Booking ID: ${result.booking?.id ?? result.booking_id ?? '—'}`);
      await Promise.all([loadBookings(), loadTickets()]);
    } catch (error) { alert(error.message); }
  }

  async function publishEvent(id) {
    try { const result = await post(`/api/events/${id}/publish`, {}); agentResult('VenueAgent event approval', result); alert('Event published successfully.'); await loadEvents(); }
    catch (error) { agentResult('VenueAgent decision', { error: error.message }); alert(error.message); }
  }
  async function editEvent(event) {
    try {
      const title = prompt('Event title', event.title); if (title === null) return;
      const category = prompt('Event category', event.category); if (category === null) return;
      const description = prompt('Event description', event.description || ''); if (description === null) return;
      const result = await put(`/api/events/${event.id}`, { title, category, description });
      agentResult('Draft event updated', result); await loadEvents();
    } catch (error) { alert(error.message); }
  }
  async function createEvent(event) {
    event.preventDefault();
    try {
      const d = formValues(event.target);
      const payload = {
        title: d.title.trim(), category: d.category.trim(), venue_id: Number(d.venue_id),
        start_time: toIso(d.start_time), end_time: toIso(d.end_time), description: d.description || '', status: 'draft',
        ticket_categories: [{ name: d.ticket_name.trim(), price: Number(d.ticket_price), quantity: Number(d.ticket_quantity) }]
      };
      const result = await post('/api/events/', payload);
      agentResult('Event created as draft', result); event.target.reset(); await loadEvents();
      alert('Draft created. Select Publish to request VenueAgent approval.');
    } catch (error) { alert(error.message); }
  }

  async function loadVenues() {
    try {
      const venues = await request('/api/venues/');
      renderTable('venues', ['ID', 'Venue', 'Location', 'Capacity', 'Hourly rate', 'Private hire', 'Actions'], venues.map(v => [
        v.id, v.name, v.location, v.capacity, v.hourly_hire_rate, v.open_for_private_hire ? 'Yes' : 'No',
        currentUser.role === 'admin' ? button('Edit', () => editVenue(v)) : '—'
      ]));
      ['eventVenue', 'hireVenue'].forEach(id => {
        const select = $(id); if (!select) return;
        select.replaceChildren(new Option('Select venue', ''));
        venues.forEach(v => select.add(new Option(`${v.name} — ${v.location}`, v.id)));
      });
    } catch (error) { displayError('venues', error); }
  }
  async function createVenue(event) {
    event.preventDefault();
    try {
      const d = formValues(event.target);
      const payload = { name: d.name.trim(), location: d.location.trim(), capacity: Number(d.capacity), description: d.description || null, image: d.image || null, hourly_hire_rate: Number(d.hourly_hire_rate), open_for_private_hire: event.target.elements.open_for_private_hire.checked };
      const result = await post('/api/venues/', payload);
      agentResult('Venue created', result); event.target.reset(); await loadVenues(); alert('Venue created.');
    } catch (error) { alert(error.message); }
  }
  async function editVenue(venue) {
    try {
      const name = prompt('Venue name', venue.name); if (name === null) return;
      const location = prompt('Location', venue.location); if (location === null) return;
      const capacity = Number(prompt('Capacity', venue.capacity)); if (!capacity) return;
      const rate = Number(prompt('Hourly hire rate', venue.hourly_hire_rate));
      const result = await put(`/api/venues/${venue.id}`, { name, location, capacity, hourly_hire_rate: rate });
      agentResult('Venue updated', result); await loadVenues();
    } catch (error) { alert(error.message); }
  }

  async function loadBookings() {
    try {
      const data = await request('/api/bookings/my-bookings');
      renderTable('bookings', ['Booking', 'Event', 'Category', 'Qty', 'Total', 'Status', 'Action'], (data.bookings || []).map(b => [
        b.booking_id, b.event_id, b.ticket_category_id, b.quantity, `Rs. ${b.total_amount}`, b.status,
        b.status === 'confirmed' ? button('Cancel booking', () => cancelBooking(b.booking_id), 'red') : '—'
      ]));
    } catch (error) { displayError('bookings', error); }
  }
  async function cancelBooking(id) {
    if (!confirm('Cancel this booking? The backend will calculate the applicable refund.')) return;
    try { const result = await post(`/api/cancellations/booking/${id}`, {}); agentResult('Booking cancellation and WaitlistAgent response', result); await Promise.all([loadBookings(), loadTickets(), loadWaitlist()]); }
    catch (error) { alert(error.message); }
  }
  async function cancelEvent(id) {
    if (!confirm('Cancel this event and process refunds for confirmed bookings?')) return;
    try { const result = await post(`/api/cancellations/event/${id}`, {}); agentResult('Event cancellation and refunds', result); await loadEvents(); }
    catch (error) { alert(error.message); }
  }
  async function loadTickets() {
    try {
      const data = await request('/api/bookings/my-tickets');
      const rows = (data.tickets || []).map(ticket => {
        const image = document.createElement('img'); image.src = ticket.qr_code; image.alt = 'Ticket QR code'; image.width = 100; image.loading = 'lazy';
        return [ticket.ticket_id, ticket.booking_id, ticket.event_id, ticket.ticket_code, ticket.status, ticket.checked_in ? 'Yes' : 'No', image];
      });
      renderTable('tickets', ['Ticket', 'Booking', 'Event', 'Ticket code', 'Status', 'Checked in', 'QR code'], rows);
    } catch (error) { displayError('tickets', error); }
  }

  async function joinWaitlist(event) {
    event.preventDefault();
    try {
      const d = formValues(event.target);
      const result = await post(`/api/waitlist/join?event_id=${Number(d.event_id)}&ticket_category_id=${Number(d.ticket_category_id)}`, {});
      agentResult('Waitlist join result', result); event.target.reset(); await loadWaitlist(); alert(result.message || 'Waitlist request submitted.');
    } catch (error) { alert(error.message); }
  }
  async function loadWaitlist() {
    try {
      const entries = await request('/api/waitlist/my-entries');
      renderTable('waitlist', ['ID', 'Event', 'Ticket category', 'Status', 'Offer expires', 'Actions'], (Array.isArray(entries) ? entries : []).map(entry => {
        let actions = '—';
        if (entry.status === 'offered') actions = actionGroup([
          { label: 'Accept offer', run: async () => { try { const result = await post(`/api/waitlist/${entry.id}/accept`, {}); agentResult('WaitlistAgent offer accepted and TicketAgent response', result); await Promise.all([loadWaitlist(), loadBookings(), loadTickets()]); } catch (e) { alert(e.message); } } },
          { label: 'Decline', className: 'gray', run: async () => { try { const result = await post(`/api/waitlist/${entry.id}/decline`, {}); agentResult('WaitlistAgent offer declined', result); await loadWaitlist(); } catch (e) { alert(e.message); } } }
        ]);
        return [entry.id, entry.event_id, entry.ticket_category_id, entry.status, entry.hold_expires_at, actions];
      }));
    } catch (error) { displayError('waitlist', error); }
  }

  async function createHire(event) {
    event.preventDefault();
    try {
      const d = formValues(event.target);
      const payload = { venue_id: Number(d.venue_id), start_time: toIso(d.start_time), end_time: toIso(d.end_time), purpose: d.purpose.trim(), guest_count: Number(d.guest_count) };
      const result = await post('/api/venue-hire/requests', payload);
      show('hireResult', result); agentResult('VenueAgent private-hire decision', result); event.target.reset(); await loadMyHire();
    } catch (error) { show('hireResult', error.message); }
  }
  async function loadMyHire() {
    try {
      const data = await request('/api/venue-hire/my-requests');
      renderTable('myhire', ['Request', 'Venue', 'Start', 'End', 'Purpose', 'Guests', 'Quoted price', 'Status'], (data.requests || []).map(r => [r.id, r.venue_id, r.start_time, r.end_time, r.purpose, r.guest_count, `Rs. ${r.quoted_price}`, r.status]));
    } catch (error) { displayError('myhire', error); }
  }
  async function loadPendingHire() {
    try {
      const data = await request('/api/venue-hire/admin/pending');
      renderTable('pendingHire', ['Request', 'User', 'Venue', 'Start', 'End', 'Purpose', 'Guests', 'Price', 'Decision'], (data.requests || []).map(r => [
        r.id, r.user_id, r.venue_id, r.start_time, r.end_time, r.purpose, r.guest_count, `Rs. ${r.quoted_price}`,
        actionGroup([{ label: 'Approve', run: () => decideHire(r.id, 'approved') }, { label: 'Reject', className: 'red', run: () => decideHire(r.id, 'rejected') }])
      ]));
    } catch (error) { displayError('pendingHire', error); }
  }
  async function decideHire(id, decision) {
    try { const result = await post(`/api/venue-hire/admin/${id}/decision`, { decision, admin_note: 'Decision made in EventSphere dashboard' }); agentResult('Admin venue-hire decision', result); await loadPendingHire(); }
    catch (error) { alert(error.message); }
  }

  async function loadEventsForCheckin() {
    try {
      const events = await request('/api/events/');
      const select = $('checkinEvent');
      if (select) { select.replaceChildren(new Option('Select event', '')); events.filter(e => e.status === 'published').forEach(e => select.add(new Option(`${e.title} (#${e.id})`, e.id))); }
    } catch (error) { displayError('checkinResult', error); }
  }
  async function checkin(event) {
    event.preventDefault();
    try {
      const d = formValues(event.target);
      const result = await post('/api/checkin/scan', { event_id: Number(d.event_id), ticket_code: d.ticket_code.trim() });
      show('checkinResult', result); agentResult('CheckinAgent admission decision', result);
    } catch (error) { show('checkinResult', error.message); agentResult('CheckinAgent response', { decision: 'REQUEST_FAILED', error: error.message }); }
  }

  async function loadStats() {
    try {
      const data = await request('/api/admin/dashboard/stats');
      const host = $('stats'); if (!host) return;
      host.replaceChildren();
      Object.entries(data).forEach(([key, value]) => { const card = document.createElement('div'); card.className = 'card'; const label = document.createElement('strong'); label.textContent = key.replaceAll('_', ' '); const number = document.createElement('div'); number.className = 'stat'; number.textContent = typeof value === 'number' ? value.toLocaleString() : value; card.append(label, number); host.append(card); });
    } catch (error) { displayError('stats', error); }
  }
  async function loadAgentMessages() {
    try { const data = await request('/api/admin/agent-messages?limit=200'); renderTable('agentMessages', ['ID', 'Sender', 'Receiver', 'Performative', 'Content', 'Conversation ID', 'Created'], (data.messages || []).map(m => [m.id, m.sender, m.receiver, m.performative, JSON.stringify(m.content), m.conversation_id, m.created_at])); }
    catch (error) { displayError('agentMessages', error); }
  }
  async function loadAgentStates() {
    try { const data = await request('/api/admin/agent-states'); renderTable('agentStates', ['Agent', 'State', 'Updated'], (data.states || []).map(s => [s.agent_name, JSON.stringify(s.state_data), s.updated_at])); }
    catch (error) { displayError('agentStates', error); }
  }
  async function loadAgentData() { await Promise.all([loadAgentMessages(), loadAgentStates()]); }
  async function loadNotifications() {
    try {
      const data = await request('/api/notifications');
      renderTable('notifications', ['ID', 'Title', 'Message', 'Status', 'Created', 'Action'], (data.notifications || []).map(n => [
        n.id, n.title, n.message, n.is_read ? 'Read' : 'Unread', n.created_at,
        n.is_read ? '—' : button('Mark as read', async () => { try { await post(`/api/notifications/${n.id}/read`, {}); await loadNotifications(); } catch (e) { alert(e.message); } })
      ]));
    } catch (error) { displayError('notifications', error); }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
