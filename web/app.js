const state = {
  data: null,
  search: "",
  cost: "all",
  selected: null,
  pinnedUnitId: null,
  unavailableUnitIds: new Set(),
};
const SVG_NS = "http://www.w3.org/2000/svg";
const web = document.querySelector("#trait-web");
const graphLayout = document.querySelector(".graph-layout");
const status = document.querySelector("#dataset-status");
const selection = document.querySelector("#selection");
const teamCodeInput = document.querySelector("#team-code-input");
const teamCodeMessage = document.querySelector("#team-code-message");
const teamSlotsElement = document.querySelector("#team-slots");
const activeTraitsElement = document.querySelector("#active-traits");
const inactiveTraitsElement = document.querySelector("#inactive-traits");
const recommendationListElement = document.querySelector("#recommendation-list");
const importCodeButton = document.querySelector("#import-code");
const addSlotButton = document.querySelector("#add-slot");
const exportCodeButton = document.querySelector("#export-code");
const EMPTY_CODE = 0;
const teamState = { slots: [] };
let recommendationWorker = null;
let recommendationWorkerFailed = false;
let recommendationRequestId = 0;
let latestRecommendationPayload = null;

function teamCodeFormat() {
  return state.data?.teamCode || {
    enabled: false,
    prefix: "",
    setId: "",
    slotCount: 0,
    localSlotLimit: state.data?.dataset?.local_board_slot_limit || 15,
  };
}

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, value);
  }
  return element;
}

function htmlElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function icon(path, alt, className = "selected-icon") {
  const image = document.createElement("img");
  image.src = path;
  image.alt = alt;
  image.className = className;
  image.loading = "lazy";
  image.addEventListener("error", () => { image.hidden = true; });
  return image;
}

function angleFor(index, total, offset = -Math.PI / 2) {
  return offset + (index / Math.max(total, 1)) * Math.PI * 2;
}

function pointAt(radius, angle) {
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function plannerCandidates(plannerCode) {
  return state.data.units.filter((unit) => unit.plannerCode === plannerCode);
}

function isEmptySlot(slot) {
  return slot.plannerCode === EMPTY_CODE && !slot.unitId && !slot.candidates.length;
}

function unitForId(unitId) {
  return unitId ? state.data.units.find((unit) => unit.id === unitId) : null;
}

function boardSlotsForUnit(unit) {
  return Number.isInteger(unit?.boardSlots) && unit.boardSlots > 0 ? unit.boardSlots : 1;
}

function plannerSlotUsage() {
  return teamState.slots.reduce(
    (total, slot) => total + boardSlotsForUnit(unitForId(slot.unitId)),
    0,
  );
}

function uniqueGroupForUnit(unit) {
  return typeof unit?.uniqueGroup === "string" && unit.uniqueGroup ? unit.uniqueGroup : null;
}

function uniqueGroupsForSlot(slot) {
  const candidates = slot.unitId ? [unitForId(slot.unitId)] : slot.candidates;
  return new Set(candidates.map(uniqueGroupForUnit).filter(Boolean));
}

function plannerHasUniqueGroup(group) {
  if (!group) return false;
  return teamState.slots.some((slot) => uniqueGroupsForSlot(slot).has(group));
}

function parseTeamCode(rawCode) {
  const format = teamCodeFormat();
  if (!format.enabled) throw new Error("Team code import/export is not configured for this catalog.");
  const code = rawCode.trim().toUpperCase();
  if (!code.startsWith(format.prefix.toUpperCase())) throw new Error(`Team code must start with ${format.prefix}.`);
  if (!code.endsWith(format.setId.toUpperCase())) throw new Error(`This tool currently accepts ${format.setId} codes.`);
  const payload = code.slice(format.prefix.length, -format.setId.length);
  if (payload.length !== format.slotCount * 3) throw new Error(`This team code must contain exactly ${format.slotCount} slots.`);
  const slots = [];
  for (let index = 0; index < payload.length; index += 3) {
    const rawPlannerCode = payload.slice(index, index + 3);
    const plannerCode = Number.parseInt(rawPlannerCode, 16);
    if (Number.isNaN(plannerCode)) throw new Error(`Invalid planner ID: ${rawPlannerCode}`);
    const candidates = plannerCandidates(plannerCode);
    slots.push({
      plannerCode,
      unitId: candidates.length === 1 ? candidates[0].id : null,
      candidates,
    });
  }
  while (slots.length && isEmptySlot(slots[slots.length - 1])) slots.pop();
  return slots;
}

function codeForSlot(slot) {
  if (slot.unitId) {
    const unit = state.data.units.find((item) => item.id === slot.unitId);
    if (!unit || unit.plannerCode === null) throw new Error(`No planner ID exists for ${slot.unitId}.`);
    return unit.plannerCode;
  }
  return slot.plannerCode;
}

function encodeTeamSlots() {
  const format = teamCodeFormat();
  if (!format.enabled) return "";
  if (!teamState.slots.length) return "";
  const exportSlots = teamState.slots.slice(0, format.slotCount);
  while (exportSlots.length < format.slotCount) {
    exportSlots.push({ plannerCode: EMPTY_CODE, unitId: null, candidates: [] });
  }
  const payload = exportSlots.map((slot) => codeForSlot(slot).toString(16).toUpperCase().padStart(3, "0")).join("");
  return `${format.prefix.toUpperCase()}${payload}${format.setId}`;
}

function setTeamMessage(text, kind = "") {
  teamCodeMessage.textContent = text;
  teamCodeMessage.className = `team-code-message${kind ? ` is-${kind}` : ""}`;
}

function renderTeamSlots() {
  teamSlotsElement.replaceChildren();
  for (const [index, slot] of teamState.slots.entries()) {
    const wrapper = document.createElement("div");
    wrapper.className = "team-slot";
    const tile = document.createElement("button");
    tile.type = "button";
    const selectedUnit = slot.unitId
      ? state.data.units.find((unit) => unit.id === slot.unitId)
      : slot.candidates[0];
    tile.className = `team-slot-tile${selectedUnit ? ` cost-${selectedUnit.cost}` : ""}`;
    tile.setAttribute(
      "aria-label",
      selectedUnit ? `${selectedUnit.name}; click to clear this tile` : "Empty planner tile",
    );
    tile.title = selectedUnit ? `${selectedUnit.name} — click to clear` : "Empty tile";
    if (selectedUnit) {
      tile.append(icon(selectedUnit.icon, selectedUnit.name, "slot-icon"));
    } else {
      tile.append(htmlElement("span", "slot-empty", slot.plannerCode ? "?" : "+"));
    }
    const clearSlot = () => {
      teamState.slots[index] = { plannerCode: EMPTY_CODE, unitId: null, candidates: [] };
      renderTeamSlots();
      updateExportCode();
      setTeamMessage("Cleared planner tile. Double-click a unit in the web to fill it.", "success");
    };
    const removeBlankSlot = () => {
      teamState.slots.splice(index, 1);
      renderTeamSlots();
      updateExportCode();
      setTeamMessage("Removed blank planner slot.", "success");
    };
    tile.addEventListener("click", clearSlot);
    tile.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      if (isEmptySlot(slot)) {
        removeBlankSlot();
      } else {
        clearSlot();
      }
    });
    wrapper.append(tile);
    teamSlotsElement.append(wrapper);
  }
  renderTeamTraits();
  renderRecommendations();
  const limit = teamCodeFormat().localSlotLimit;
  const usedSlots = plannerSlotUsage();
  addSlotButton.disabled = usedSlots >= limit;
  addSlotButton.textContent = `+ Add blank slot (${usedSlots}/${limit})`;
}

function traitActivationThresholds(trait) {
  const thresholds = trait.activationThresholds;
  if (Array.isArray(thresholds)) {
    const valid = thresholds.filter((threshold) => Number.isInteger(threshold) && threshold > 0);
    if (valid.length) return valid;
  }
  const fallback = state.data?.dataset?.default_trait_activation_threshold;
  return [Number.isInteger(fallback) && fallback > 0 ? fallback : 2];
}

function isTraitActive(trait, count) {
  return traitActivationThresholds(trait).some((threshold) => count >= threshold);
}

function plannerUnits() {
  const unitsById = new Map();
  for (const slot of teamState.slots) {
    const units = (() => {
      if (slot.unitId) {
        return state.data.units.filter((unit) => unit.id === slot.unitId);
      }
      if (slot.candidates.length === 1) {
        return slot.candidates;
      }
      return [];
    })();
    for (const unit of units) unitsById.set(unit.id, unit);
  }
  return [...unitsById.values()];
}

function makeTeamTraitBadge(trait, count, active) {
  const badge = document.createElement("button");
  badge.type = "button";
  badge.className = `team-trait-badge${active ? " is-active" : " is-inactive"}`;
  const thresholds = traitActivationThresholds(trait);
  const nextThreshold = thresholds.find((threshold) => threshold > count);
  const stateLabel = active
    ? "active"
    : `not active; needs ${nextThreshold || thresholds[0]} units`;
  badge.setAttribute("aria-label", `${trait.name}, ${count}, ${stateLabel}`);
  badge.title = `${trait.name}: ${count} ${stateLabel}`;
  badge.append(icon(trait.icon, `${trait.name} icon`, "team-trait-icon"));
  badge.append(htmlElement("span", "team-trait-count", String(count)));
  badge.addEventListener("click", () => selectTrait(trait));
  return badge;
}

function renderTraitGroup(element, entries, emptyText) {
  element.replaceChildren();
  if (!entries.length) {
    element.append(htmlElement("span", "team-traits-empty", emptyText));
    return;
  }
  for (const { trait, count, active } of entries) {
    element.append(makeTeamTraitBadge(trait, count, active));
  }
}

function renderTeamTraits() {
  if (!state.data) return;
  const counts = new Map();
  for (const unit of plannerUnits()) {
    for (const trait of state.data.traits) {
      if (trait.units.some((member) => member.id === unit.id)) {
        const contribution = unit.traitPoints?.[trait.id] ?? 1;
        counts.set(trait.id, (counts.get(trait.id) || 0) + contribution);
      }
    }
  }

  const entries = state.data.traits
    .filter((trait) => counts.has(trait.id))
    .map((trait) => {
      const count = counts.get(trait.id);
      return { trait, count, active: isTraitActive(trait, count) };
    });
  const sortTraits = (left, right) => (
    right.count - left.count || left.trait.name.localeCompare(right.trait.name)
  );
  const active = entries.filter((entry) => entry.active).sort(sortTraits);
  const inactive = entries.filter((entry) => !entry.active).sort(sortTraits);
  renderTraitGroup(activeTraitsElement, active, "Add units to activate traits.");
  renderTraitGroup(inactiveTraitsElement, inactive, "None");
}

function recommendationUnitGroup(label, units, className) {
  const group = htmlElement("div", `recommendation-unit-group ${className}`);
  group.append(htmlElement("span", "recommendation-unit-label", label));
  const unitList = htmlElement("div", "recommendation-unit-list");
  for (const unit of units) {
    const unitElement = htmlElement("span", "recommendation-unit");
    unitElement.title = `${unit.name} (${unit.cost}-cost)`;
    unitElement.append(icon(unit.icon, unit.name, "recommendation-icon"));
    unitList.append(unitElement);
  }
  group.append(unitList);
  return group;
}

function applyRecommendation(suggestion) {
  const dropIndexes = suggestion.drops
    .map((entry) => entry.index)
    .sort((left, right) => right - left);
  for (const index of dropIndexes) {
    if (index >= 0 && index < teamState.slots.length) teamState.slots.splice(index, 1);
  }

  const limit = teamCodeFormat().localSlotLimit;
  for (const unit of suggestion.adds) {
    const uniqueGroup = uniqueGroupForUnit(unit);
    if (plannerHasUniqueGroup(uniqueGroup)) continue;
    const slot = { plannerCode: unit.plannerCode, unitId: unit.id, candidates: [unit] };
    const blankIndex = teamState.slots.findIndex(isEmptySlot);
    const projectedUsage = plannerSlotUsage()
      - (blankIndex >= 0 ? 1 : 0)
      + boardSlotsForUnit(unit);
    if (projectedUsage > limit) continue;
    if (blankIndex >= 0) {
      teamState.slots[blankIndex] = slot;
    } else {
      teamState.slots.push(slot);
    }
  }
  renderTeamSlots();
  updateExportCode();
  const additions = suggestion.adds.map((unit) => unit.name).join(" + ");
  setTeamMessage(
    suggestion.drops.length
      ? `Applied flex: ${additions} for ${suggestion.drops.map((entry) => entry.unit.name).join(" + ")}.`
      : `Added ${additions} to the planner.`,
    "success",
  );
}

function renderRecommendationResults(suggestions, requestId) {
  if (requestId !== recommendationRequestId || !state.data || !recommendationListElement) return;
  recommendationListElement.replaceChildren();
  const hasKnownUnit = teamState.slots.some((slot) => slot.unitId);
  if (!hasKnownUnit && !state.unavailableUnitIds.size) {
    recommendationListElement.append(
      htmlElement("p", "recommendation-empty", "Add or import a unit to see graph-connected suggestions."),
    );
    return;
  }
  if (!suggestions.length) {
    recommendationListElement.append(
      htmlElement("p", "recommendation-empty", "No connected improvement found with the current catalog and availability choices."),
    );
    return;
  }

  for (const suggestion of suggestions) {
    const card = htmlElement("article", "recommendation-card");
    if (suggestion.drops.length) {
      card.append(recommendationUnitGroup("Drop", suggestion.drops.map((entry) => entry.unit), "drop-units"));
    }
    card.append(recommendationUnitGroup("Add", suggestion.adds, "add-units"));
    card.append(htmlElement("p", "recommendation-reason", suggestion.reasons.join(" · ")));
    const applyButton = document.createElement("button");
    applyButton.type = "button";
    applyButton.className = "recommendation-apply";
    applyButton.textContent = "Apply";
    applyButton.addEventListener("click", () => applyRecommendation(suggestion));
    card.append(applyButton);
    recommendationListElement.append(card);
  }
}

function scheduleRecommendationFallback(payload) {
  window.setTimeout(() => {
    if (payload.requestId !== recommendationRequestId || !window.TFTRecommendationEngine) return;
    try {
      const suggestions = window.TFTRecommendationEngine.recommend(
        payload.data,
        payload.slots,
        payload.unavailableUnitIds,
        payload.overrides,
      );
      renderRecommendationResults(suggestions, payload.requestId);
    } catch (error) {
      console.error(error);
      renderRecommendationResults([], payload.requestId);
    }
  }, 0);
}

function getRecommendationWorker() {
  if (recommendationWorker || recommendationWorkerFailed || typeof Worker === "undefined") {
    return recommendationWorker;
  }
  try {
    recommendationWorker = new Worker("recommendations/worker.js");
    recommendationWorker.addEventListener("message", (event) => {
      const { requestId, suggestions, error } = event.data || {};
      if (error) {
        console.error(error);
        recommendationWorkerFailed = true;
        recommendationWorker?.terminate();
        recommendationWorker = null;
        if (latestRecommendationPayload?.requestId === requestId) {
          scheduleRecommendationFallback(latestRecommendationPayload);
        }
        return;
      }
      renderRecommendationResults(suggestions || [], requestId);
    });
    recommendationWorker.addEventListener("error", (event) => {
      console.error(event.error || event.message);
      recommendationWorkerFailed = true;
      recommendationWorker?.terminate();
      recommendationWorker = null;
      if (latestRecommendationPayload) scheduleRecommendationFallback(latestRecommendationPayload);
    }, { once: true });
  } catch (error) {
    console.error(error);
    recommendationWorkerFailed = true;
    recommendationWorker = null;
  }
  return recommendationWorker;
}

function renderRecommendations() {
  if (!state.data || !recommendationListElement) return;
  const requestId = ++recommendationRequestId;
  const payload = {
    requestId,
    data: state.data,
    slots: teamState.slots,
    unavailableUnitIds: [...state.unavailableUnitIds],
    overrides: {
      localSlotLimit: teamCodeFormat().localSlotLimit,
      boardCapacity: plannerSlotUsage(),
    },
  };
  latestRecommendationPayload = payload;
  recommendationListElement.replaceChildren(
    htmlElement("p", "recommendation-empty", "Calculating graph-connected flexes…"),
  );
  const worker = getRecommendationWorker();
  if (worker) {
    worker.postMessage(payload);
  } else {
    scheduleRecommendationFallback(payload);
  }
}

function addUnitToTeam(unit) {
  if (state.unavailableUnitIds.has(unit.id)) {
    setTeamMessage(`${unit.name} is crossed out as unavailable.`, "warning");
    return;
  }
  const uniqueGroup = uniqueGroupForUnit(unit);
  if (plannerHasUniqueGroup(uniqueGroup)) {
    setTeamMessage("That unit group is already represented on the team.", "warning");
    return;
  }
  const limit = teamCodeFormat().localSlotLimit;
  if (plannerSlotUsage() + boardSlotsForUnit(unit) > limit) {
    setTeamMessage(`The local planner is limited to ${limit} slots.`, "warning");
    return;
  }
  teamState.slots.push({
    plannerCode: unit.plannerCode,
    unitId: unit.id,
    candidates: [unit],
  });
  renderTeamSlots();
  updateExportCode();
  setTeamMessage(`${unit.name} added to the team planner.`, "success");
}

function updateExportCode() {
  if (!teamCodeFormat().enabled) {
    exportCodeButton.disabled = true;
    return;
  }
  if (!teamState.slots.length) {
    exportCodeButton.disabled = true;
    return;
  }
  try {
    const code = encodeTeamSlots();
    exportCodeButton.disabled = false;
    const codeSlotCount = teamCodeFormat().slotCount;
    if (teamState.slots.length > codeSlotCount) {
      setTeamMessage(
        `Board has ${teamState.slots.length} units. Team Planner export includes the first ${codeSlotCount}; extra units stay local.`,
        "warning",
      );
    }
  } catch (error) {
    exportCodeButton.disabled = true;
    setTeamMessage(error.message, "error");
  }
}

function addBlankSlot() {
  const limit = teamCodeFormat().localSlotLimit;
  if (plannerSlotUsage() >= limit) return;
  teamState.slots.push({ plannerCode: EMPTY_CODE, unitId: null, candidates: [] });
  renderTeamSlots();
  updateExportCode();
  if (teamState.slots.length <= teamCodeFormat().slotCount) {
    setTeamMessage(`Added blank slot. Choose a unit by clicking its tile.`, "success");
  }
}

function importTeamCode() {
  try {
    teamState.slots = parseTeamCode(teamCodeInput.value);
    renderTeamSlots();
    updateExportCode();
    const recognized = teamState.slots.filter((slot) => slot.unitId).length;
    setTeamMessage(`Imported ${recognized} recognized units. Edit any slot below, then copy the export.`, "success");
  } catch (error) {
    setTeamMessage(error.message, "error");
    exportCodeButton.disabled = true;
  }
}

async function copyExportedCode() {
  const code = encodeTeamSlots();
  try {
    await navigator.clipboard.writeText(code);
    const codeSlotCount = teamCodeFormat().slotCount;
    if (teamState.slots.length > codeSlotCount) {
      setTeamMessage(
        `Exported code copied. The first ${codeSlotCount} units were encoded; extra units remain local.`,
        "warning",
      );
    } else {
      setTeamMessage("Exported code copied to the clipboard.", "success");
    }
  } catch {
    setTeamMessage("Export generated below. Clipboard access was unavailable.", "error");
  }
}

function nodeEvent(node, callback) {
  node.addEventListener("mouseenter", () => focusNode(node.dataset.kind, node.dataset.id));
  node.addEventListener("mouseleave", restorePinnedFocus);
  node.addEventListener("focus", () => focusNode(node.dataset.kind, node.dataset.id));
  node.addEventListener("blur", restorePinnedFocus);
  node.addEventListener("click", callback);
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      callback();
    }
  });
}

function graphData() {
  const query = state.search.trim().toLocaleLowerCase();
  const costMatches = (unit) => state.cost === "all" || String(unit.cost) === state.cost;
  const unitNameMatches = (unit) => !query || unit.name.toLocaleLowerCase().includes(query);
  const traitNameMatches = (trait) => !query || trait.name.toLocaleLowerCase().includes(query);
  const unitMatches = new Set(state.data.units.filter(
    (unit) => costMatches(unit) && unitNameMatches(unit),
  ).map((unit) => unit.id));
  const traitMatches = new Set(state.data.traits.filter(traitNameMatches).map((trait) => trait.id));

  const units = state.data.units.filter((unit) => {
    if (!costMatches(unit)) return false;
    if (!query) return true;
    return unitMatches.has(unit.id) || state.data.traits.some(
      (trait) => traitMatches.has(trait.id) && trait.units.some((member) => member.id === unit.id),
    );
  });
  const visibleUnitIds = new Set(units.map((unit) => unit.id));
  const traits = state.data.traits.map((trait) => ({
    ...trait,
    units: trait.units.filter((unit) => visibleUnitIds.has(unit.id)),
  })).filter((trait) => trait.units.length > 0);
  return { units, traits };
}

function positionMap(items, radius) {
  return new Map(items.map((item, index) => [item.id, pointAt(radius, angleFor(index, items.length))]));
}

function addSvgImage(parent, path, point, size, className) {
  const image = svgElement("image", {
    href: path,
    x: point.x - size / 2,
    y: point.y - size / 2,
    width: size,
    height: size,
    class: className,
    preserveAspectRatio: "xMidYMid slice",
  });
  image.addEventListener("error", () => { image.setAttribute("visibility", "hidden"); });
  parent.append(image);
}

function makeGraph(data) {
  const svg = svgElement("svg", {
    class: "graph",
    viewBox: "-500 -500 1000 1000",
    role: "img",
    "aria-label": "Radial graph connecting TFT units to their traits",
  });
  const background = svgElement("g");
  for (const radius of [185, 300, 420]) {
    background.append(svgElement("circle", { class: "web-ring", cx: 0, cy: 0, r: radius }));
  }
  svg.append(background);

  if (!data.units.length) return svg;
  const unitPositions = positionMap(data.units, 420);
  const traitPositions = positionMap(data.traits, 185);
  const edgeLayer = svgElement("g", { class: "edge-layer" });
  const traitLayer = svgElement("g", { class: "trait-layer" });
  const unitLayer = svgElement("g", { class: "unit-layer" });

  for (const trait of data.traits) {
    const traitPoint = traitPositions.get(trait.id);
    for (const unit of trait.units) {
      const unitPoint = unitPositions.get(unit.id);
      edgeLayer.append(svgElement("line", {
        class: "web-edge",
        "data-trait-id": trait.id,
        "data-unit-id": unit.id,
        x1: traitPoint.x,
        y1: traitPoint.y,
        x2: unitPoint.x,
        y2: unitPoint.y,
      }));
    }
  }

  for (const [index, trait] of data.traits.entries()) {
    const point = traitPositions.get(trait.id);
    const group = svgElement("g", {
      class: "node trait-node",
      tabindex: "0",
      role: "button",
      "data-kind": "trait",
      "data-id": trait.id,
      "aria-label": `${trait.name} trait, ${trait.units.length} units`,
    });
    group.append(svgElement("circle", { class: "node-ring", cx: point.x, cy: point.y, r: 23 }));
    addSvgImage(group, trait.icon, point, 34, "trait-icon");
    const labelPoint = pointAt(218, angleFor(index, data.traits.length));
    group.append(svgElement("text", {
      class: "trait-label",
      x: labelPoint.x,
      y: labelPoint.y,
      "dominant-baseline": "middle",
    }));
    group.lastChild.textContent = trait.name;
    const title = svgElement("title");
    title.textContent = `${trait.name}: ${trait.units.map((unit) => unit.name).join(", ")}`;
    group.append(title);
    nodeEvent(group, () => selectTrait(trait));
    traitLayer.append(group);
  }

  for (const [index, unit] of data.units.entries()) {
    const point = unitPositions.get(unit.id);
    const unavailable = state.unavailableUnitIds.has(unit.id);
    const group = svgElement("g", {
      class: `node unit-node${unavailable ? " is-unavailable" : ""}`,
      tabindex: "0",
      role: "button",
      "data-kind": "unit",
      "data-id": unit.id,
      "aria-label": `${unit.name}, ${unit.cost}-cost${unavailable ? ", unavailable" : ""}`,
    });
    group.append(svgElement("circle", { class: "node-ring", cx: point.x, cy: point.y, r: 25 }));
    group.append(svgElement("circle", { class: `unit-cost-ring cost-${unit.cost}`, cx: point.x, cy: point.y, r: 27 }));
    addSvgImage(group, unit.icon, point, 38, "unit-icon");
    const labelAngle = angleFor(index, data.units.length);
    const labelPoint = pointAt(454, labelAngle);
    group.append(svgElement("text", {
      class: "node-label",
      x: labelPoint.x,
      y: labelPoint.y,
      "text-anchor": labelPoint.x < -5 ? "end" : labelPoint.x > 5 ? "start" : "middle",
      "dominant-baseline": "middle",
    }));
    group.lastChild.textContent = unit.name;
    const title = svgElement("title");
    title.textContent = unavailable
      ? `${unit.name} (${unit.cost}-cost, unavailable)`
      : `${unit.name} (${unit.cost}-cost)`;
    group.append(title);
    if (unavailable) {
      group.append(
        svgElement("line", {
          class: "unavailable-mark",
          x1: point.x - 21,
          y1: point.y - 21,
          x2: point.x + 21,
          y2: point.y + 21,
        }),
        svgElement("line", {
          class: "unavailable-mark",
          x1: point.x + 21,
          y1: point.y - 21,
          x2: point.x - 21,
          y2: point.y + 21,
        }),
      );
    }
    nodeEvent(group, () => selectUnit(unit));
    group.addEventListener("dblclick", (event) => {
      event.preventDefault();
      addUnitToTeam(unit);
    });
    unitLayer.append(group);
  }
  svg.append(edgeLayer, traitLayer, unitLayer);
  return svg;
}

function updateFilters(searchValue, costValue, sourceControl = null) {
  const sourceClass = sourceControl?.className;
  const selectionStart = sourceControl?.selectionStart;
  const selectionEnd = sourceControl?.selectionEnd;
  state.search = searchValue;
  state.cost = costValue;
  if (state.data) render();
  if (sourceClass === "expanded-search") {
    const replacement = web.querySelector(".expanded-search");
    replacement?.focus({ preventScroll: true });
    if (selectionStart !== null && selectionStart !== undefined) {
      replacement?.setSelectionRange(selectionStart, selectionEnd);
    }
  } else if (sourceClass === "expanded-cost") {
    web.querySelector(".expanded-cost")?.focus({ preventScroll: true });
  }
}

function makeGraphControls() {
  const controls = htmlElement("div", "controls graph-controls");
  controls.setAttribute("aria-label", "Trait web filters");
  const searchLabel = document.createElement("label");
  searchLabel.append(htmlElement("span", "", "Search"));
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.className = "expanded-search";
  searchInput.placeholder = "Unit or trait name";
  searchInput.autocomplete = "off";
  searchInput.value = state.search;
  searchInput.addEventListener("input", (event) => {
    updateFilters(event.target.value, state.cost, event.target);
  });
  searchLabel.append(searchInput);

  const costLabel = document.createElement("label");
  costLabel.append(htmlElement("span", "", "Unit cost"));
  const costSelect = document.createElement("select");
  costSelect.className = "expanded-cost";
  for (const [value, label] of [
    ["all", "All costs"],
    ["1", "1-cost"],
    ["2", "2-cost"],
    ["3", "3-cost"],
    ["4", "4-cost"],
    ["5", "5-cost"],
  ]) {
    costSelect.append(new Option(label, value));
  }
  costSelect.value = state.cost;
  costSelect.addEventListener("change", (event) => {
    updateFilters(state.search, event.target.value, event.target);
  });
  costLabel.append(costSelect);

  const summaryElement = htmlElement("div", "catalog-summary");
  summaryElement.id = "summary";
  summaryElement.setAttribute("aria-live", "polite");

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "close-expanded";
  closeButton.textContent = "Close web";
  closeButton.addEventListener("click", () => setWebExpanded(false));
  controls.append(searchLabel, costLabel, summaryElement, closeButton);
  return controls;
}

function setWebExpanded(expanded) {
  graphLayout.classList.toggle("is-expanded", expanded);
  document.body.classList.toggle("web-expanded", expanded);
  if (expanded) {
    requestAnimationFrame(() => web.querySelector(".close-expanded")?.focus());
  } else {
    web.querySelector(".expanded-search")?.focus({ preventScroll: true });
  }
}

function makeInfoHeader(label, title, imagePath, meta) {
  selection.replaceChildren();
  selection.append(htmlElement("p", "eyebrow", label));
  if (imagePath) selection.append(icon(imagePath, `${title} icon`));
  selection.append(htmlElement("h2", "", title));
  selection.append(htmlElement("p", "selected-meta", meta));
  return htmlElement("div", "selected-links");
}

function toggleUnitAvailability(unit) {
  if (state.unavailableUnitIds.has(unit.id)) {
    state.unavailableUnitIds.delete(unit.id);
  } else {
    state.unavailableUnitIds.add(unit.id);
  }
  render();
  renderTeamSlots();
  selectUnit(unit);
  setTeamMessage(
    state.unavailableUnitIds.has(unit.id)
      ? `${unit.name} crossed out as unavailable. Suggestions will avoid it.`
      : `${unit.name} is available again.`,
    "success",
  );
}

function makeAvailabilityButton(unit) {
  const unavailable = state.unavailableUnitIds.has(unit.id);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "availability-toggle";
  button.textContent = unavailable ? "Restore availability" : "Cross out unavailable";
  button.addEventListener("click", () => toggleUnitAvailability(unit));
  return button;
}

function selectUnit(unit) {
  if (state.pinnedUnitId === unit.id) {
    state.pinnedUnitId = null;
    clearFocus();
    return;
  }
  state.selected = { kind: "unit", id: unit.id };
  state.pinnedUnitId = unit.id;
  focusNode("unit", unit.id);
  const links = makeInfoHeader("Unit", unit.name, unit.icon, `${unit.cost}-cost unit`);
  const traits = state.data.traits.filter((trait) => trait.units.some((member) => member.id === unit.id));
  for (const trait of traits) links.append(htmlElement("span", "link-chip", trait.name));
  selection.append(makeAvailabilityButton(unit), links);
}

function selectTrait(trait) {
  state.selected = { kind: "trait", id: trait.id };
  state.pinnedUnitId = null;
  clearFocus();
  const links = makeInfoHeader("Trait", trait.name, trait.icon, `${trait.units.length} connected units`);
  for (const unit of trait.units) links.append(htmlElement("span", "link-chip", unit.name));
  selection.append(links);
}

function focusNode(kind, id) {
  const relatedTraits = new Set();
  const relatedUnits = new Set();
  if (kind === "unit") {
    relatedUnits.add(id);
    for (const trait of state.data.traits) {
      if (trait.units.some((unit) => unit.id === id)) {
        relatedTraits.add(trait.id);
        trait.units.forEach((unit) => relatedUnits.add(unit.id));
      }
    }
  } else {
    relatedTraits.add(id);
    const trait = state.data.traits.find((item) => item.id === id);
    trait?.units.forEach((unit) => relatedUnits.add(unit.id));
  }
  document.querySelectorAll(".node").forEach((node) => {
    const active = node.dataset.kind === "unit"
      ? relatedUnits.has(node.dataset.id)
      : relatedTraits.has(node.dataset.id);
    node.classList.toggle("is-faded", !active);
  });
  document.querySelectorAll(".web-edge").forEach((edge) => {
    const active = relatedTraits.has(edge.dataset.traitId) && relatedUnits.has(edge.dataset.unitId);
    edge.classList.toggle("is-faded", !active);
    edge.classList.toggle("is-active", active);
  });
}

function clearFocus() {
  document.querySelectorAll(".node, .web-edge").forEach((element) => {
    element.classList.remove("is-faded", "is-active");
  });
}

function restorePinnedFocus() {
  const pinnedNode = [...document.querySelectorAll(".unit-node")]
    .find((node) => node.dataset.id === state.pinnedUnitId);
  if (state.pinnedUnitId && pinnedNode) {
    focusNode("unit", state.pinnedUnitId);
  } else {
    clearFocus();
  }
}

function render() {
  const data = graphData();
  web.replaceChildren();
  const controls = makeGraphControls();
  const intro = htmlElement("div", "graph-intro");
  intro.append(
    htmlElement("p", "", "Units orbit the rim. Traits anchor the inner web. Hover to trace a connection; click a unit to keep it highlighted. Click it again or elsewhere to release it."),
    htmlElement("span", "graph-key", `${data.units.length} units · ${data.traits.length} traits`),
  );
  if (!data.units.length) {
    web.append(controls, intro, htmlElement("p", "empty", "No units match those filters."));
    web.querySelector(".catalog-summary").textContent = "0 units · 0 traits";
    clearFocus();
    return;
  }
  web.append(controls, intro, makeGraph(data));
  web.querySelector(".catalog-summary").textContent = `${data.units.length} units · ${data.traits.length} traits · radial web`;
  restorePinnedFocus();
}

async function loadCatalog() {
  try {
    const response = await fetch("data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    const dataset = state.data.dataset || {};
    const format = teamCodeFormat();
    const datasetName = dataset.name || "TFT catalog";
    document.querySelector("#app-title").firstChild.textContent = `${datasetName} `;
    document.title = `${datasetName} Trait Web`;
    teamCodeInput.placeholder = format.enabled ? `${format.prefix}…${format.setId}` : "No team code mapping";
    status.textContent = `${datasetName} · local data`;
    if (!format.enabled) {
      teamCodeInput.disabled = true;
      importCodeButton.disabled = true;
      exportCodeButton.disabled = true;
      setTeamMessage("This catalog has no Team Planner code mapping; local planning remains available.");
    }
    render();
    renderTeamSlots();
  } catch (error) {
    status.textContent = "Catalog unavailable";
    web.replaceChildren(htmlElement("p", "empty", "Could not load data.json. Serve this folder with a local web server."));
    console.error(error);
  }
}

importCodeButton.addEventListener("click", importTeamCode);
addSlotButton.addEventListener("click", addBlankSlot);
teamCodeInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") importTeamCode();
});
exportCodeButton.addEventListener("click", copyExportedCode);
web.addEventListener("dblclick", (event) => {
  if (event.target.closest?.(".unit-node, button, input, select")) return;
  event.preventDefault();
  setWebExpanded(true);
});
document.addEventListener("click", (event) => {
  if (!state.pinnedUnitId || event.target.closest?.(".node")) return;
  state.pinnedUnitId = null;
  clearFocus();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && graphLayout.classList.contains("is-expanded")) {
    event.preventDefault();
    setWebExpanded(false);
  }
});
loadCatalog();
