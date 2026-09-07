/**
 * Nizhal Community Bank-Level Multi-Tab Session Synchronization & Inactivity Manager
 * 
 * Features:
 * 1. Real-time Cross-Tab Sync via BroadcastChannel & LocalStorage.
 * 2. Instant Cross-Tab Login (Redirects other open login tabs).
 * 3. Instant Cross-Tab Logout (Terminates all open dashboard tabs immediately).
 * 4. Shared Idle Activity Timer across all tabs.
 * 5. 60-Second Inactivity Warning Modal with Live Countdown.
 * 6. Periodic Backend Heartbeat Ping & Anti-Stale Session Protection.
 */

(function () {
    const CHANNEL_NAME = 'nizhal_bank_auth_sync';
    const IDLE_TIMEOUT_MS = 30 * 60 * 1000;      // 30 minutes
    const WARNING_TIME_MS = 60 * 1000;           // Show warning 60 seconds before
    const PING_INTERVAL_MS = 60 * 1000;          // Heartbeat ping every 60s

    let broadcastChannel = null;
    if (typeof BroadcastChannel !== 'undefined') {
        try {
            broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
        } catch (e) {
            console.warn('BroadcastChannel not supported or restricted, using storage fallback.');
        }
    }

    // Broadcast event to other tabs
    function broadcast(type, payload = {}) {
        const msg = { type, payload, timestamp: Date.now() };
        if (broadcastChannel) {
            broadcastChannel.postMessage(msg);
        }
        try {
            localStorage.setItem('nizhal_session_event', JSON.stringify(msg));
        } catch (e) {}
    }

    // Handle events received from other tabs
    function handleSyncMessage(eventData) {
        if (!eventData || !eventData.type) return;

        const { type, payload } = eventData;
        const currentPath = window.location.pathname;
        const isLoginPage = currentPath.includes('/login');

        switch (type) {
            case 'SESSION_LOGOUT':
                // Another tab logged out! Terminate this tab immediately
                if (!isLoginPage) {
                    showSessionTerminatedOverlay('You have signed out from another tab.');
                    setTimeout(() => {
                        window.location.replace('/login/?reason=cross_tab_logout');
                    }, 400);
                }
                break;

            case 'SESSION_LOGIN':
                // Another tab logged in! If we are on login page, redirect to dashboard
                if (isLoginPage) {
                    window.location.replace('/dashboard/');
                }
                break;

            case 'USER_ACTIVITY':
                // Reset local idle timer based on other tab's activity
                resetIdleTimer(false);
                break;
        }
    }

    // Listen on BroadcastChannel
    if (broadcastChannel) {
        broadcastChannel.onmessage = (event) => {
            handleSyncMessage(event.data);
        };
    }

    // Listen on LocalStorage storage event (fallback & cross-window sync)
    window.addEventListener('storage', (e) => {
        if (e.key === 'nizhal_session_event' && e.newValue) {
            try {
                const data = JSON.parse(e.newValue);
                handleSyncMessage(data);
            } catch (err) {}
        }
    });

    // Notify other tabs on specific pages
    window.NizhalAuthSync = {
        notifyLogin: function (username) {
            broadcast('SESSION_LOGIN', { username: username || 'User' });
        },
        notifyLogout: function () {
            broadcast('SESSION_LOGOUT', {});
        },
        keepAlive: function () {
            return pingServer();
        }
    };

    // --- Dashboard Inactivity & Heartbeat Management ---
    const isDashboard = window.location.pathname.startsWith('/dashboard/');
    if (!isDashboard) {
        return; // Only run active idle monitoring on dashboard/authenticated pages
    }

    let lastActiveTime = Date.now();
    let warningTimerId = null;
    let logoutTimerId = null;
    let countdownIntervalId = null;
    let warningModalEl = null;

    function recordActivity() {
        lastActiveTime = Date.now();
        try {
            localStorage.setItem('nizhal_last_active', String(lastActiveTime));
        } catch (e) {}
        broadcast('USER_ACTIVITY', {});
        resetIdleTimer(false);
    }

    // Throttled event listener for activity
    let throttleTimeout = null;
    function onUserInteraction() {
        if (!throttleTimeout) {
            recordActivity();
            throttleTimeout = setTimeout(() => {
                throttleTimeout = null;
            }, 3000);
        }
    }

    ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'].forEach(evt => {
        window.addEventListener(evt, onUserInteraction, { passive: true });
    });

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            recordActivity();
            pingServer();
        }
    });

    window.addEventListener('focus', () => {
        recordActivity();
    });

    // Create Bank-Grade Inactivity Warning Modal
    function createWarningModal() {
        if (document.getElementById('nizhalInactivityModal')) return;

        const modal = document.createElement('div');
        modal.id = 'nizhalInactivityModal';
        modal.className = 'fixed inset-0 z-50 hidden items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs transition-opacity duration-200';
        modal.innerHTML = `
            <div class="relative w-full max-w-md bg-white border border-slate-300 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                <div class="h-1.5 bg-gradient-to-r from-amber-500 via-rose-500 to-amber-500"></div>
                <div class="p-6">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-none bg-amber-100 border border-amber-300 text-amber-700 flex items-center justify-center shrink-0">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                        </div>
                        <div>
                            <h3 class="font-display font-bold text-base text-slate-900">Session Timeout Warning</h3>
                            <p class="text-xs text-slate-500">Bank-Level Security Inactivity Protocol</p>
                        </div>
                    </div>
                    
                    <p class="text-xs sm:text-sm text-slate-700 leading-relaxed mb-4">
                        You have been inactive. For your security, your session will automatically terminate in:
                    </p>

                    <div class="bg-slate-50 border border-slate-200 p-3 text-center mb-5">
                        <span id="inactivityCountdown" class="font-mono font-bold text-2xl text-rose-600">60</span>
                        <span class="text-xs font-semibold text-slate-500 ml-1">seconds</span>
                    </div>

                    <div class="flex items-center justify-end gap-2.5">
                        <button type="button" onclick="window.location.href='/logout/'" class="px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-100 text-xs font-semibold transition cursor-pointer">
                            Log Out Now
                        </button>
                        <button type="button" id="staySignedInBtn" onclick="window.staySignedIn()" class="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition shadow-sm cursor-pointer">
                            Stay Signed In
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        warningModalEl = modal;
    }

    function showWarningModal() {
        createWarningModal();
        if (!warningModalEl) return;
        warningModalEl.classList.remove('hidden');
        warningModalEl.classList.add('flex');

        let secondsRemaining = 60;
        const countdownDisplay = document.getElementById('inactivityCountdown');
        if (countdownDisplay) countdownDisplay.innerText = secondsRemaining;

        if (countdownIntervalId) clearInterval(countdownIntervalId);
        countdownIntervalId = setInterval(() => {
            secondsRemaining -= 1;
            if (countdownDisplay) countdownDisplay.innerText = secondsRemaining;
            if (secondsRemaining <= 0) {
                clearInterval(countdownIntervalId);
                triggerAutoLogout();
            }
        }, 1000);
    }

    function hideWarningModal() {
        if (warningModalEl) {
            warningModalEl.classList.add('hidden');
            warningModalEl.classList.remove('flex');
        }
        if (countdownIntervalId) {
            clearInterval(countdownIntervalId);
            countdownIntervalId = null;
        }
    }

    window.staySignedIn = function () {
        hideWarningModal();
        pingServer().then(() => {
            recordActivity();
        });
    };

    function triggerAutoLogout() {
        hideWarningModal();
        showSessionTerminatedOverlay('Session expired due to inactivity.');
        broadcast('SESSION_LOGOUT', { reason: 'idle_timeout' });
        setTimeout(() => {
            window.location.replace('/logout/?reason=timeout');
        }, 300);
    }

    function resetIdleTimer(shouldHideWarning = true) {
        if (shouldHideWarning) hideWarningModal();
        if (warningTimerId) clearTimeout(warningTimerId);
        if (logoutTimerId) clearTimeout(logoutTimerId);

        const timeSinceActive = Date.now() - lastActiveTime;
        const timeUntilWarning = Math.max(0, (IDLE_TIMEOUT_MS - WARNING_TIME_MS) - timeSinceActive);
        const timeUntilLogout = Math.max(0, IDLE_TIMEOUT_MS - timeSinceActive);

        warningTimerId = setTimeout(showWarningModal, timeUntilWarning);
        logoutTimerId = setTimeout(triggerAutoLogout, timeUntilLogout);
    }

    // Graceful Overlay when session is closed from another tab
    function showSessionTerminatedOverlay(msg) {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-4 text-white animate-in fade-in duration-150';
        overlay.innerHTML = `
            <div class="bg-slate-900 border border-slate-700 p-6 max-w-sm w-full text-center shadow-2xl">
                <div class="w-12 h-12 bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto mb-3">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                    </svg>
                </div>
                <h4 class="font-display font-bold text-sm text-white mb-1">Session Terminated</h4>
                <p class="text-xs text-slate-400 mb-3">${msg || 'Redirecting to login...'}</p>
                <div class="w-5 h-5 border-2 border-blue-400 border-t-transparent animate-spin mx-auto rounded-full"></div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    // Periodic Server Heartbeat Ping
    function pingServer() {
        return fetch('/dashboard/session/ping/', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                triggerAutoLogout();
                return { authenticated: false };
            }
            return response.json();
        })
        .then(data => {
            if (data && data.authenticated === false) {
                triggerAutoLogout();
            }
            return data;
        })
        .catch(err => {
            // Ignore network blips during page unload
        });
    }

    // Initialize timers and start heartbeat
    resetIdleTimer();
    setInterval(pingServer, PING_INTERVAL_MS);

})();
