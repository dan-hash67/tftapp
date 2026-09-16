/* Generic, data-driven flex suggestions for the static prototype. */
(function exposeRecommendationEngine(global) {
  const DEFAULT_WEIGHTS = {
    cost: 1.5,
    progress: 2,
    breakpoint: 8,
    synergy: 2,
    focus: 1.5,
    lostBreakpoint: 14,
    orphan: 4,
    drop: 1.5,
    dropCost: 0.5,
    role: 8,
    roleGap: 5,
  };

  const DEFAULT_OPTIONS = {
    maxSuggestions: 5,
    maxBundleSize: 3,
    maxDrops: 4,
    candidatePoolSize: 12,
    weights: DEFAULT_WEIGHTS,
  };

  function positiveInteger(value, fallback) {
    return Number.isInteger(value) && value > 0 ? value : fallback;
  }

  function recommendationOptions(data, overrides = {}) {
    const configured = data.dataset?.recommendation || {};
    const configuredWeights = configured.weights || {};
    return {
      maxSuggestions: positiveInteger(
        overrides.maxSuggestions ?? configured.max_suggestions,
        DEFAULT_OPTIONS.maxSuggestions,
      ),
      maxBundleSize: positiveInteger(
        overrides.maxBundleSize ?? configured.max_bundle_size,
        DEFAULT_OPTIONS.maxBundleSize,
      ),
      maxDrops: positiveInteger(
        overrides.maxDrops ?? configured.max_drops,
        DEFAULT_OPTIONS.maxDrops,
      ),
      candidatePoolSize: positiveInteger(
        overrides.candidatePoolSize ?? configured.candidate_pool_size,
        DEFAULT_OPTIONS.candidatePoolSize,
      ),
      localSlotLimit: positiveInteger(
        overrides.localSlotLimit ?? data.dataset?.local_board_slot_limit,
        15,
      ),
      boardCapacity: positiveInteger(overrides.boardCapacity, 0),
      weights: {
        ...DEFAULT_WEIGHTS,
        ...configuredWeights,
        ...(overrides.weights || {}),
      },
    };
  }

  function buildModel(data) {
    const units = data.units || [];
    const traits = data.traits || [];
    const unitById = new Map(units.map((unit) => [unit.id, unit]));
    const traitById = new Map(traits.map((trait) => [trait.id, trait]));
    const traitIdsByUnit = new Map(units.map((unit) => [unit.id, new Set()]));
    const pointsByUnit = new Map(
      units.map((unit) => [unit.id, new Map(Object.entries(unit.traitPoints || {}))]),
    );

    for (const unit of units) {
      for (const traitId of Object.keys(unit.traitPoints || {})) {
        if (traitById.has(traitId)) traitIdsByUnit.get(unit.id).add(traitId);
      }
    }
    for (const trait of traits) {
      for (const member of trait.units || []) {
        if (!unitById.has(member.id)) continue;
        traitIdsByUnit.get(member.id).add(trait.id);
        if (!pointsByUnit.get(member.id).has(trait.id)) {
          pointsByUnit.get(member.id).set(trait.id, 1);
        }
      }
    }

    return { units, traits, unitById, traitById, traitIdsByUnit, pointsByUnit };
  }

  function thresholdsFor(trait) {
    const thresholds = Array.isArray(trait.activationThresholds)
      ? trait.activationThresholds.filter((value) => Number.isInteger(value) && value > 0)
      : [];
    return thresholds.length ? thresholds : [2];
  }

  function boardSlotsFor(unit) {
    return Number.isInteger(unit?.boardSlots) && unit.boardSlots > 0 ? unit.boardSlots : 1;
  }

  function uniqueGroupFor(unit) {
    return typeof unit?.uniqueGroup === "string" && unit.uniqueGroup ? unit.uniqueGroup : null;
  }

  function roleTagsFor(unit) {
    return new Set(
      (Array.isArray(unit?.roleTags) ? unit.roleTags : [])
        .filter((tag) => typeof tag === "string" && tag.trim())
        .map((tag) => tag.trim().toLocaleLowerCase()),
    );
  }

  function roleTargets(boardSize, knownRoles) {
    const targets = {
      frontline: boardSize < 5 ? 1 : boardSize < 9 ? 2 : 3,
      damage: 1,
      carry: 1,
      crowd_control: boardSize >= 5 ? 1 : 0,
      support: boardSize >= 6 ? 1 : 0,
    };
    return new Map(
      Object.entries(targets).filter(([role, target]) => target > 0 && knownRoles.has(role)),
    );
  }

  function roleProfile(unitIds, model) {
    const uniqueIds = [...new Set(unitIds)].filter((id) => model.unitById.has(id));
    const knownRoles = new Set(
      model.units.flatMap((unit) => [...roleTagsFor(unit)]),
    );
    const counts = new Map();
    for (const unitId of uniqueIds) {
      for (const role of roleTagsFor(model.unitById.get(unitId))) {
        counts.set(role, (counts.get(role) || 0) + 1);
      }
    }
    const targets = roleTargets(uniqueIds.length, knownRoles);
    let score = 0;
    const gaps = new Set();
    for (const [role, target] of targets) {
      score += Math.min(counts.get(role) || 0, target) / target;
      if ((counts.get(role) || 0) < target) gaps.add(role);
    }
    return { counts, score, gaps };
  }

  function breakpointProgress(trait, count) {
    const thresholds = thresholdsFor(trait);
    const reached = thresholds.filter((threshold) => count >= threshold).length;
    const next = thresholds.find((threshold) => threshold > count);
    return reached + (next ? count / next : 0);
  }

  function summarize(unitIds, model) {
    const uniqueIds = [...new Set(unitIds)].filter((id) => model.unitById.has(id));
    const counts = new Map();
    for (const unitId of uniqueIds) {
      for (const traitId of model.traitIdsByUnit.get(unitId) || []) {
        const rawPoints = model.pointsByUnit.get(unitId)?.get(traitId);
        const points = Number.isFinite(Number(rawPoints)) && Number(rawPoints) > 0
          ? Number(rawPoints)
          : 1;
        counts.set(traitId, (counts.get(traitId) || 0) + points);
      }
    }

    const presentTraitIds = new Set();
    const activeTraitIds = new Set();
    let progress = 0;
    for (const trait of model.traits) {
      const count = counts.get(trait.id) || 0;
      if (count > 0) presentTraitIds.add(trait.id);
      if (thresholdsFor(trait).some((threshold) => count >= threshold)) {
        activeTraitIds.add(trait.id);
      }
      progress += breakpointProgress(trait, count);
    }
    const role = roleProfile(uniqueIds, model);
    return {
      uniqueIds,
      counts,
      presentTraitIds,
      activeTraitIds,
      progress,
      roleCounts: role.counts,
      roleScore: role.score,
      roleGaps: role.gaps,
    };
  }

  function traitPoints(unit, traitId, model) {
    const rawPoints = model.pointsByUnit.get(unit.id)?.get(traitId);
    return Number.isFinite(Number(rawPoints)) && Number(rawPoints) > 0
      ? Number(rawPoints)
      : 1;
  }

  function combinations(items, size) {
    if (size === 0) return [[]];
    if (size > items.length) return [];
    const result = [];
    function visit(start, chosen) {
      if (chosen.length === size) {
        result.push([...chosen]);
        return;
      }
      const remaining = size - chosen.length;
      for (let index = start; index <= items.length - remaining; index += 1) {
        chosen.push(items[index]);
        visit(index + 1, chosen);
        chosen.pop();
      }
    }
    visit(0, []);
    return result;
  }

  function setDifference(left, right) {
    return [...left].filter((value) => !right.has(value));
  }

  function candidatePool(
    model,
    base,
    focusTraitIds,
    unavailableIds,
    occupiedUniqueGroups,
    options,
  ) {
    const baseTraitIds = base.presentTraitIds;
    const baseUniqueGroups = new Set(
      base.uniqueIds
        .map((unitId) => uniqueGroupFor(model.unitById.get(unitId)))
        .filter(Boolean),
    );
    for (const group of occupiedUniqueGroups) baseUniqueGroups.add(group);
    if (!baseTraitIds.size && !focusTraitIds.size) return [];

    return model.units
      .filter((unit) => (
        !unavailableIds.has(unit.id)
        && !base.uniqueIds.includes(unit.id)
        && !(uniqueGroupFor(unit) && baseUniqueGroups.has(uniqueGroupFor(unit)))
      ))
      .map((unit) => {
        const connectedTraitIds = [...(model.traitIdsByUnit.get(unit.id) || [])]
          .filter((traitId) => baseTraitIds.has(traitId) || focusTraitIds.has(traitId));
        const sharedPoints = connectedTraitIds
          .filter((traitId) => baseTraitIds.has(traitId))
          .reduce((total, traitId) => total + traitPoints(unit, traitId, model), 0);
        const focusPoints = connectedTraitIds
          .filter((traitId) => focusTraitIds.has(traitId))
          .reduce((total, traitId) => total + traitPoints(unit, traitId, model), 0);
        if (!connectedTraitIds.length) return null;
        const roleNeed = [...roleTagsFor(unit)].filter((role) => base.roleGaps.has(role)).length;
        return {
          unit,
          connectionScore: sharedPoints * 3
            + focusPoints * 2
            + connectedTraitIds.length
            + roleNeed * 4,
        };
      })
      .filter(Boolean)
      .sort((left, right) => (
        right.connectionScore - left.connectionScore
        || left.unit.cost - right.unit.cost
        || left.unit.name.localeCompare(right.unit.name)
      ))
      .slice(0, options.candidatePoolSize)
      .map((entry) => entry.unit);
  }

  function respectsUniqueGroups(addedUnits, base, model, occupiedUniqueGroups) {
    const groups = new Set(
      base.uniqueIds
        .map((unitId) => uniqueGroupFor(model.unitById.get(unitId)))
        .filter(Boolean),
    );
    for (const group of occupiedUniqueGroups) groups.add(group);
    for (const unit of addedUnits) {
      const group = uniqueGroupFor(unit);
      if (!group) continue;
      if (groups.has(group)) return false;
      groups.add(group);
    }
    return true;
  }

  function evaluateAction({
    model,
    base,
    baseSlotUnits,
    droppedSlots,
    addedUnits,
    unavailableIds,
    focusTraitIds,
    options,
  }) {
    const keptSlotUnits = baseSlotUnits
      .filter((entry) => !droppedSlots.some((dropped) => dropped.index === entry.index))
      .filter((entry) => !unavailableIds.has(entry.unit.id));
    const resultUnitIds = keptSlotUnits.map((entry) => entry.unit.id).concat(
      addedUnits.map((unit) => unit.id),
    );
    const result = summarize(resultUnitIds, model);
    const addedTraitIds = new Set();
    let sharedPoints = 0;
    let focusPoints = 0;
    let orphanPoints = 0;
    for (const unit of addedUnits) {
      for (const traitId of model.traitIdsByUnit.get(unit.id) || []) {
        const points = traitPoints(unit, traitId, model);
        if (base.presentTraitIds.has(traitId)) {
          sharedPoints += points;
          addedTraitIds.add(traitId);
        } else if (focusTraitIds.has(traitId)) {
          focusPoints += points;
          addedTraitIds.add(traitId);
        } else {
          orphanPoints += points;
        }
      }
    }

    const addedCost = addedUnits.reduce((total, unit) => total + unit.cost, 0);
    const droppedAvailable = droppedSlots.filter((entry) => !unavailableIds.has(entry.unit.id));
    const droppedCost = droppedAvailable.reduce((total, entry) => total + entry.unit.cost, 0);
    const costDelta = addedCost - droppedCost;
    const newActiveTraitIds = new Set(setDifference(result.activeTraitIds, base.activeTraitIds));
    const lostActiveTraitIds = new Set(setDifference(base.activeTraitIds, result.activeTraitIds));
    const progressDelta = result.progress - base.progress;
    const roleDelta = result.roleScore - base.roleScore;
    const roleGapDelta = base.roleGaps.size - result.roleGaps.size;
    const weights = options.weights;
    const score = (
      costDelta * weights.cost
      + progressDelta * weights.progress
      + newActiveTraitIds.size * weights.breakpoint
      + sharedPoints * weights.synergy
      + focusPoints * weights.focus
      - lostActiveTraitIds.size * weights.lostBreakpoint
      - orphanPoints * weights.orphan
      - droppedSlots.length * weights.drop
      - droppedCost * weights.dropCost
      + roleDelta * weights.role
      + roleGapDelta * weights.roleGap
    );

    const traitNames = (ids) => [...ids]
      .map((id) => model.traitById.get(id)?.name)
      .filter(Boolean);
    const addedNames = addedTraitIds.size ? traitNames(addedTraitIds).slice(0, 3) : [];
    const reasons = [];
    if (costDelta > 0) reasons.push(`+${costDelta} unit-cost value`);
    if (newActiveTraitIds.size) {
      reasons.push(`activates ${traitNames(newActiveTraitIds).slice(0, 2).join(" + ")}`);
    } else if (progressDelta > 0.05 && addedNames.length) {
      reasons.push(`advances ${addedNames.join(" + ")}`);
    }
    if (sharedPoints > 0) reasons.push(`shares ${sharedPoints} existing trait point${sharedPoints === 1 ? "" : "s"}`);
    if (focusPoints > 0 && focusTraitIds.size) reasons.push("matches the crossed-out unit's trait neighborhood");
    const improvedRoles = setDifference(base.roleGaps, result.roleGaps);
    if (improvedRoles.length) reasons.push(`covers ${improvedRoles.slice(0, 2).join(" + ")}`);
    if (!reasons.length) reasons.push("best available connected improvement");

    return {
      score,
      adds: addedUnits,
      drops: droppedSlots,
      reasons,
      metrics: {
        costDelta,
        progressDelta,
        newActiveTraitIds: [...newActiveTraitIds],
        lostActiveTraitIds: [...lostActiveTraitIds],
        sharedPoints,
        orphanPoints,
        roleDelta,
        roleGapDelta,
      },
      signature: `${droppedSlots.map((entry) => entry.unit.id).join(",")}=>${addedUnits.map((unit) => unit.id).join(",")}`,
    };
  }

  function recommend(data, slots = [], unavailableUnitIds = [], overrides = {}) {
    const options = recommendationOptions(data, overrides);
    const model = buildModel(data);
    const unavailableIds = new Set(unavailableUnitIds);
    const allSlots = slots.map((slot, index) => ({
      index,
      unit: slot.unitId ? model.unitById.get(slot.unitId) : null,
      candidates: slot.candidates || [],
    })).filter((entry) => entry.unit);
    const occupiedUniqueGroups = new Set(
      slots
        .filter((slot) => !slot.unitId)
        .flatMap((slot) => slot.candidates || [])
        .map(uniqueGroupFor)
        .filter(Boolean),
    );
    const blankSlots = slots.filter((slot) => (
      slot.plannerCode === 0 && !slot.unitId && !(slot.candidates || []).length
    )).length;
    const currentSlotUsage = slots.reduce((total, slot) => {
      const unit = slot.unitId ? model.unitById.get(slot.unitId) : null;
      return total + boardSlotsFor(unit);
    }, 0);
    const boardCapacity = options.boardCapacity || currentSlotUsage;
    const baseSlotUnits = allSlots;
    const baseUnitIds = allSlots
      .filter((entry) => !unavailableIds.has(entry.unit.id))
      .map((entry) => entry.unit.id);
    const base = summarize(baseUnitIds, model);
    const focusTraitIds = new Set();
    for (const unitId of unavailableIds) {
      for (const traitId of model.traitIdsByUnit.get(unitId) || []) focusTraitIds.add(traitId);
    }
    const candidates = candidatePool(
      model,
      base,
      focusTraitIds,
      unavailableIds,
      occupiedUniqueGroups,
      options,
    );
    if (!candidates.length) return [];

    const unavailableOnBoard = allSlots.filter((entry) => unavailableIds.has(entry.unit.id));
    const requiredUnavailableIndexes = new Set(unavailableOnBoard.map((entry) => entry.index));
    const suggestions = [];
    const maxAdditions = Math.min(options.maxBundleSize, candidates.length);
    for (let addCount = 1; addCount <= maxAdditions; addCount += 1) {
      for (const addedUnits of combinations(candidates, addCount)) {
        if (!respectsUniqueGroups(addedUnits, base, model, occupiedUniqueGroups)) continue;
        const addedSlotUsage = addedUnits.reduce((total, unit) => total + boardSlotsFor(unit), 0);
        const blankReplacements = Math.min(blankSlots, addCount);
        const requiredDropUsage = Math.max(
          0,
          currentSlotUsage + addedSlotUsage - blankReplacements - boardCapacity,
        );
        const maxUsefulDrops = Math.min(options.maxDrops, allSlots.length);
        for (let dropCount = 0; dropCount <= maxUsefulDrops; dropCount += 1) {
          const validDrops = [];
          for (const droppedSlots of combinations(allSlots, dropCount)) {
            const droppedIndexes = new Set(droppedSlots.map((entry) => entry.index));
            if (![...requiredUnavailableIndexes].every((index) => droppedIndexes.has(index))) continue;
            const droppedSlotUsage = droppedSlots.reduce(
              (total, entry) => total + boardSlotsFor(entry.unit),
              0,
            );
            if (droppedSlotUsage < requiredDropUsage) continue;
            const finalSlotUsage = currentSlotUsage
              - droppedSlotUsage
              - blankReplacements
              + addedSlotUsage;
            if (finalSlotUsage > boardCapacity || finalSlotUsage > options.localSlotLimit) continue;
            validDrops.push(droppedSlots);
          }
          if (validDrops.length) {
            for (const droppedSlots of validDrops) suggestions.push(evaluateAction({
              model,
              base,
              baseSlotUnits,
              droppedSlots,
              addedUnits,
              unavailableIds,
              focusTraitIds,
              options,
            }));
            break;
          }
        }
      }
    }

    const unique = [];
    const signatures = new Set();
    for (const suggestion of suggestions.sort((left, right) => right.score - left.score)) {
      if (signatures.has(suggestion.signature)) continue;
      signatures.add(suggestion.signature);
      unique.push(suggestion);
      if (unique.length >= options.maxSuggestions) break;
    }
    return unique;
  }

  const api = { recommend };
  global.TFTRecommendationEngine = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window !== "undefined" ? window : globalThis));
