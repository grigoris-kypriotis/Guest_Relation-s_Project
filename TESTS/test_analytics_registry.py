"""
Test Analytics Registry
-----------------------
Unit tests for MODULES.analytics_registry:
- Assert exactly 13 registry entries
- Assert unique keys across all entries
- Assert every render_attr exists as a callable on TraceAnalyticsPlotEngine
- Assert get_spec("missing") raises KeyError
- Assert the removed keys ("departmental_resolution_latency", "trace_status_funnel")
  are absent from compute_visual_analytics_data output
"""

import unittest
from MODULES.analytics_registry import CHART_REGISTRY, ChartSpec, get_spec
from MODULES.plot_viewer import TraceAnalyticsPlotEngine
from MODULES.trace_analytics import compute_visual_analytics_data


class TestAnalyticsRegistry(unittest.TestCase):
    def test_registry_count_and_types(self):
        """Assert exactly 12 registry entries and each is an instance of ChartSpec."""
        self.assertEqual(len(CHART_REGISTRY), 12, "Registry must contain exactly 12 operational chart specifications.")
        for spec in CHART_REGISTRY:
            self.assertIsInstance(spec, ChartSpec)
            self.assertTrue(isinstance(spec.lenses, frozenset))
            self.assertGreater(len(spec.lenses), 0)

    def test_unique_keys(self):
        """Assert unique keys across all chart specifications."""
        keys = [spec.key for spec in CHART_REGISTRY]
        self.assertEqual(len(keys), len(set(keys)), "Registry chart keys must be strictly unique.")

    def test_render_attr_exists_on_plot_engine(self):
        """Assert every render_attr exists on TraceAnalyticsPlotEngine and is callable."""
        for spec in CHART_REGISTRY:
            self.assertTrue(
                hasattr(TraceAnalyticsPlotEngine, spec.render_attr),
                f"TraceAnalyticsPlotEngine is missing attribute: {spec.render_attr} for key {spec.key}"
            )
            self.assertTrue(
                callable(getattr(TraceAnalyticsPlotEngine, spec.render_attr)),
                f"TraceAnalyticsPlotEngine attribute {spec.render_attr} must be callable"
            )

    def test_get_spec_lookup_and_missing_key_error(self):
        """Assert get_spec retrieves correct spec and raises KeyError when missing."""
        spec = get_spec("tour_operator_mix")
        self.assertEqual(spec.key, "tour_operator_mix")
        self.assertEqual(spec.render_attr, "render_tour_operator_mix")

        with self.assertRaises(KeyError):
            get_spec("missing")

        with self.assertRaises(KeyError):
            get_spec("departmental_resolution_latency")

        with self.assertRaises(KeyError):
            get_spec("trace_status_funnel")

        with self.assertRaises(KeyError):
            get_spec("checkout_proximity_risk_queue")

    def test_removed_keys_absent_from_compute_visual_analytics_data(self):
        """Assert removed keys are absent from compute_visual_analytics_data output."""
        metrics_empty = compute_visual_analytics_data([])
        self.assertNotIn("departmental_resolution_latency", metrics_empty)
        self.assertNotIn("trace_status_funnel", metrics_empty)
        self.assertNotIn("checkout_proximity_risk_queue", metrics_empty)

        mock_traces = [
            {"room_number": "1101", "category": "Trace", "notes": "AC noisy", "departure": "2026-09-22"},
            {"room_number": "1102", "category": "Room Change Request", "notes": "Smell", "departure": "2026-09-23"},
        ]
        metrics_with_data = compute_visual_analytics_data(mock_traces)
        self.assertNotIn("departmental_resolution_latency", metrics_with_data)
        self.assertNotIn("trace_status_funnel", metrics_with_data)
        self.assertNotIn("checkout_proximity_risk_queue", metrics_with_data)


if __name__ == "__main__":
    unittest.main()
