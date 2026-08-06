/**
 * novaTech AI — User Profile Page Logic (profile.js)
 */

document.addEventListener('DOMContentLoaded', async () => {
  await Auth.ensureGuestSession();

  let profileData = null;
  let isEditing = false;

  // ── DOM ──────────────────────────────────────────────────────────────────

  const profileAvatar   = document.getElementById('profile-avatar');
  const profileName     = document.getElementById('profile-name');
  const profileEmail    = document.getElementById('profile-email');
  const profilePhone    = document.getElementById('profile-phone');
  const profileAddress  = document.getElementById('profile-address');
  const profileJoined   = document.getElementById('profile-joined');
  const editBtn         = document.getElementById('btn-edit-profile');
  const saveBtn         = document.getElementById('btn-save-profile');
  const cancelBtn       = document.getElementById('btn-cancel-edit');
  const profileForm     = document.getElementById('profile-form');
  const convList        = document.getElementById('recent-convs');
  const orderList       = document.getElementById('recent-orders');
  const profileInitials = document.getElementById('profile-initials');
  const navUserName     = document.getElementById('nav-user-name');
  const navAvatar       = document.getElementById('nav-avatar');
  const logoutBtn       = document.getElementById('btn-logout');

  logoutBtn?.addEventListener('click', () => Auth.logout());

  // ── Load Profile ─────────────────────────────────────────────────────────

  async function loadProfile() {
    try {
      profileData = await API.get('/api/profile');
      renderProfile(profileData);
    } catch (err) {
      Toast.error('Failed to load profile: ' + err.message);
    }
  }

  function renderProfile(data) {
    if (!data) return;

    const initials = getInitials(data.name);

    if (profileAvatar) {
      if (data.avatar_url) {
        profileAvatar.innerHTML = `<img src="${data.avatar_url}" alt="${data.name}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
      } else {
        profileAvatar.textContent = initials;
      }
    }

    if (profileInitials) profileInitials.textContent = initials;
    if (profileName) profileName.textContent = data.name;
    if (profileEmail) profileEmail.textContent = data.email;
    if (profilePhone) profilePhone.textContent = data.phone || '—';
    if (profileAddress) profileAddress.textContent = data.address || '—';
    if (profileJoined) profileJoined.textContent = 'Member since ' + formatDate(data.created_at);

    // Nav bar
    if (navUserName) navUserName.textContent = data.name;
    if (navAvatar) {
      if (data.avatar_url) {
        navAvatar.innerHTML = `<img src="${data.avatar_url}" alt="${data.name}">`;
      } else {
        navAvatar.textContent = initials;
      }
    }

    // Populate form fields
    const editName    = document.getElementById('edit-name');
    const editPhone   = document.getElementById('edit-phone');
    const editAddress = document.getElementById('edit-address');

    if (editName) editName.value = data.name || '';
    if (editPhone) editPhone.value = data.phone || '';
    if (editAddress) editAddress.value = data.address || '';
  }

  // ── Edit Profile ──────────────────────────────────────────────────────────

  editBtn?.addEventListener('click', () => {
    setEditMode(true);
  });

  cancelBtn?.addEventListener('click', () => {
    setEditMode(false);
    renderProfile(profileData); // Reset form
  });

  function setEditMode(editing) {
    isEditing = editing;
    const viewFields = document.querySelectorAll('.profile-view-field');
    const editFields = document.querySelectorAll('.profile-edit-field');

    viewFields.forEach(el => el.classList.toggle('hidden', editing));
    editFields.forEach(el => el.classList.toggle('hidden', !editing));

    editBtn?.classList.toggle('hidden', editing);
    saveBtn?.classList.toggle('hidden', !editing);
    cancelBtn?.classList.toggle('hidden', !editing);
  }

  profileForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const name    = document.getElementById('edit-name')?.value.trim();
    const phone   = document.getElementById('edit-phone')?.value.trim();
    const address = document.getElementById('edit-address')?.value.trim();

    if (!name) {
      Toast.error('Name is required');
      return;
    }

    const origText = saveBtn?.innerHTML;
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner spinner-sm"></span> Saving...';
    }

    try {
      const updated = await API.patch('/api/profile', { name, phone, address });
      profileData = updated;
      Auth.setUser(updated);
      renderProfile(updated);
      setEditMode(false);
      Toast.success('Profile updated successfully! ✓');
    } catch (err) {
      Toast.error('Failed to save profile: ' + err.message);
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = origText;
      }
    }
  });

  // ── Load Recent Conversations ─────────────────────────────────────────────

  async function loadConversations() {
    if (!convList) return;

    try {
      const conversations = await API.get('/api/conversations');

      if (!conversations.length) {
        convList.innerHTML = `
          <div style="text-align:center;padding:2rem;color:var(--text-muted)">
            <div style="font-size:2rem;margin-bottom:0.5rem">💬</div>
            <div>No conversations yet</div>
            <a href="index.html" class="link" style="font-size:0.85rem;margin-top:0.5rem;display:inline-block">Start your first chat →</a>
          </div>`;
        return;
      }

      convList.innerHTML = conversations.slice(0, 5).map(conv => `
        <a href="index.html" class="conv-list-item" onclick="sessionStorage.setItem('load_conv','${conv.id}')">
          <div class="conv-icon">💬</div>
          <div class="conv-info">
            <div class="conv-title">${escapeHTML(conv.title)}</div>
            <div class="conv-meta">${conv.message_count} messages · ${formatRelative(conv.updated_at)}</div>
          </div>
          <div class="conv-arrow">→</div>
        </a>
      `).join('');
    } catch (err) {
      convList.innerHTML = `<div style="color:var(--text-muted);padding:1rem;font-size:0.85rem">Failed to load conversations</div>`;
    }
  }

  // ── Load Recent Orders ────────────────────────────────────────────────────

  async function loadOrders() {
    if (!orderList) return;

    try {
      const orders = await API.get('/api/mock/orders');

      if (!orders.length) {
        orderList.innerHTML = `
          <div style="text-align:center;padding:2rem;color:var(--text-muted)">
            <div style="font-size:2rem;margin-bottom:0.5rem">📦</div>
            <div>No orders found</div>
          </div>`;
        return;
      }

      const statusColors = {
        delivered: '#10b981', in_transit: '#6C63FF', processing: '#f59e0b',
        cancelled: '#ef4444', pending: '#94a3b8',
      };

      const statusLabels = {
        delivered: '✓ Delivered', in_transit: '🚚 In Transit',
        processing: '⏳ Processing', cancelled: '✕ Cancelled', pending: '⏳ Pending',
      };

      orderList.innerHTML = orders.slice(0, 3).map(order => `
        <div class="order-list-item">
          <div class="order-info">
            <div class="order-id">${order.id}</div>
            <div class="order-items">${order.items.map(i => i.product).join(', ')}</div>
            <div class="order-date">${formatDate(order.created_at)}</div>
          </div>
          <div class="order-right">
            <div class="order-amount">₹${order.total_amount.toLocaleString('en-IN')}</div>
            <div class="order-status" style="color:${statusColors[order.status] || '#94a3b8'}">
              ${statusLabels[order.status] || order.status}
            </div>
          </div>
        </div>
      `).join('');
    } catch {
      orderList.innerHTML = `<div style="color:var(--text-muted);padding:1rem;font-size:0.85rem">Sign in to view orders</div>`;
    }
  }

  function escapeHTML(str) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  await loadProfile();
  await loadConversations();
  await loadOrders();
});
