"""A test fixture, not a step anyone installs: the smallest step this library can declare, so its tests can exercise
discovery and the step wrapper without the reference steps (which live in trellis until LS2b, egeria-trellis-steps)."""
from trellis_analytics.manifest import StepManifest


def run(inputs):
    """One result per run: the slug it was asked about, measured as present."""
    return [{"scope": inputs.slug, "state": "measured", "value": {"seen": "yes"}, "summary": "seen"}]


MANIFEST = StepManifest(name="ta_fixture_step", function="ta_fixture_step.run", source="ods", version="0.0.0",
                        description="Test fixture: never installed, registered only inside a test.",
                        resource_types=["database"], annotation_type="ResourceMeasureAnnotation",
                        credential_tier="none", inputs=[])
