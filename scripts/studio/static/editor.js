// Picasso Studio editor — Pro creative tool UI.
// Layout: icon-grid toolbar (left) · canvas with floating controls (center) · filmstrip history (right)
// Wiring: real /api/* + SSE; falls back to a built-in mock when /api/ops 404s (preview mode).

(() => {
  // ---- State -------------------------------------------------------------
  const state = {
    sessionId: null,
    ops: {},                  // { category: [op...] }
    opsByName: {},
    sessionData: null,        // last server payload
    zoom: 1,
    fitZoom: 1,
    pan: { x: 0, y: 0 },
    showCompare: false,
    comparePos: 0.5,          // 0..1
    checker: false,
    activeStep: -1,           // index into history; -1 means "current"
    naturalSize: { w: 0, h: 0 },
    fileMeta: { format: "", bytes: 0 },
    isMock: false,
    accent: "blue",
    density: "default",
    showLabels: false,
    toolFilter: "all",
    eventSource: null,
  };

  const ACCENTS = {
    blue:    { accent: "#6ea8d8", accent2: "#4a7ba8", soft: "#243a52" },
    indigo:  { accent: "#8b8cf0", accent2: "#6263c4", soft: "#2c2c54" },
    teal:    { accent: "#5fcfb8", accent2: "#3f9c8a", soft: "#1f3d3a" },
    pink:    { accent: "#e88bb6", accent2: "#b35e87", soft: "#42263a" },
    orange:  { accent: "#e8a86c", accent2: "#b87a44", soft: "#42301f" },
    lime:    { accent: "#b8d96a", accent2: "#869d44", soft: "#2f3a1f" },
    red:     { accent: "#e26b6b", accent2: "#a84444", soft: "#421f1f" },
    mono:    { accent: "#d6dde4", accent2: "#8a96a4", soft: "#2a323e" },
  };

  // ---- DOM lookups -------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const els = {
    fileInput:    $("file-input"),
    uploadBtn:    $("upload-btn"),
    undoBtn:      $("undo-btn"),
    redoBtn:      $("redo-btn"),
    clearBtn:     $("clear-btn"),
    copyBtn:      $("copy-btn"),
    downloadBtn:  $("download-btn"),
    tweaksBtn:    $("tweaks-btn"),
    searchTrigger:$("search-trigger"),
    searchInput:  $("search-input"),
    opsArea:      $("ops-area"),
    opsLoaded:    $("ops-loaded"),
    canvasArea:   $("canvas-area"),
    canvasStage:  $("canvas-stage"),
    canvasFrame:  $("canvas-frame"),
    canvasImg:    $("canvas-img"),
    canvasEmpty:  $("canvas-empty"),
    canvasTools:  $("canvas-tools"),
    canvasMeta:   $("canvas-meta"),
    zoomDisplay:  $("zoom-display"),
    statusZoom:   $("status-zoom"),
    sessionPill:  $("session-pill"),
    sessionId:    $("session-id"),
    sessionCopy:  $("session-copy"),
    filmstrip:    $("filmstrip"),
    historyCount: $("history-count"),
    mcpLink:      $("mcp-link"),
    mcpUrl:       $("mcp-url"),
    connStatus:   $("conn-status"),
    liveDot:      $("live-dot"),
    dimItem:      $("dim-item"),  dimText: $("dim-text"),
    formatItem:   $("format-item"), formatText: $("format-text"),
    filesizeItem: $("filesize-item"), filesizeText: $("filesize-text"),
    lastOp:       $("last-op"),    lastOpText: $("last-op-text"),
    tweaks:       $("tweaks"),
    tweaksHead:   $("tweaks-head"),
    tweaksClose:  $("tweaks-close"),
    tweaksBody:   $("tweaks-body"),
    paletteOverlay:$("palette-overlay"),
    paletteInput: $("palette-input"),
    paletteResults:$("palette-results"),
    toolbarTabs:  $("toolbar-tabs"),
    toastHost:    $("toast-host"),
    toastHostAlerts: $("toast-host-alerts"),
    appShell:     document.querySelector(".app"),
  };

  // ---- Toast -------------------------------------------------------------
  // Errors route to the assertive aria-live host so screen readers announce
  // them without focus change; success/info go to the polite host. Without
  // this, AT users miss op failures entirely.
  function toast(msg, type = "") {
    const t = document.createElement("div");
    t.className = "toast" + (type ? " " + type : "");
    t.textContent = msg;
    const host = type === "error" ? els.toastHostAlerts : els.toastHost;
    host.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .3s"; }, 1700);
    setTimeout(() => t.remove(), 2100);
  }

  // ---- a11y helpers ------------------------------------------------------
  // Focusable elements inside an open dialog/popover, used to trap Tab.
  const FOCUSABLE_SEL =
    'a[href], area[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function focusableIn(root) {
    return Array.from(root.querySelectorAll(FOCUSABLE_SEL))
      .filter(el => !el.hasAttribute("aria-hidden") && el.offsetParent !== null);
  }

  // Wrap an open dialog with: focus the first field, trap Tab inside, close
  // on Escape, restore focus to the opener on close. Returns a {dispose}
  // handle the caller invokes from its own close path.
  function trapDialogFocus(rootEl, opener, onEscape) {
    const previousActive = document.activeElement;
    const focusables = focusableIn(rootEl);
    if (focusables[0]) focusables[0].focus();
    function onKeyDown(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onEscape && onEscape();
        return;
      }
      if (e.key !== "Tab") return;
      const list = focusableIn(rootEl);
      if (list.length === 0) return;
      const first = list[0], last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        last.focus(); e.preventDefault();
      } else if (!e.shiftKey && document.activeElement === last) {
        first.focus(); e.preventDefault();
      }
    }
    rootEl.addEventListener("keydown", onKeyDown);
    return {
      dispose() {
        rootEl.removeEventListener("keydown", onKeyDown);
        const restoreTarget = opener || previousActive;
        if (restoreTarget && typeof restoreTarget.focus === "function") {
          restoreTarget.focus();
        }
      },
    };
  }

  // Confirm via a real <dialog role="alertdialog"> instead of native confirm()
  // (which steals focus into browser chrome and is announced inconsistently).
  // Resolves true on confirm, false on cancel/Escape/backdrop.
  function alertConfirm({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", danger = false }) {
    return new Promise(resolve => {
      const opener = document.activeElement;
      const overlay = document.createElement("div");
      overlay.className = "palette-overlay open";
      overlay.style.zIndex = "10000";
      overlay.innerHTML = `
        <div class="palette" role="alertdialog" aria-modal="true"
             aria-labelledby="ad-title" aria-describedby="ad-msg"
             style="width:380px;padding:18px 20px;">
          <h3 id="ad-title" style="margin:0 0 8px 0;font-size:14px;">${title}</h3>
          <p id="ad-msg" style="margin:0 0 16px 0;color:var(--ink-2);font-size:12.5px;line-height:1.45;">${message}</p>
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button class="pill-btn ad-cancel" type="button">${cancelLabel}</button>
            <button class="pill-btn ${danger ? '' : 'primary'} ad-confirm" type="button"
                    style="${danger ? 'background:var(--danger);color:#fff;border-color:var(--danger);' : ''}">${confirmLabel}</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      const card = overlay.querySelector(".palette");
      const cancelBtn = overlay.querySelector(".ad-cancel");
      const confirmBtn = overlay.querySelector(".ad-confirm");

      function finish(value) {
        trap.dispose();
        overlay.remove();
        resolve(value);
      }
      const trap = trapDialogFocus(card, opener, () => finish(false));
      cancelBtn.onclick = () => finish(false);
      confirmBtn.onclick = () => finish(true);
      overlay.addEventListener("mousedown", (e) => {
        if (e.target === overlay) finish(false);
      });
    });
  }

  // Update the canvas <img alt> to reflect what the AT user is "seeing".
  function updateCanvasAlt() {
    const sd = state.sessionData;
    const sz = state.naturalSize;
    if (!sd) {
      els.canvasImg.alt = "No image loaded";
      return;
    }
    const total = sd.history?.length || 0;
    const dims = (sz.w && sz.h) ? `, ${sz.w} by ${sz.h} pixels` : "";
    if (state.activeStep < 0 || total === 0) {
      els.canvasImg.alt = `Original image${dims}`;
    } else {
      const step = state.activeStep + 1;
      const note = sd.history[state.activeStep]?.note || "edit";
      els.canvasImg.alt = `${note} — step ${step} of ${total}${dims}`;
    }
  }

  // Reflect session state in the document title so AT/tab-switching users
  // can distinguish browser tabs and know whether unsaved edits exist.
  function updateDocumentTitle() {
    const sd = state.sessionData;
    const total = sd?.history?.length || 0;
    document.title = total ? `Picasso Studio — ${total} edit${total > 1 ? "s" : ""}` : "Picasso Studio";
  }

  // WAI-ARIA radiogroup / tablist keyboard pattern. Implements roving
  // tabindex (only the active item is in the Tab order) + arrow / Home /
  // End traversal. Radio/tab containers without this make AT users Tab
  // through every option.
  function wireRadiogroup(container) {
    if (!container) return;
    const items = Array.from(container.querySelectorAll('[role="radio"], [role="tab"]'));
    if (!items.length) return;
    const setActive = (i) => {
      items.forEach((r, j) => { r.tabIndex = j === i ? 0 : -1; });
      items[i].focus();
      items[i].click();
    };
    const startIdx = Math.max(0, items.findIndex(r =>
      r.getAttribute("aria-checked") === "true" ||
      r.getAttribute("aria-selected") === "true"));
    items.forEach((r, i) => { r.tabIndex = i === startIdx ? 0 : -1; });
    container.addEventListener("keydown", (e) => {
      const i = items.indexOf(document.activeElement);
      if (i < 0) return;
      let next = null;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % items.length;
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + items.length) % items.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = items.length - 1;
      if (next !== null) { e.preventDefault(); setActive(next); }
    });
  }

  // ---- Auth token bootstrap + Net helpers --------------------------------
  // Token sources, in priority:
  //  1. `?launch=NONCE` in the URL — first run from the launcher / open_studio
  //     MCP tool; we redeem it via /token-handshake which also sets a cookie.
  //  2. sessionStorage["picasso.token"] — surviving page refreshes.
  //  3. Cookie set by /token-handshake — implicit; used by EventSource +
  //     `<img>` (which can't set Authorization headers).
  async function bootstrapAuth() {
    const params = new URLSearchParams(location.search);
    const launch = params.get("launch");
    if (launch) {
      try {
        const res = await fetch(`/token-handshake?launch=${encodeURIComponent(launch)}`, {
          credentials: "same-origin",
        });
        if (res.ok) {
          const data = await res.json();
          sessionStorage.setItem("picasso.token", data.token);
        }
      } catch (e) { /* silent — fallback to existing storage */ }
      // Strip the launch nonce from the URL so a refresh doesn't try to
      // redeem an already-consumed nonce.
      const clean = new URL(location.href);
      clean.searchParams.delete("launch");
      history.replaceState({}, "", clean.toString());
    }
  }

  function authHeader() {
    const tok = sessionStorage.getItem("picasso.token");
    return tok ? { "Authorization": "Bearer " + tok } : {};
  }

  async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}), ...authHeader() };
    const res = await fetch(path, { credentials: "same-origin", ...opts, headers });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  // ---- Op loading + categorization --------------------------------------
  async function loadOps() {
    try {
      state.ops = await api("/api/ops");
      state.isMock = false;
    } catch (e) {
      // Standalone preview mode — use a baked-in registry from the catalog.
      state.ops = window.__MOCK_OPS || {};
      state.isMock = true;
      els.connStatus.textContent = "preview (no backend)";
      els.liveDot.style.background = "var(--warn)";
      els.liveDot.style.boxShadow = "0 0 6px var(--warn)";
    }
    // index by name
    state.opsByName = {};
    for (const cat of Object.keys(state.ops)) {
      for (const op of state.ops[cat]) state.opsByName[op.name] = { ...op, category: cat };
    }
    const total = Object.values(state.ops).reduce((n, arr) => n + arr.length, 0);
    els.opsLoaded.textContent = `${total}`;
    renderOps();
  }

  function categoryColor(cat) {
    const meta = (window.OP_CATEGORIES || {})[cat];
    if (!meta) return { color: "var(--accent)", soft: "var(--accent-soft)" };
    return { color: `oklch(0.74 0.13 ${meta.hue})`, soft: `oklch(0.28 0.05 ${meta.hue})` };
  }

  function renderOps() {
    const root = els.opsArea;
    root.innerHTML = "";
    const order = ["transform", "color", "filter", "effect", "compose", "social", "animate", "gif", "utility"];
    const catKeys = order.filter(k => state.ops[k]);
    for (const cat of catKeys) {
      if (!filterShowsCat(cat)) continue;
      const ops = state.ops[cat];
      const meta = (window.OP_CATEGORIES || {})[cat] || { label: cat };
      const colors = categoryColor(cat);

      const div = document.createElement("div");
      div.className = "cat";
      div.style.setProperty("--cat-color", colors.color);
      div.style.setProperty("--cat-color-soft", colors.soft);

      const head = document.createElement("button");
      head.type = "button";
      head.className = "cat-header";
      head.setAttribute("aria-expanded", "true");
      head.setAttribute("aria-label", `${meta.label} category, ${ops.length} ops`);
      head.innerHTML = `
        <span class="cat-dot" aria-hidden="true"></span>
        <span>${meta.label}</span>
        <span class="count" aria-hidden="true">${ops.length}</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="M6 9l6 6 6-6"/></svg>
      `;
      head.onclick = () => {
        const collapsed = div.classList.toggle("collapsed");
        head.setAttribute("aria-expanded", collapsed ? "false" : "true");
      };
      div.appendChild(head);

      const grid = document.createElement("div");
      grid.className = "ops-grid";
      for (const op of ops) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "op-btn" + (Object.keys(op.params || {}).length ? " has-params" : "");
        btn.dataset.tip = op.label;
        btn.dataset.opName = op.name;
        // Accessible name = the op label; visible tooltip via title for sighted hover.
        // The CSS `data-tip` tooltip stays for sighted users — focus-visible
        // (handled in CSS) gives keyboard users their own focus indicator.
        const hasParams = Object.keys(op.params || {}).length > 0;
        btn.setAttribute("aria-label",
          op.label + (hasParams ? " (opens parameters dialog)" : "")
        );
        if (hasParams) {
          btn.setAttribute("aria-haspopup", "dialog");
          btn.setAttribute("aria-expanded", "false");
        }
        btn.title = op.label;
        btn.innerHTML = `
          <span class="op-glyph" aria-hidden="true">${window.renderOpIcon(op.name, 18)}</span>
          <span class="op-label" aria-hidden="true">${op.label}</span>
        `;
        btn.onclick = (e) => {
          e.stopPropagation();
          if (op.interactive) {
            enterInteractive(op);
          } else {
            if (hasParams) btn.setAttribute("aria-expanded", "true");
            openPopover(op, btn);
          }
        };
        grid.appendChild(btn);
      }
      div.appendChild(grid);
      root.appendChild(div);
    }
  }

  function filterShowsCat(cat) {
    if (state.toolFilter === "all") return true;
    if (state.toolFilter === "image") return ["transform","color","filter","effect","compose","social","utility"].includes(cat);
    if (state.toolFilter === "gif") return cat === "gif";
    if (state.toolFilter === "anim") return cat === "animate";
    return true;
  }

  // ---- Param popover -----------------------------------------------------
  let openPop = null;
  let popoverFieldSeq = 0;

  function closePopover() {
    if (openPop) {
      openPop.trap?.dispose();
      openPop.outsideClickCleanup?.();
      openPop.el.remove();
      openPop.btn.classList.remove("open");
      if (openPop.btn.hasAttribute("aria-expanded")) {
        openPop.btn.setAttribute("aria-expanded", "false");
      }
      openPop = null;
    }
  }

  function openPopover(op, btn) {
    closePopover();
    btn.classList.add("open");
    if (btn.hasAttribute("aria-expanded")) btn.setAttribute("aria-expanded", "true");
    const pop = document.createElement("div");
    pop.className = "popover";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-modal", "false");
    pop.setAttribute("aria-label", `${op.label} parameters`);
    const colors = categoryColor(op.category || resolveCategory(op.name));
    pop.style.setProperty("--cat-color", colors.color);
    pop.style.setProperty("--cat-color-soft", colors.soft);

    const arrow = document.createElement("div");
    arrow.className = "popover-arrow";
    arrow.setAttribute("aria-hidden", "true");
    pop.appendChild(arrow);

    const head = document.createElement("div");
    head.className = "popover-head";
    head.innerHTML = `
      <span class="glyph" aria-hidden="true">${window.renderOpIcon(op.name, 16)}</span>
      <span class="title">${op.label}</span>
      <span class="cat-tag">${op.category || resolveCategory(op.name)}</span>
    `;
    pop.appendChild(head);

    if (op.description) {
      const d = document.createElement("div");
      d.className = "popover-desc";
      d.textContent = op.description;
      pop.appendChild(d);
    }

    // Build form fields. Each control gets a unique id and the <label> gets
    // an explicit `for` so screen readers announce field name + value
    // correctly. Sliders also expose aria-valuetext so the live value reads.
    const params = op.params || {};
    const values = {};
    const fieldsHost = document.createElement("div");
    pop.appendChild(fieldsHost);

    for (const [pname, pmeta] of Object.entries(params)) {
      const fieldId = `pop-${op.name}-${pname}-${++popoverFieldSeq}`;
      const field = document.createElement("div");
      field.className = "field";
      const label = document.createElement("label");
      label.setAttribute("for", fieldId);
      const valSpan = document.createElement("span");
      valSpan.className = "val";
      valSpan.setAttribute("aria-hidden", "true"); // value is on the control
      label.innerHTML = `<span>${pname}</span>`;
      const helpText = pmeta.help || "";
      if (helpText && pmeta.type !== "int" && pmeta.type !== "float") {
        const help = document.createElement("span");
        help.className = "help";
        help.textContent = helpText;
        label.appendChild(help);
      } else {
        label.appendChild(valSpan);
      }
      field.appendChild(label);

      // pick best control
      const def = pmeta.default;
      const type = pmeta.type || "str";
      if ((type === "int" || type === "float") && pmeta.min !== undefined && pmeta.max !== undefined) {
        // slider — native <input type="range"> is the right semantic; we
        // keep aria-valuetext in sync so SRs announce the live value.
        const slider = document.createElement("input");
        slider.type = "range";
        slider.id = fieldId;
        slider.min = pmeta.min;
        slider.max = pmeta.max;
        slider.step = type === "int" ? 1 : ((pmeta.max - pmeta.min) / 100);
        slider.value = def !== undefined && def !== null ? def : pmeta.min;
        slider.setAttribute("aria-label", pname);
        slider.setAttribute("aria-valuetext", String(slider.value));
        valSpan.textContent = slider.value;
        slider.oninput = () => {
          values[pname] = type === "int" ? parseInt(slider.value, 10) : parseFloat(slider.value);
          valSpan.textContent = slider.value;
          slider.setAttribute("aria-valuetext", String(slider.value));
        };
        values[pname] = type === "int" ? parseInt(slider.value, 10) : parseFloat(slider.value);
        field.appendChild(slider);
      } else if (type === "str" && pmeta.help && pmeta.help.includes("/")) {
        // segmented choices
        const choices = parseChoices(pmeta.help);
        if (choices.length >= 2 && choices.length <= 6) {
          const seg = document.createElement("div");
          seg.className = "seg";
          seg.setAttribute("role", "radiogroup");
          seg.setAttribute("aria-labelledby", fieldId + "-grouplabel");
          // The <label for> can't point to a non-form-control, so we add a
          // hidden anchor with the same id for aria-labelledby instead.
          const anchor = document.createElement("span");
          anchor.id = fieldId + "-grouplabel";
          anchor.className = "visually-hidden";
          anchor.textContent = pname;
          field.appendChild(anchor);
          choices.forEach(ch => {
            const b = document.createElement("button");
            b.type = "button";
            b.setAttribute("role", "radio");
            b.setAttribute("aria-checked", "false");
            b.textContent = ch;
            b.onclick = () => {
              seg.querySelectorAll("button").forEach(x => {
                x.classList.remove("active");
                x.setAttribute("aria-checked", "false");
              });
              b.classList.add("active");
              b.setAttribute("aria-checked", "true");
              values[pname] = ch;
            };
            if (ch === def || (def == null && ch === choices[0])) {
              b.classList.add("active");
              b.setAttribute("aria-checked", "true");
              values[pname] = ch;
            }
            seg.appendChild(b);
          });
          field.appendChild(seg);
          // Move the for-target onto the first radio so label-click focuses it.
          const firstRadio = seg.querySelector("button");
          if (firstRadio) firstRadio.id = fieldId;
          wireRadiogroup(seg);
        } else {
          const sel = document.createElement("select");
          sel.id = fieldId;
          for (const ch of choices) {
            const o = document.createElement("option");
            o.value = ch; o.textContent = ch;
            if (ch === def) o.selected = true;
            sel.appendChild(o);
          }
          sel.onchange = () => values[pname] = sel.value;
          values[pname] = def || choices[0];
          field.appendChild(sel);
        }
      } else if (type === "str" && (pname.toLowerCase().includes("color") || (typeof def === "string" && /^#[0-9a-f]{6}$/i.test(def)))) {
        // color picker — both inputs share the field name; for/id points at
        // the picker (the visual color square is the primary affordance).
        const row = document.createElement("div");
        row.className = "color-row";
        const picker = document.createElement("input");
        picker.type = "color";
        picker.id = fieldId;
        picker.setAttribute("aria-label", pname + " (color picker)");
        picker.value = def && /^#[0-9a-f]{6}$/i.test(def) ? def : "#ffffff";
        const text = document.createElement("input");
        text.type = "text";
        text.id = fieldId + "-hex";
        text.setAttribute("aria-label", pname + " (hex value)");
        text.value = def !== undefined ? def : "";
        picker.oninput = () => { text.value = picker.value; values[pname] = picker.value; };
        text.oninput = () => { values[pname] = text.value; if (/^#[0-9a-f]{6}$/i.test(text.value)) picker.value = text.value; };
        values[pname] = text.value;
        row.appendChild(picker);
        row.appendChild(text);
        field.appendChild(row);
      } else if (type === "bool") {
        const seg = document.createElement("div");
        seg.className = "seg";
        seg.setAttribute("role", "radiogroup");
        seg.setAttribute("aria-labelledby", fieldId + "-grouplabel");
        const anchor = document.createElement("span");
        anchor.id = fieldId + "-grouplabel";
        anchor.className = "visually-hidden";
        anchor.textContent = pname;
        field.appendChild(anchor);
        ["true","false"].forEach(ch => {
          const b = document.createElement("button");
          b.type = "button";
          b.setAttribute("role", "radio");
          b.setAttribute("aria-checked", "false");
          b.textContent = ch;
          b.onclick = () => {
            seg.querySelectorAll("button").forEach(x => {
              x.classList.remove("active");
              x.setAttribute("aria-checked", "false");
            });
            b.classList.add("active");
            b.setAttribute("aria-checked", "true");
            values[pname] = ch === "true";
          };
          if ((def === true && ch === "true") || (def !== true && ch === "false")) {
            b.classList.add("active");
            b.setAttribute("aria-checked", "true");
            values[pname] = ch === "true";
          }
          seg.appendChild(b);
        });
        field.appendChild(seg);
        const firstRadio = seg.querySelector("button");
        if (firstRadio) firstRadio.id = fieldId;
        wireRadiogroup(seg);
      } else if (type === "int" || type === "float") {
        // bare numeric input
        const input = document.createElement("input");
        input.type = "number";
        input.id = fieldId;
        if (def != null && def !== "—") input.value = def;
        if (pmeta.min !== undefined) input.min = pmeta.min;
        if (pmeta.max !== undefined) input.max = pmeta.max;
        input.oninput = () => {
          values[pname] = type === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
        };
        if (input.value !== "") values[pname] = type === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
        field.appendChild(input);
      } else {
        const input = document.createElement("input");
        input.type = "text";
        input.id = fieldId;
        if (def != null) input.value = def;
        input.oninput = () => values[pname] = input.value;
        if (def != null) values[pname] = def;
        field.appendChild(input);
      }
      fieldsHost.appendChild(field);
    }

    // actions
    const actions = document.createElement("div");
    actions.className = "popover-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "pill-btn";
    cancel.textContent = "Cancel";
    cancel.onclick = closePopover;
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "pill-btn primary";
    apply.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12l5 5 9-12"/></svg> Apply`;
    apply.setAttribute("aria-label", `Apply ${op.label}`);
    apply.onclick = () => { applyOp(op, values); closePopover(); };
    actions.appendChild(cancel);
    actions.appendChild(apply);
    pop.appendChild(actions);

    document.body.appendChild(pop);

    // position to the right of the button
    const r = btn.getBoundingClientRect();
    let left = r.right + 10;
    let top = r.top;
    // clamp into viewport
    const popW = 280;
    if (left + popW > window.innerWidth - 8) left = r.left - popW - 10;
    const popH = pop.offsetHeight;
    if (top + popH > window.innerHeight - 8) top = window.innerHeight - popH - 10;
    if (top < 8) top = 8;
    pop.style.left = left + "px";
    pop.style.top = top + "px";

    // Focus trap + Escape + return-focus on close. Without this, Tab cycles
    // out of the popover into background content, leaving the popover
    // visually open with no focused control.
    const trap = trapDialogFocus(pop, btn, () => closePopover());

    // Close on outside click. Bound after a microtask so the activating
    // click on `btn` doesn't immediately re-trigger close.
    let outsideClickCleanup = null;
    setTimeout(() => {
      const dismiss = (e) => {
        if (!pop.contains(e.target) && e.target !== btn) closePopover();
      };
      document.addEventListener("mousedown", dismiss);
      outsideClickCleanup = () => document.removeEventListener("mousedown", dismiss);
      if (openPop) openPop.outsideClickCleanup = outsideClickCleanup;
    }, 0);

    openPop = { el: pop, btn, trap, outsideClickCleanup };
  }

  function parseChoices(help) {
    // accepts "horizontal or vertical" or "right/left/up/down" or "right/left/up/down/center"
    const m = help.match(/[a-z_]+(?:[\/]\s?[a-z_]+)+/i);
    if (m) return m[0].split("/").map(s => s.trim());
    if (/\bor\b/.test(help)) return help.split(/\s+or\s+/i).map(s => s.trim()).filter(Boolean);
    return [];
  }

  function resolveCategory(opName) {
    for (const cat of Object.keys(state.ops)) {
      if (state.ops[cat].some(o => o.name === opName)) return cat;
    }
    return "filter";
  }

  // ---- Apply op ----------------------------------------------------------
  async function applyOp(op, values) {
    if (!state.sessionId) {
      toast("Upload an image first", "error");
      return;
    }
    if (state.isMock) {
      mockApplyOp(op, values);
      return;
    }
    const body = { session_id: state.sessionId, ...values };
    try {
      const result = await api(`/api/ops/${op.name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (result.error) {
        toast(`Error: ${result.error}`, "error");
      } else {
        toast(`${op.label} applied`, "ok");
      }
    } catch (e) {
      toast(`Failed: ${e.message}`, "error");
    }
  }

  // ---- Upload ------------------------------------------------------------
  async function uploadFile(file) {
    if (state.isMock) {
      mockUploadFile(file);
      return;
    }
    const fd = new FormData();
    fd.append("image", file);
    try {
      const sess = await api("/api/sessions", { method: "POST", body: fd });
      onSessionCreated(sess);
    } catch (e) {
      toast(`Upload failed: ${e.message}`, "error");
    }
  }

  function onSessionCreated(sess) {
    state.sessionId = sess.id;
    try { localStorage.setItem("picasso.lastSession", sess.id); } catch (e) {}
    els.sessionId.textContent = sess.id;
    els.sessionPill.classList.add("active");
    setCanvasFromRel(sess.current_image);
    renderHistory(sess);
    state.fileMeta.format = (sess.current_image.split(".").pop() || "").toUpperCase();
    state.fileMeta.bytes = sess.size || 0;
    refreshStatusBar();
    if (!state.isMock) subscribeSSE(sess.id);
  }

  function setCanvasFromRel(relPath) {
    const url = state.isMock ? relPath : `/sessions_files/${relPath}?t=${Date.now()}`;
    els.canvasImg.onload = () => {
      state.naturalSize = { w: els.canvasImg.naturalWidth, h: els.canvasImg.naturalHeight };
      els.canvasFrame.style.display = "block";
      els.canvasEmpty.style.display = "none";
      els.canvasTools.style.display = "flex";
      fitCanvas();
      refreshStatusBar();
      updateCanvasAlt();
      updateDocumentTitle();
    };
    els.canvasImg.src = url;
  }

  // ---- History / Filmstrip ----------------------------------------------
  function renderHistory(sess) {
    state.sessionData = sess;
    const hist = sess.history || [];
    els.historyCount.textContent = `${hist.length} step${hist.length === 1 ? "" : "s"}`;
    els.filmstrip.innerHTML = "";

    // step 0 = original
    addFilmRow({
      thumb: rel(sess.original),
      name: "Original",
      params: "",
      idx: -1,
      isOriginal: true,
    });

    for (let i = 0; i < hist.length; i++) {
      const h = hist[i];
      addFilmRow({
        thumb: rel(h.output),
        name: h.note || (state.opsByName[h.op]?.label) || h.op,
        params: paramSummary(h.params),
        idx: i,
        isOriginal: false,
      });
    }

    if (hist.length === 0 && !sess.original) {
      els.filmstrip.innerHTML = `<div class="filmstrip-empty">No edits yet — apply an op to get started.</div>`;
    }

    if (hist.length) {
      const last = hist[hist.length - 1];
      els.lastOp.style.display = "inline-flex";
      els.lastOpText.textContent = state.opsByName[last.op]?.label || last.op;
    } else {
      els.lastOp.style.display = "none";
    }
  }

  function rel(p) {
    return state.isMock ? p : `/sessions_files/${p}?t=${state.sessionId || ""}`;
  }

  function addFilmRow({ thumb, name, params, idx, isOriginal }) {
    if (els.filmstrip.querySelector(".filmstrip-empty")) els.filmstrip.innerHTML = "";

    const wrap = document.createElement("div");
    wrap.style.display = "flex";
    wrap.style.flexDirection = "column";

    if (idx >= 0) {
      const c = document.createElement("div");
      c.className = "film-connector";
      wrap.appendChild(c);
    }

    // Real <button> so keyboard users can Tab into the history and pick a
    // step. The previous <div onclick> was unreachable by AT.
    const row = document.createElement("button");
    row.type = "button";
    row.className = "film-step";
    const labelName = escapeHtml(name);
    const stepLabel = isOriginal ? "Original image" : `Step ${idx + 1}: ${labelName}`;
    row.setAttribute("aria-label", stepLabel + (params ? ` (${escapeHtml(params)})` : ""));
    if (idx === state.activeStep) {
      row.classList.add("active");
      row.setAttribute("aria-current", "step");
    }
    row.innerHTML = `
      <div class="thumb"><img src="${thumb}" alt="" /></div>
      <div class="meta">
        <div class="op-name">${labelName}</div>
        ${params ? `<div class="params">${escapeHtml(params)}</div>` : ""}
      </div>
      <span class="step-num" aria-hidden="true">${isOriginal ? "ORG" : String(idx + 1).padStart(2, "0")}</span>
    `;
    row.onclick = () => {
      state.activeStep = idx;
      els.canvasImg.src = thumb;
      els.filmstrip.querySelectorAll(".film-step").forEach(r => {
        r.classList.remove("active");
        r.removeAttribute("aria-current");
      });
      row.classList.add("active");
      row.setAttribute("aria-current", "step");
      updateCanvasAlt();
    };
    wrap.appendChild(row);
    els.filmstrip.appendChild(wrap);
  }

  function paramSummary(params) {
    if (!params || !Object.keys(params).length) return "";
    return Object.entries(params).slice(0, 3).map(([k, v]) => {
      let s = String(v);
      if (s.length > 12) s = s.slice(0, 11) + "…";
      return `${k}=${s}`;
    }).join(" · ");
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  // ---- SSE ---------------------------------------------------------------
  function subscribeSSE(sid) {
    if (state.eventSource) state.eventSource.close();
    // withCredentials sends the picasso_token cookie set by /token-handshake.
    // EventSource can't add an Authorization header, so cookie is the only path.
    const es = new EventSource(`/api/sessions/${sid}/events`, { withCredentials: true });
    state.eventSource = es;
    es.onopen = () => {
      els.connStatus.textContent = "live";
      els.liveDot.style.background = "var(--ok)";
      els.liveDot.style.boxShadow = "0 0 6px var(--ok)";
    };
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      // R3 backend split the single `op_applied` event into two:
      //   - `op_entry_appended` carries the new entry + cursor flags only
      //     (no full snapshot — saves ~50KB per event on long histories).
      //   - `cursor_changed` carries the full session for undo/redo/clear/jump.
      // `hello` is the initial subscribe-time snapshot. Old `op_applied`
      // kept for compatibility with any older backend builds.
      if (data.type === "hello" || data.type === "cursor_changed" || data.type === "op_applied") {
        const sess = data.session;
        if (!sess) return;
        state.activeStep = (typeof sess.cursor === "number") ? sess.cursor : sess.history.length - 1;
        setCanvasFromRel(sess.current_image);
        renderHistory(sess);
        state.fileMeta.format = (sess.current_image.split(".").pop() || "").toUpperCase();
        state.fileMeta.bytes = sess.size || 0;
        refreshStatusBar();
        if (els.undoBtn) els.undoBtn.disabled = !sess.can_undo;
        if (els.redoBtn) els.redoBtn.disabled = !sess.can_redo;
        updateCanvasAlt();
        updateDocumentTitle();
      } else if (data.type === "op_entry_appended") {
        // Incremental update — apply the delta to the cached session
        // instead of re-fetching the whole snapshot.
        const sess = state.sessionData;
        if (sess && data.entry) {
          // Truncate redo branch (matches what record_op did server-side)
          if (data.cursor < sess.history.length) {
            sess.history = sess.history.slice(0, data.cursor);
          }
          sess.history.push(data.entry);
          sess.cursor = data.cursor;
          sess.can_undo = !!data.can_undo;
          sess.can_redo = !!data.can_redo;
          sess.current_image = data.entry.output;
          state.activeStep = data.cursor;
          setCanvasFromRel(sess.current_image);
          renderHistory(sess);
          state.fileMeta.format = (sess.current_image.split(".").pop() || "").toUpperCase();
          state.fileMeta.bytes = data.entry.size || 0;
          refreshStatusBar();
          if (els.undoBtn) els.undoBtn.disabled = !data.can_undo;
          if (els.redoBtn) els.redoBtn.disabled = !data.can_redo;
          updateCanvasAlt();
          updateDocumentTitle();
        }
      }
    };
    es.onerror = () => {
      els.connStatus.textContent = "reconnecting…";
      els.liveDot.style.background = "var(--warn)";
    };
  }

  // ---- Canvas: zoom, pan, fit -------------------------------------------
  function applyTransform() {
    const f = els.canvasFrame;
    f.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px) scale(${state.zoom})`;
    els.zoomDisplay.textContent = `${Math.round(state.zoom * 100)}%`;
    els.statusZoom.textContent = `${Math.round(state.zoom * 100)}%`;
    if (state.showCompare) updateCompareUI();
  }

  function fitCanvas() {
    const stage = els.canvasStage.getBoundingClientRect();
    const pad = 40;
    const sx = (stage.width - pad * 2) / state.naturalSize.w;
    const sy = (stage.height - pad * 2) / state.naturalSize.h;
    const z = Math.min(sx, sy, 1);
    state.zoom = z; state.fitZoom = z;
    state.pan.x = (stage.width - state.naturalSize.w * z) / 2;
    state.pan.y = (stage.height - state.naturalSize.h * z) / 2;
    applyTransform();
  }

  function setZoom(newZoom, anchorX, anchorY) {
    newZoom = Math.max(0.05, Math.min(8, newZoom));
    if (anchorX === undefined) {
      const r = els.canvasStage.getBoundingClientRect();
      anchorX = r.width / 2; anchorY = r.height / 2;
    }
    // keep pixel under cursor stable
    const ratio = newZoom / state.zoom;
    state.pan.x = anchorX - (anchorX - state.pan.x) * ratio;
    state.pan.y = anchorY - (anchorY - state.pan.y) * ratio;
    state.zoom = newZoom;
    applyTransform();
  }

  // ---- Canvas tools wiring ----------------------------------------------
  function bindCanvasTools() {
    els.canvasTools.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const a = btn.dataset.action;
      if (a === "zoom-in")  setZoom(state.zoom * 1.25);
      if (a === "zoom-out") setZoom(state.zoom / 1.25);
      if (a === "fit")      fitCanvas();
      if (a === "actual")   setZoom(1);
      if (a === "checker") {
        state.checker = !state.checker;
        els.canvasStage.classList.toggle("checker", state.checker);
        btn.classList.toggle("active", state.checker);
        btn.setAttribute("aria-pressed", state.checker ? "true" : "false");
      }
      if (a === "compare") {
        toggleCompare();
        btn.classList.toggle("active", state.showCompare);
        btn.setAttribute("aria-pressed", state.showCompare ? "true" : "false");
      }
    });

    // Pan with drag
    let dragging = false, sx = 0, sy = 0, px = 0, py = 0;
    els.canvasStage.addEventListener("mousedown", (e) => {
      if (e.target.closest(".compare-slider")) return;
      if (state.showCompare && e.target.closest(".compare-label")) return;
      if (interactiveMode || e.target.closest("#interactive-overlay") || e.target.closest("#apply-cancel-pill")) return;
      dragging = true;
      sx = e.clientX; sy = e.clientY;
      px = state.pan.x; py = state.pan.y;
      els.canvasStage.classList.add("grabbing");
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      state.pan.x = px + (e.clientX - sx);
      state.pan.y = py + (e.clientY - sy);
      applyTransform();
    });
    window.addEventListener("mouseup", () => {
      dragging = false;
      els.canvasStage.classList.remove("grabbing");
    });

    // Wheel zoom
    els.canvasStage.addEventListener("wheel", (e) => {
      if (els.canvasFrame.style.display === "none") return;
      e.preventDefault();
      const r = els.canvasStage.getBoundingClientRect();
      const ax = e.clientX - r.left;
      const ay = e.clientY - r.top;
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      setZoom(state.zoom * factor, ax, ay);
    }, { passive: false });
  }

  // ---- Before/After compare ---------------------------------------------
  let compareEls = null;

  function toggleCompare() {
    state.showCompare = !state.showCompare;
    if (state.showCompare) buildCompare(); else tearDownCompare();
  }

  function buildCompare() {
    if (!state.sessionData || !state.sessionData.history.length) {
      toast("Apply an op first to compare", "error");
      state.showCompare = false;
      return;
    }
    tearDownCompare();
    const stage = els.canvasStage;

    // Create a duplicate "before" frame inside canvas-frame, clipped to slider
    const beforeFrame = document.createElement("div");
    beforeFrame.style.cssText = `
      position: absolute; inset: 0;
      overflow: hidden;
      clip-path: inset(0 ${(1 - state.comparePos) * 100}% 0 0);
      pointer-events: none;
    `;
    const beforeImg = document.createElement("img");
    beforeImg.src = rel(state.sessionData.original);
    beforeImg.style.cssText = "display:block; width: 100%; height: 100%; object-fit: contain;";
    // Match the canvas image size exactly
    beforeImg.style.width = els.canvasImg.naturalWidth + "px";
    beforeImg.style.height = els.canvasImg.naturalHeight + "px";
    beforeFrame.appendChild(beforeImg);
    els.canvasFrame.appendChild(beforeFrame);

    // Slider + labels (in stage coords). Real ARIA slider semantics +
    // keyboard nudge so AT users can move the divider without the mouse.
    const slider = document.createElement("div");
    slider.className = "compare-slider";
    slider.setAttribute("role", "slider");
    slider.setAttribute("tabindex", "0");
    slider.setAttribute("aria-label", "Before / after comparison divider");
    slider.setAttribute("aria-valuemin", "0");
    slider.setAttribute("aria-valuemax", "100");
    slider.setAttribute("aria-valuenow", String(Math.round(state.comparePos * 100)));
    slider.setAttribute("aria-valuetext", `${Math.round(state.comparePos * 100)}% after`);
    slider.addEventListener("keydown", (e) => {
      const step = e.shiftKey ? 0.1 : 0.05;
      let nv = state.comparePos;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") nv -= step;
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") nv += step;
      else if (e.key === "Home") nv = 0;
      else if (e.key === "End") nv = 1;
      else return;
      e.preventDefault();
      state.comparePos = Math.max(0, Math.min(1, nv));
      updateCompareUI();
    });
    const labelB = document.createElement("div");
    labelB.className = "compare-label";
    labelB.textContent = "Before";
    labelB.style.left = "12px";
    const labelA = document.createElement("div");
    labelA.className = "compare-label";
    labelA.textContent = "After";
    labelA.style.right = "12px";
    stage.appendChild(slider);
    stage.appendChild(labelB);
    stage.appendChild(labelA);

    compareEls = { beforeFrame, slider, labelB, labelA };
    updateCompareUI();

    // Drag slider
    let dragging = false;
    slider.addEventListener("mousedown", (e) => { dragging = true; e.stopPropagation(); });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const r = stage.getBoundingClientRect();
      const x = e.clientX - r.left;
      // map x → comparePos based on the displayed image bounds
      const imgLeft = state.pan.x;
      const imgRight = state.pan.x + state.naturalSize.w * state.zoom;
      const t = (x - imgLeft) / (imgRight - imgLeft);
      state.comparePos = Math.max(0, Math.min(1, t));
      updateCompareUI();
    });
    window.addEventListener("mouseup", () => { dragging = false; });
  }

  function updateCompareUI() {
    if (!compareEls) return;
    const { beforeFrame, slider, labelB, labelA } = compareEls;
    beforeFrame.style.clipPath = `inset(0 ${(1 - state.comparePos) * 100}% 0 0)`;

    const imgLeft = state.pan.x;
    const imgWidth = state.naturalSize.w * state.zoom;
    const imgRight = imgLeft + imgWidth;
    const sliderX = imgLeft + imgWidth * state.comparePos;
    const stageH = els.canvasStage.getBoundingClientRect().height;
    const imgTop = state.pan.y;
    const imgHeight = state.naturalSize.h * state.zoom;

    slider.style.left = sliderX + "px";
    slider.style.top = Math.max(0, imgTop) + "px";
    slider.style.height = Math.min(stageH, imgHeight) + "px";
    const pct = Math.round(state.comparePos * 100);
    slider.setAttribute("aria-valuenow", String(pct));
    slider.setAttribute("aria-valuetext", `${pct}% after`);

    labelB.style.left = (imgLeft + 12) + "px";
    labelB.style.top = (imgTop + 12) + "px";
    labelA.style.left = "auto";
    labelA.style.right = (els.canvasStage.getBoundingClientRect().width - imgRight + 12) + "px";
    labelA.style.top = (imgTop + 12) + "px";
  }

  function tearDownCompare() {
    if (!compareEls) return;
    compareEls.beforeFrame.remove();
    compareEls.slider.remove();
    compareEls.labelB.remove();
    compareEls.labelA.remove();
    compareEls = null;
  }

  // ---- Status bar refresh ----------------------------------------------
  function refreshStatusBar() {
    if (state.naturalSize.w) {
      els.dimItem.style.display = "inline-flex";
      els.dimText.textContent = `${state.naturalSize.w} × ${state.naturalSize.h}`;
    }
    if (state.fileMeta.format) {
      els.formatItem.style.display = "inline-flex";
      els.formatText.textContent = state.fileMeta.format;
    }
    if (state.fileMeta.bytes) {
      els.filesizeItem.style.display = "inline-flex";
      els.filesizeText.textContent = formatBytes(state.fileMeta.bytes);
    } else {
      els.filesizeItem.style.display = "none";
    }
  }
  function formatBytes(b) {
    if (b < 1024) return b + " B";
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + " KB";
    return (b / 1024 / 1024).toFixed(2) + " MB";
  }

  // ---- Interactive ops (crop, text, etc.) -------------------------------
  // Active mode: { op, type, data } where type is "rect" | "text" | "point"
  let interactiveMode = null;

  function enterInteractive(op) {
    if (!state.sessionId) return toast("Upload an image first", "error");
    if (interactiveMode) exitInteractive(false);
    closePopover();
    const type = op.interactive && op.interactive.type;
    if (type === "rect") return enterRectMode(op);
    if (type === "text") return enterTextMode(op);
    toast("Interactive type not implemented: " + type, "error");
  }

  function exitInteractive(commit) {
    if (!interactiveMode) return;
    const m = interactiveMode;
    interactiveMode = null;
    document.getElementById("interactive-overlay")?.remove();
    document.getElementById("apply-cancel-pill")?.remove();
    document.getElementById("text-modal")?.remove();
    if (els.canvasTools && els.canvasFrame.style.display !== "none") {
      els.canvasTools.style.display = "flex";
    }
    if (commit && m && m.commit) m.commit();
  }

  function showApplyCancel(onApply, onCancel, label = "Apply") {
    const pill = document.createElement("div");
    pill.id = "apply-cancel-pill";
    pill.innerHTML = `
      <button class="ac-cancel">Cancel</button>
      <button class="ac-apply">${label}</button>
    `;
    pill.querySelector(".ac-cancel").onclick = onCancel;
    pill.querySelector(".ac-apply").onclick = onApply;
    els.canvasArea.appendChild(pill);
    if (els.canvasTools) els.canvasTools.style.display = "none";
  }

  // Convert image-pixel coords to screen coords (relative to canvas-stage), and back
  function imageToScreen(x, y) {
    const f = els.canvasFrame.getBoundingClientRect();
    const stage = els.canvasStage.getBoundingClientRect();
    const scaleX = f.width / state.naturalSize.w;
    const scaleY = f.height / state.naturalSize.h;
    return { x: f.left - stage.left + x * scaleX, y: f.top - stage.top + y * scaleY };
  }
  function screenToImage(sx, sy) {
    const f = els.canvasFrame.getBoundingClientRect();
    const stage = els.canvasStage.getBoundingClientRect();
    const scaleX = f.width / state.naturalSize.w;
    const scaleY = f.height / state.naturalSize.h;
    return { x: (sx - (f.left - stage.left)) / scaleX, y: (sy - (f.top - stage.top)) / scaleY };
  }

  // ---- RECT mode (crop) -------------------------------------------------
  function enterRectMode(op) {
    const w = state.naturalSize.w, h = state.naturalSize.h;
    // start with center 60% box
    let rect = { x1: Math.round(w * 0.2), y1: Math.round(h * 0.2),
                 x2: Math.round(w * 0.8), y2: Math.round(h * 0.8) };
    let aspect = "free"; // "free" | "1:1" | "16:9" | "source"

    const overlay = document.createElement("div");
    overlay.id = "interactive-overlay";
    overlay.className = "rect-overlay";
    overlay.innerHTML = `
      <div class="dim dim-top" aria-hidden="true"></div>
      <div class="dim dim-right" aria-hidden="true"></div>
      <div class="dim dim-bottom" aria-hidden="true"></div>
      <div class="dim dim-left" aria-hidden="true"></div>
      <div class="rect-box" role="application" tabindex="0"
           aria-label="Crop region — arrow keys to move, Shift+arrow to resize, hold Alt for 10px steps">
        <div class="rect-label" aria-live="polite"></div>
        <div class="handle h-nw" data-h="nw" aria-hidden="true"></div>
        <div class="handle h-n"  data-h="n"  aria-hidden="true"></div>
        <div class="handle h-ne" data-h="ne" aria-hidden="true"></div>
        <div class="handle h-e"  data-h="e"  aria-hidden="true"></div>
        <div class="handle h-se" data-h="se" aria-hidden="true"></div>
        <div class="handle h-s"  data-h="s"  aria-hidden="true"></div>
        <div class="handle h-sw" data-h="sw" aria-hidden="true"></div>
        <div class="handle h-w"  data-h="w"  aria-hidden="true"></div>
      </div>
      <div class="aspect-bar" role="radiogroup" aria-label="Crop aspect ratio">
        <button type="button" role="radio" data-a="free"   class="active" aria-checked="true">Free</button>
        <button type="button" role="radio" data-a="1:1"    aria-checked="false">1:1</button>
        <button type="button" role="radio" data-a="16:9"   aria-checked="false">16:9</button>
        <button type="button" role="radio" data-a="source" aria-checked="false">Source</button>
      </div>
    `;
    els.canvasStage.appendChild(overlay);
    const box = overlay.querySelector(".rect-box");
    const label = overlay.querySelector(".rect-label");
    const dimT = overlay.querySelector(".dim-top");
    const dimR = overlay.querySelector(".dim-right");
    const dimB = overlay.querySelector(".dim-bottom");
    const dimL = overlay.querySelector(".dim-left");

    function applyAspect() {
      if (aspect === "free") return;
      const cx = (rect.x1 + rect.x2) / 2, cy = (rect.y1 + rect.y2) / 2;
      const cw = rect.x2 - rect.x1, ch = rect.y2 - rect.y1;
      let ratio;
      if (aspect === "1:1") ratio = 1;
      else if (aspect === "16:9") ratio = 16 / 9;
      else if (aspect === "source") ratio = w / h;
      // pick longest dim and adjust the other
      let nw = cw, nh = ch;
      if (cw / ch > ratio) nw = ch * ratio; else nh = cw / ratio;
      rect.x1 = Math.max(0, Math.round(cx - nw / 2));
      rect.y1 = Math.max(0, Math.round(cy - nh / 2));
      rect.x2 = Math.min(w, Math.round(cx + nw / 2));
      rect.y2 = Math.min(h, Math.round(cy + nh / 2));
    }

    function render() {
      const tl = imageToScreen(rect.x1, rect.y1);
      const br = imageToScreen(rect.x2, rect.y2);
      const stage = els.canvasStage.getBoundingClientRect();
      box.style.left = tl.x + "px";
      box.style.top = tl.y + "px";
      box.style.width = (br.x - tl.x) + "px";
      box.style.height = (br.y - tl.y) + "px";
      dimT.style.left = "0"; dimT.style.top = "0"; dimT.style.width = "100%"; dimT.style.height = tl.y + "px";
      dimB.style.left = "0"; dimB.style.bottom = "0"; dimB.style.width = "100%"; dimB.style.height = (stage.height - br.y) + "px";
      dimL.style.left = "0"; dimL.style.top = tl.y + "px"; dimL.style.width = tl.x + "px"; dimL.style.height = (br.y - tl.y) + "px";
      dimR.style.right = "0"; dimR.style.top = tl.y + "px"; dimR.style.width = (stage.width - br.x) + "px"; dimR.style.height = (br.y - tl.y) + "px";
      label.textContent = `${rect.x2 - rect.x1} × ${rect.y2 - rect.y1}`;
    }
    render();
    window.addEventListener("resize", render);
    const renderInterval = setInterval(render, 100); // re-render on zoom/pan

    // Drag handles + box body
    let dragging = null; // {kind: "move"|"handle", handle?, startRect, startMouse}
    overlay.addEventListener("mousedown", (e) => {
      if (e.target.classList.contains("aspect-bar") || e.target.closest(".aspect-bar")) return;
      const handle = e.target.dataset.h;
      const isBox = e.target === box;
      if (handle) dragging = { kind: "handle", handle, startRect: { ...rect }, startX: e.clientX, startY: e.clientY };
      else if (isBox) dragging = { kind: "move", startRect: { ...rect }, startX: e.clientX, startY: e.clientY };
      e.preventDefault();
    });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    function onMove(e) {
      if (!dragging) return;
      const f = els.canvasFrame.getBoundingClientRect();
      const dx = (e.clientX - dragging.startX) * (w / f.width);
      const dy = (e.clientY - dragging.startY) * (h / f.height);
      let r = { ...dragging.startRect };
      if (dragging.kind === "move") {
        const cw = r.x2 - r.x1, ch = r.y2 - r.y1;
        r.x1 = Math.max(0, Math.min(w - cw, r.x1 + dx));
        r.y1 = Math.max(0, Math.min(h - ch, r.y1 + dy));
        r.x2 = r.x1 + cw; r.y2 = r.y1 + ch;
      } else {
        const h_ = dragging.handle;
        if (h_.includes("n")) r.y1 = Math.max(0, Math.min(r.y2 - 10, r.y1 + dy));
        if (h_.includes("s")) r.y2 = Math.max(r.y1 + 10, Math.min(h, r.y2 + dy));
        if (h_.includes("w")) r.x1 = Math.max(0, Math.min(r.x2 - 10, r.x1 + dx));
        if (h_.includes("e")) r.x2 = Math.max(r.x1 + 10, Math.min(w, r.x2 + dx));
      }
      rect = r;
      applyAspect();
      render();
    }
    function onUp() { dragging = null; }

    overlay.querySelectorAll(".aspect-bar button").forEach(btn => {
      btn.onclick = () => {
        aspect = btn.dataset.a;
        overlay.querySelectorAll(".aspect-bar button").forEach(b => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-checked", b === btn ? "true" : "false");
        });
        applyAspect();
        render();
      };
    });
    wireRadiogroup(overlay.querySelector(".aspect-bar"));

    // Keyboard alternative to drag (WCAG 2.5.7 Dragging Movements + 2.1.1).
    // Arrow keys move; Shift+arrow resizes; hold Alt for 10px steps. Focus
    // the rect-box on entry so AT users can immediately operate it.
    box.tabIndex = 0;
    box.focus();
    box.addEventListener("keydown", (e) => {
      const arrow = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (!arrow) return;
      e.preventDefault();
      const stepSize = e.altKey ? 10 : 1;
      const [dxs, dys] = arrow;
      let r = { ...rect };
      if (e.shiftKey) {
        // Resize from the bottom-right corner
        r.x2 = Math.max(r.x1 + 10, Math.min(w, r.x2 + dxs * stepSize));
        r.y2 = Math.max(r.y1 + 10, Math.min(h, r.y2 + dys * stepSize));
      } else {
        const cw = r.x2 - r.x1, ch = r.y2 - r.y1;
        r.x1 = Math.max(0, Math.min(w - cw, r.x1 + dxs * stepSize));
        r.y1 = Math.max(0, Math.min(h - ch, r.y1 + dys * stepSize));
        r.x2 = r.x1 + cw; r.y2 = r.y1 + ch;
      }
      rect = r;
      applyAspect();
      render();
    });

    interactiveMode = {
      op, type: "rect",
      cleanup: () => { clearInterval(renderInterval); window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); },
      commit: async () => {
        try {
          await api(`/api/ops/${op.name}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: state.sessionId,
              left: Math.round(rect.x1), top: Math.round(rect.y1),
              right: Math.round(rect.x2), bottom: Math.round(rect.y2),
            }),
          });
          toast(`${op.label} applied`, "ok");
        } catch (e) { toast(`${op.label} failed: ${e.message}`, "error"); }
      },
    };
    showApplyCancel(
      () => { const m = interactiveMode; m.cleanup(); exitInteractive(true); },
      () => { interactiveMode.cleanup(); exitInteractive(false); },
      "Apply Crop"
    );
  }

  // ---- TEXT mode --------------------------------------------------------
  let cachedFonts = null;
  async function getSystemFonts() {
    if (cachedFonts) return cachedFonts;
    if (window.queryLocalFonts) {
      try {
        const fonts = await window.queryLocalFonts();
        cachedFonts = [...new Set(fonts.map(f => f.family))].sort();
        return cachedFonts;
      } catch (e) { /* user denied or unsupported */ }
    }
    try {
      cachedFonts = await api("/api/fonts");
      return cachedFonts;
    } catch (e) {
      cachedFonts = ["Arial", "Times New Roman", "Courier New", "Verdana", "Georgia", "Tahoma"];
      return cachedFonts;
    }
  }

  async function enterTextMode(op) {
    const fonts = await getSystemFonts();
    const opener = document.activeElement;

    const modal = document.createElement("div");
    modal.id = "text-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-labelledby", "tm-title");
    modal.innerHTML = `
      <div class="text-modal-card" role="document">
        <h3 id="tm-title">Add Text</h3>
        <label for="tm-text">Text
          <textarea id="tm-text" rows="3" placeholder="Your text here" aria-required="true">Hello</textarea>
        </label>
        <label for="tm-font">Font
          <input list="tm-fonts-list" id="tm-font" value="Arial" autocomplete="off" />
          <datalist id="tm-fonts-list">${fonts.map(f => `<option value="${f}">`).join("")}</datalist>
        </label>
        <label for="tm-size">Size
          <input id="tm-size" type="range" min="8" max="400" value="64" aria-valuetext="64 pixels" />
          <span id="tm-size-val" aria-hidden="true">64</span>
          <span aria-hidden="true">px</span>
        </label>
        <label for="tm-color">Color <input id="tm-color" type="color" value="#ffffff" /></label>
        <div class="text-modal-actions">
          <button class="ac-cancel" type="button">Cancel</button>
          <button class="ac-apply" type="button">Place on canvas</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    // Take background out of the focus tree while the modal is open.
    if (els.appShell) els.appShell.inert = true;

    const tmText = modal.querySelector("#tm-text");
    const tmFont = modal.querySelector("#tm-font");
    const tmSize = modal.querySelector("#tm-size");
    const tmSizeVal = modal.querySelector("#tm-size-val");
    const tmColor = modal.querySelector("#tm-color");

    tmSize.oninput = () => {
      tmSizeVal.textContent = tmSize.value;
      tmSize.setAttribute("aria-valuetext", `${tmSize.value} pixels`);
    };

    function cleanup() {
      if (els.appShell) els.appShell.inert = false;
      trap.dispose();
      if (modal.isConnected) modal.remove();
    }

    const trap = trapDialogFocus(modal, opener, () => { cleanup(); exitInteractive(false); });

    modal.querySelector(".ac-cancel").onclick = () => { cleanup(); exitInteractive(false); };
    modal.querySelector(".ac-apply").onclick = () => {
      const cfg = { text: tmText.value, font: tmFont.value, size: parseInt(tmSize.value, 10), color: tmColor.value };
      cleanup();
      placeTextOverlay(op, cfg);
    };
  }

  function placeTextOverlay(op, cfg) {
    // Initial position: center of image
    let pos = { x: state.naturalSize.w * 0.3, y: state.naturalSize.h * 0.45 };

    const overlay = document.createElement("div");
    overlay.id = "interactive-overlay";
    overlay.className = "text-overlay";
    overlay.innerHTML = `<div class="text-drag" tabindex="0" role="application"
      aria-label="Text placement — drag with mouse or use arrow keys to position; hold Alt for 10px steps"
      style="font-family: ${cfg.font}; color: ${cfg.color}; white-space: pre;">${cfg.text.replace(/</g,"&lt;")}</div>`;
    els.canvasStage.appendChild(overlay);
    const drag = overlay.querySelector(".text-drag");
    drag.focus();

    function render() {
      const f = els.canvasFrame.getBoundingClientRect();
      const scaleX = f.width / state.naturalSize.w;
      const tl = imageToScreen(pos.x, pos.y);
      drag.style.left = tl.x + "px";
      drag.style.top = tl.y + "px";
      drag.style.fontSize = (cfg.size * scaleX) + "px";
    }
    render();
    const renderInterval = setInterval(render, 100);
    window.addEventListener("resize", render);

    // Drag to reposition
    let dragging = null;
    drag.addEventListener("mousedown", (e) => {
      dragging = { startX: e.clientX, startY: e.clientY, startPos: { ...pos } };
      e.preventDefault();
    });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    function onMove(e) {
      if (!dragging) return;
      const f = els.canvasFrame.getBoundingClientRect();
      const dx = (e.clientX - dragging.startX) * (state.naturalSize.w / f.width);
      const dy = (e.clientY - dragging.startY) * (state.naturalSize.h / f.height);
      pos.x = dragging.startPos.x + dx;
      pos.y = dragging.startPos.y + dy;
      render();
    }
    function onUp() { dragging = null; }

    // Keyboard nudge — arrow keys move; Alt for 10px steps. Same WCAG 2.5.7
    // requirement as the crop overlay.
    function onKeyDown(e) {
      const arrow = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (!arrow) return;
      e.preventDefault();
      const stepSize = e.altKey ? 10 : 1;
      pos.x = Math.max(0, Math.min(state.naturalSize.w, pos.x + arrow[0] * stepSize));
      pos.y = Math.max(0, Math.min(state.naturalSize.h, pos.y + arrow[1] * stepSize));
      render();
    }
    drag.addEventListener("keydown", onKeyDown);

    interactiveMode = {
      op, type: "text",
      cleanup: () => {
        clearInterval(renderInterval);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        drag.removeEventListener("keydown", onKeyDown);
      },
      commit: async () => {
        try {
          await api(`/api/ops/${op.name}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: state.sessionId,
              text: cfg.text, font: cfg.font, size: cfg.size, color: cfg.color,
              x: Math.round(pos.x), y: Math.round(pos.y),
            }),
          });
          toast("Text added", "ok");
        } catch (e) { toast("Text failed: " + e.message, "error"); }
      },
    };
    showApplyCancel(
      () => { const m = interactiveMode; m.cleanup(); exitInteractive(true); },
      () => { interactiveMode.cleanup(); exitInteractive(false); },
      "Bake into image"
    );
  }

  // ---- Drag & drop -------------------------------------------------------
  function bindDragDrop() {
    let depth = 0;
    window.addEventListener("dragenter", (e) => {
      e.preventDefault(); depth++;
      if (e.dataTransfer.types.includes("Files")) els.canvasArea.classList.add("drag-over");
    });
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("dragleave", () => {
      depth--; if (depth <= 0) { els.canvasArea.classList.remove("drag-over"); depth = 0; }
    });
    window.addEventListener("drop", (e) => {
      e.preventDefault(); depth = 0;
      els.canvasArea.classList.remove("drag-over");
      const f = e.dataTransfer.files[0];
      if (f) uploadFile(f);
    });
  }

  // ---- Undo / Redo / Clear ----------------------------------------------
  async function doUndo() {
    if (!state.sessionId || els.undoBtn.disabled) return;
    try { await api(`/api/sessions/${state.sessionId}/undo`, { method: "POST" }); }
    catch (e) { toast("Undo failed: " + e.message, "error"); }
  }
  async function doRedo() {
    if (!state.sessionId || els.redoBtn.disabled) return;
    try { await api(`/api/sessions/${state.sessionId}/redo`, { method: "POST" }); }
    catch (e) { toast("Redo failed: " + e.message, "error"); }
  }
  async function doClear() {
    if (!state.sessionId) return;
    const ok = await alertConfirm({
      title: "Clear all edits?",
      message: "This reverts the image to the original. Edit history will be lost.",
      confirmLabel: "Clear edits",
      cancelLabel: "Cancel",
      danger: true,
    });
    if (!ok) return;
    try { await api(`/api/sessions/${state.sessionId}/clear`, { method: "POST" }); toast("Cleared", "ok"); }
    catch (e) { toast("Clear failed: " + e.message + ". Try again or refresh.", "error"); }
  }

  // ---- Top bar wiring ----------------------------------------------------
  function bindTopbar() {
    els.uploadBtn.onclick = () => els.fileInput.click();
    els.fileInput.onchange = (e) => { const f = e.target.files[0]; if (f) uploadFile(f); };
    els.undoBtn.onclick = doUndo;
    els.redoBtn.onclick = doRedo;
    els.clearBtn.onclick = doClear;
    els.copyBtn.onclick = async () => {
      if (els.canvasFrame.style.display === "none") return toast("Nothing to copy", "error");
      try {
        // Image src is a /sessions_files/* URL — needs the auth cookie.
        const blob = await fetch(els.canvasImg.src, { credentials: "same-origin" }).then(r => r.blob());
        await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
        toast("Copied to clipboard", "ok");
      } catch (e) { toast("Copy failed: " + e.message, "error"); }
    };
    els.downloadBtn.onclick = () => {
      if (els.canvasFrame.style.display === "none") return toast("Nothing to download", "error");
      const a = document.createElement("a");
      a.href = els.canvasImg.src;
      a.download = "picasso-" + Date.now() + "." + (state.fileMeta.format.toLowerCase() || "png");
      a.click();
    };
    els.tweaksBtn.onclick = () => toggleTweaks();
    els.searchTrigger.onclick = (e) => { if (e.target !== els.searchInput) openPalette(); };
    els.searchInput.onfocus = () => openPalette();

    els.toolbarTabs.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-mode]");
      if (!b) return;
      els.toolbarTabs.querySelectorAll("button").forEach(x => {
        x.classList.remove("active");
        x.setAttribute("aria-selected", "false");
      });
      b.classList.add("active");
      b.setAttribute("aria-selected", "true");
      state.toolFilter = b.dataset.mode;
      renderOps();
    });
    // Wire arrow-key navigation for the tablist (radiogroup-style pattern).
    wireRadiogroup(els.toolbarTabs);

    els.sessionCopy.onclick = () => {
      if (state.sessionId) {
        navigator.clipboard.writeText(state.sessionId);
        toast("Session ID copied", "ok");
      }
    };
    els.mcpLink.onclick = () => {
      navigator.clipboard.writeText(els.mcpUrl.textContent);
      toast("MCP URL copied", "ok");
    };
  }

  // ---- Command palette ---------------------------------------------------
  let paletteIdx = 0;
  let paletteHits = [];
  let paletteOpener = null; // element to return focus to on close

  function openPalette() {
    paletteOpener = document.activeElement;
    els.paletteOverlay.hidden = false;
    els.paletteOverlay.classList.add("open");
    els.paletteInput.value = "";
    els.paletteInput.setAttribute("aria-expanded", "true");
    els.paletteInput.focus();
    renderPalette("");
  }
  function closePalette() {
    els.paletteOverlay.classList.remove("open");
    els.paletteOverlay.hidden = true;
    els.paletteInput.setAttribute("aria-expanded", "false");
    els.paletteInput.removeAttribute("aria-activedescendant");
    // Return focus to whatever opened the palette (Ctrl+K from anywhere,
    // click on the search trigger, etc.). Falls back to the search trigger
    // so keyboard users land somewhere predictable.
    const restore = paletteOpener || els.searchTrigger;
    paletteOpener = null;
    if (restore && typeof restore.focus === "function") restore.focus();
  }
  function renderPalette(q) {
    const all = Object.values(state.opsByName);
    const ql = q.toLowerCase();
    paletteHits = all.filter(o =>
      !q || o.name.toLowerCase().includes(ql) || o.label.toLowerCase().includes(ql) ||
      (o.description || "").toLowerCase().includes(ql) || o.category.toLowerCase().includes(ql)
    ).slice(0, 50);
    paletteIdx = 0;
    els.paletteResults.innerHTML = "";
    paletteHits.forEach((op, i) => {
      const r = document.createElement("li");
      r.id = `palette-row-${i}`;
      r.className = "palette-row" + (i === 0 ? " active" : "");
      r.setAttribute("role", "option");
      r.setAttribute("aria-selected", i === 0 ? "true" : "false");
      r.innerHTML = `
        <span class="icon" aria-hidden="true">${window.renderOpIcon(op.name, 14)}</span>
        <span class="name">${op.label}</span>
        <span class="cat" aria-label="category ${op.category}">${op.category}</span>
      `;
      r.onmouseenter = () => setPaletteIndex(i);
      r.onclick = () => commitPalette();
      els.paletteResults.appendChild(r);
    });
    // Keep aria-activedescendant pointed at the highlighted row so SR
    // users hear which result Enter would commit.
    if (paletteHits.length) {
      els.paletteInput.setAttribute("aria-activedescendant", "palette-row-0");
    } else {
      els.paletteInput.removeAttribute("aria-activedescendant");
    }
  }

  function setPaletteIndex(i) {
    paletteIdx = i;
    const rows = els.paletteResults.querySelectorAll(".palette-row");
    rows.forEach((row, idx) => {
      const active = idx === i;
      row.classList.toggle("active", active);
      row.setAttribute("aria-selected", active ? "true" : "false");
    });
    els.paletteInput.setAttribute("aria-activedescendant", `palette-row-${i}`);
  }
  function commitPalette() {
    const op = paletteHits[paletteIdx];
    closePalette();
    if (!op) return;
    // find the visible button to anchor the popover; fallback to search trigger
    const btn = document.querySelector(`.op-btn[data-op-name="${op.name}"]`) || els.searchTrigger;
    btn.scrollIntoView && btn.scrollIntoView({ block: "center" });
    setTimeout(() => openPopover(op, btn), 50);
  }
  function bindPalette() {
    els.paletteInput.addEventListener("input", e => renderPalette(e.target.value));
    els.paletteInput.addEventListener("keydown", e => {
      if (e.key === "Escape") { e.stopPropagation(); return closePalette(); }
      if (e.key === "Enter") return commitPalette();
      if (e.key === "ArrowDown") {
        setPaletteIndex(Math.min(paletteHits.length - 1, paletteIdx + 1));
        scrollActiveIntoView();
        e.preventDefault();
      }
      if (e.key === "ArrowUp") {
        setPaletteIndex(Math.max(0, paletteIdx - 1));
        scrollActiveIntoView();
        e.preventDefault();
      }
    });
    els.paletteOverlay.addEventListener("click", (e) => {
      if (e.target === els.paletteOverlay) closePalette();
    });
    function scrollActiveIntoView() {
      const active = els.paletteResults.querySelector(".palette-row.active");
      if (active) active.scrollIntoView({ block: "nearest" });
    }
  }

  // ---- Tweaks panel ------------------------------------------------------
  function toggleTweaks() {
    const isOpen = els.tweaks.classList.toggle("open");
    // Keep the `hidden` attribute in sync with visibility — per HTML spec
    // SRs ignore [hidden] elements regardless of CSS display, so leaving
    // hidden on while .open visually shows the panel hides it from AT.
    els.tweaks.hidden = !isOpen;
    els.tweaksBtn.classList.toggle("active", isOpen);
    els.tweaksBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    if (isOpen && !els.tweaksBody.children.length) renderTweaks();
    // Keyboard parity: focus into the panel on open, return to the trigger
    // on close. Non-modal so background stays interactive — no focus trap.
    if (isOpen) {
      (els.tweaksClose || els.tweaks).focus();
    } else {
      els.tweaksBtn.focus();
    }
  }

  function applyAccent(name) {
    const a = ACCENTS[name];
    if (!a) return;
    document.documentElement.style.setProperty("--accent", a.accent);
    document.documentElement.style.setProperty("--accent-2", a.accent2);
    document.documentElement.style.setProperty("--accent-soft", a.soft);
    state.accent = name;
    localStorage.setItem("picasso.accent", name);
  }
  function applyDensity(d) {
    document.body.dataset.density = d;
    state.density = d;
    localStorage.setItem("picasso.density", d);
  }
  function applyShowLabels(b) {
    document.body.dataset.showLabels = b ? "true" : "false";
    state.showLabels = b;
    localStorage.setItem("picasso.labels", b ? "1" : "0");
  }

  function renderTweaks() {
    els.tweaksBody.innerHTML = "";

    const sec = (title) => {
      const s = document.createElement("div");
      s.className = "tweak-section";
      s.innerHTML = `<h5>${title}</h5>`;
      els.tweaksBody.appendChild(s);
      return s;
    };
    const row = (parent, label, ctrl) => {
      const r = document.createElement("div");
      r.className = "tweak-row";
      r.innerHTML = `<label>${label}</label>`;
      const c = document.createElement("div"); c.className = "ctrl";
      if (typeof ctrl === "string") c.innerHTML = ctrl; else c.appendChild(ctrl);
      r.appendChild(c);
      parent.appendChild(r);
    };

    // Accent color — radiogroup of <button> swatches so keyboard users can
    // Tab in and Space/Enter to select. Previous <div onclick> was unreachable.
    const s1 = sec("Accent");
    const swatchRow = document.createElement("div");
    swatchRow.className = "swatch-row";
    swatchRow.setAttribute("role", "radiogroup");
    swatchRow.setAttribute("aria-label", "Accent color");
    Object.keys(ACCENTS).forEach(name => {
      const sw = document.createElement("button");
      sw.type = "button";
      sw.className = "swatch" + (state.accent === name ? " active" : "");
      sw.style.background = ACCENTS[name].accent;
      sw.title = name;
      sw.setAttribute("role", "radio");
      sw.setAttribute("aria-checked", state.accent === name ? "true" : "false");
      sw.setAttribute("aria-label", `Accent color: ${name}`);
      sw.onclick = () => {
        applyAccent(name);
        swatchRow.querySelectorAll(".swatch").forEach(x => {
          x.classList.remove("active");
          x.setAttribute("aria-checked", "false");
        });
        sw.classList.add("active");
        sw.setAttribute("aria-checked", "true");
      };
      swatchRow.appendChild(sw);
    });
    row(s1, "Theme color", swatchRow);
    wireRadiogroup(swatchRow);

    // Density
    const s2 = sec("Density");
    const seg = document.createElement("div");
    seg.className = "seg-mini";
    seg.setAttribute("role", "radiogroup");
    seg.setAttribute("aria-label", "Layout density");
    ["compact","default","comfy"].forEach(d => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", state.density === d ? "true" : "false");
      b.textContent = d;
      if (state.density === d) b.classList.add("active");
      b.onclick = () => {
        applyDensity(d);
        seg.querySelectorAll("button").forEach(x => {
          x.classList.remove("active");
          x.setAttribute("aria-checked", "false");
        });
        b.classList.add("active");
        b.setAttribute("aria-checked", "true");
      };
      seg.appendChild(b);
    });
    row(s2, "Layout density", seg);
    wireRadiogroup(seg);

    // Labels under icons
    const s3 = sec("Toolbar");
    const labelToggle = makeToggle(state.showLabels, (v) => applyShowLabels(v), "Show op labels under icons");
    row(s3, "Show op labels", labelToggle);

    const checkerToggle = makeToggle(state.checker, (v) => {
      state.checker = v;
      els.canvasStage.classList.toggle("checker", v);
    }, "Transparency checker");
    const sCanvas = sec("Canvas");
    row(sCanvas, "Transparency checker", checkerToggle);

    const compareToggle = makeToggle(state.showCompare, (v) => {
      if (v !== state.showCompare) toggleCompare();
    }, "Before/after compare");
    row(sCanvas, "Before/after compare", compareToggle);

    // Reset
    const sZ = sec("Workspace");
    const resetBtn = document.createElement("button");
    resetBtn.className = "pill-btn";
    resetBtn.textContent = "Reset view";
    resetBtn.onclick = () => fitCanvas();
    row(sZ, "Camera", resetBtn);
  }

  function makeToggle(value, onChange, label) {
    // <button role="switch"> is the right semantic for a binary toggle —
    // SR users hear "switch, on/off" and can flip it with Space/Enter.
    // The previous <div> implementation was invisible to AT and unreachable
    // by keyboard.
    const t = document.createElement("button");
    t.type = "button";
    t.className = "toggle" + (value ? " on" : "");
    t.setAttribute("role", "switch");
    t.setAttribute("aria-checked", value ? "true" : "false");
    if (label) t.setAttribute("aria-label", label);
    function flip() {
      const nv = !t.classList.contains("on");
      t.classList.toggle("on", nv);
      t.setAttribute("aria-checked", nv ? "true" : "false");
      onChange(nv);
    }
    t.addEventListener("click", flip);
    t.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        flip();
      }
    });
    return t;
  }

  // ---- Tweaks drag -------------------------------------------------------
  function bindTweaksDrag() {
    let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
    els.tweaksHead.addEventListener("mousedown", (e) => {
      if (e.target.closest(".close")) return;
      dragging = true;
      const r = els.tweaks.getBoundingClientRect();
      sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
      els.tweaks.style.right = "auto"; els.tweaks.style.bottom = "auto";
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      els.tweaks.style.left = (ox + e.clientX - sx) + "px";
      els.tweaks.style.top  = (oy + e.clientY - sy) + "px";
    });
    window.addEventListener("mouseup", () => dragging = false);
    els.tweaksClose.onclick = () => toggleTweaks();
  }

  // ---- Keyboard shortcuts ------------------------------------------------
  function bindKeys() {
    window.addEventListener("keydown", (e) => {
      const inField = ["INPUT","TEXTAREA","SELECT"].includes(e.target.tagName);
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); openPalette(); return; }
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && !e.shiftKey) { e.preventDefault(); doUndo(); return; }
      if ((e.metaKey || e.ctrlKey) && (e.key === "y" || (e.key === "z" && e.shiftKey))) { e.preventDefault(); doRedo(); return; }
      if (e.key === "Escape") {
        if (els.paletteOverlay.classList.contains("open")) return closePalette();
        if (openPop) return closePopover();
        if (interactiveMode) { if (interactiveMode.cleanup) interactiveMode.cleanup(); return exitInteractive(false); }
        if (els.tweaks.classList.contains("open")) return toggleTweaks();
      }
      if (inField) return;
      if (e.key === "+" || e.key === "=") setZoom(state.zoom * 1.25);
      if (e.key === "-") setZoom(state.zoom / 1.25);
      if (e.key === "f" || e.key === "F") fitCanvas();
      if (e.key === "1") setZoom(1);
      if (e.key === "0") fitCanvas();
    });
  }

  // ---- Restore preferences ----------------------------------------------
  function restorePrefs() {
    const a = localStorage.getItem("picasso.accent"); if (a) applyAccent(a);
    const d = localStorage.getItem("picasso.density"); if (d) applyDensity(d);
    const l = localStorage.getItem("picasso.labels"); if (l) applyShowLabels(l === "1");
    // Detect host for MCP URL
    els.mcpUrl.textContent = `${location.origin}/mcp`;
  }

  // ---- MOCK BACKEND (preview mode only) ---------------------------------
  // Used only when /api/ops returns 404 (i.e. running standalone).
  function mockUploadFile(file) {
    const url = URL.createObjectURL(file);
    const sess = {
      id: "demo_" + Math.random().toString(36).slice(2, 10),
      original: url,
      current_image: url,
      history: [],
    };
    onSessionCreated(sess);
  }
  function mockApplyOp(op, values) {
    if (!state.sessionData) return;
    const newSess = {
      ...state.sessionData,
      history: [...state.sessionData.history, {
        op: op.name, params: values, output: state.sessionData.current_image,
        ts: Date.now() / 1000, note: op.label,
      }],
    };
    state.activeStep = newSess.history.length - 1;
    renderHistory(newSess);
    toast(`${op.label} (preview-only — would apply on backend)`, "ok");
  }

  // ---- Init --------------------------------------------------------------
  // Subscribe to the process-wide event channel so this tab learns about
  // sessions created elsewhere (typically via MCP / Claude Desktop). Auto-
  // switches to the new session if the tab isn't currently bound to one,
  // or shows a toast offering to switch if it is.
  function subscribeGlobalEvents() {
    if (state.isMock) return;
    const es = new EventSource("/api/events");
    es.onmessage = (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch (_) { return; }
      if (data.type !== "session_created") return;
      const newSid = data.session_id;
      if (!newSid || newSid === state.sessionId) return;
      // No active session OR same as one we just landed on → auto-switch.
      // Otherwise toast "click to switch" to avoid yanking the user mid-edit.
      if (!state.sessionId) {
        loadSessionById(newSid);
      } else {
        showSwitchPill(newSid);
      }
    };
  }

  async function loadSessionById(sid) {
    try {
      const sess = await api(`/api/sessions/${sid}`);
      onSessionCreated(sess);
      subscribeSSE(sess.id);
      toast(`Switched to new session`, "ok");
    } catch (e) {
      toast(`Couldn't load session: ${e.message}`, "error");
    }
  }

  function showSwitchPill(sid) {
    // Reuse the toast host but make it click-to-action.
    const t = document.createElement("div");
    t.className = "toast";
    t.style.cursor = "pointer";
    t.innerHTML = `New session from Claude — <strong>click to open</strong>`;
    t.onclick = () => { t.remove(); loadSessionById(sid); };
    els.toastHost.appendChild(t);
    setTimeout(() => { if (t.isConnected) t.remove(); }, 15000);
  }

  async function init() {
    // Auth bootstrap MUST happen before any /api/* call. Redeems the
    // ?launch nonce (if present) for the bearer token + cookie.
    await bootstrapAuth();
    bindCanvasTools();
    bindDragDrop();
    bindTopbar();
    bindPalette();
    bindKeys();
    bindTweaksDrag();
    restorePrefs();
    await loadOps();
    subscribeGlobalEvents();

    // Restore last session from localStorage if the backend still has it
    if (!state.isMock) {
      const lastId = (() => { try { return localStorage.getItem("picasso.lastSession"); } catch (e) { return null; } })();
      if (lastId) {
        try {
          const sess = await api(`/api/sessions/${lastId}`);
          onSessionCreated(sess);
          subscribeSSE(sess.id);
          toast("Session restored", "ok");
        } catch (e) {
          // 404 = server forgot it (restart, etc.) — clear stale id
          try { localStorage.removeItem("picasso.lastSession"); } catch (_) {}
        }
      }
    }

    // Auto-load demo image when in preview mode and the host supplied one
    if (state.isMock && window.__DEMO_IMAGE) {
      const sess = {
        id: "demo_session",
        original: window.__DEMO_IMAGE,
        current_image: window.__DEMO_IMAGE,
        history: window.__DEMO_HISTORY || [],
      };
      onSessionCreated(sess);
    }

    window.addEventListener("resize", () => {
      if (els.canvasFrame.style.display !== "none") fitCanvas();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
