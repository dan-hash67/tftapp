/* Run the bounded flex search away from the page's UI thread. */
importScripts("engine.js");

self.addEventListener("message", (event) => {
  const { requestId, data, slots, unavailableUnitIds, overrides } = event.data || {};
  try {
    const suggestions = self.TFTRecommendationEngine.recommend(
      data,
      slots || [],
      unavailableUnitIds || [],
      overrides || {},
    );
    self.postMessage({ requestId, suggestions });
  } catch (error) {
    self.postMessage({
      requestId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});
