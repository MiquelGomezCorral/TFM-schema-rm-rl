/*
 * Shared Reward Machine graph interactions, used by the web UI (Dash loads this
 * asset) and inlined into exported HTML pages, so both behave the same.
 *
 * window.rmGraph.attach(cy, container) wires one Cytoscape instance:
 *   - hovering an edge highlights it; hovering a state highlights its outgoing edges;
 *   - tapping an edge opens the transition panel inside `container`, which must be
 *     a positioned element (the panel is absolutely placed in its top-left corner);
 *   - the close button, tapping a state or the empty canvas closes it.
 * attach returns `{ close }` and wires an instance only once, so the web UI can call it
 * after every elements update and close the panel itself when the graph really changed.
 *
 * window.rmGraph.guardFrameWheel(cy, container) is for pages that may sit in a frame
 * (the HTML export): there a plain wheel scrolls the surrounding page and Ctrl or Cmd +
 * wheel zooms the graph, with a short hint, like embedded maps. Outside a frame it does
 * nothing, so the page keeps plain wheel zoom.
 *
 * The highlight look lives in the Cytoscape stylesheet (`.rm-hover`, see
 * HOVER_CLASS in visualization.py), the panel and hint look in rm_graph.css.
 */
(function () {
  "use strict";

  const HOVER_CLASS = "rm-hover";
  const HINT_MILLISECONDS = 1200;
  const attached = new WeakMap();

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function stateName(id) {
    return "u" + String(id).replace(/^state-/, "");
  }

  function literalChip(literal) {
    const text = String(literal);
    const negated = text.startsWith("!") ? " rm-graph-literal-negated" : "";
    return element("span", "rm-graph-literal" + negated, text);
  }

  function caseCard(formalCase, index) {
    const reward = Number(formalCase.reward) || 0;
    const sign = reward > 0 ? "positive" : reward < 0 ? "negative" : "zero";
    const condition = [].concat(formalCase.condition || []);

    const head = element("div", "rm-graph-case-head");
    head.append(
      element("span", "rm-graph-case-name", "Case " + (index + 1)),
      element("span", "rm-graph-reward-" + sign, "· r=" + formalCase.reward_label)
    );
    const literals = element("div", "rm-graph-literals");
    literals.append(...(condition.length ? condition : ["true"]).map(literalChip));

    const card = element("div", "rm-graph-case");
    card.append(head, literals);
    return card;
  }

  function panelHead(edge, caseCount) {
    const head = element("div", "rm-graph-head");
    head.append(
      element(
        "span",
        "rm-graph-title",
        stateName(edge.data("source")) + " → " + stateName(edge.data("target"))
      ),
      element(
        "span",
        "rm-graph-count",
        caseCount + " formal case" + (caseCount === 1 ? "" : "s")
      )
    );
    return head;
  }

  function attach(cy, container) {
    const existing = attached.get(cy);
    if (existing) {
      return existing;
    }

    const panel = element("div", "rm-graph-panel");
    const content = element("div", "rm-graph-content");
    const closeButton = element("button", "rm-graph-close", "Close");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close transition details");
    panel.hidden = true;
    panel.append(content, closeButton);
    container.append(panel);

    function close() {
      panel.hidden = true;
      content.replaceChildren();
      cy.edges().unselect();
    }

    function open(edge) {
      const cases = edge.data("cases");
      if (!Array.isArray(cases)) {
        return;
      }
      content.replaceChildren(panelHead(edge, cases.length), ...cases.map(caseCard));
      panel.scrollTop = 0;
      panel.hidden = false;
    }

    function clearHover() {
      cy.elements().removeClass(HOVER_CLASS);
      cy.container().style.cursor = "";
    }

    cy.on("mouseover", "edge", (event) => {
      event.target.addClass(HOVER_CLASS);
      cy.container().style.cursor = "pointer";
    });
    cy.on("mouseover", "node", (event) => {
      event.target.outgoers("edge").addClass(HOVER_CLASS);
    });
    // Also fires when the pointer leaves the canvas straight from an element.
    cy.on("mouseout", clearHover);
    cy.on("tap", "edge", (event) => open(event.target));
    cy.on("tap", "node", close);
    cy.on("tap", (event) => {
      if (event.target === cy) {
        close();
      }
    });
    closeButton.addEventListener("click", close);

    const controller = { close };
    attached.set(cy, controller);
    return controller;
  }

  function guardFrameWheel(cy, container) {
    if (window.self === window.top) {
      return;
    }

    const hint = element("div", "rm-graph-hint", "Ctrl + scroll to zoom");
    hint.hidden = true;
    hint.setAttribute("role", "status");
    container.append(hint);

    let hideTimer;
    cy.userZoomingEnabled(false);
    // Capture on the container so this runs before Cytoscape's own wheel handler,
    // which only calls preventDefault (and so blocks page scrolling) while zoom is on.
    container.addEventListener(
      "wheel",
      (event) => {
        const zoom = event.ctrlKey || event.metaKey;
        cy.userZoomingEnabled(zoom);
        clearTimeout(hideTimer);
        hint.hidden = zoom;
        if (!zoom) {
          hideTimer = setTimeout(() => {
            hint.hidden = true;
          }, HINT_MILLISECONDS);
        }
      },
      { capture: true, passive: true }
    );
  }

  window.rmGraph = { attach, guardFrameWheel };
})();
