"""TR-114: the seam names ONE read for Resource Explorer's own file reads, and its shape is pinned.

fs_activity must tell a person's read of a file from Resource Explorer's own (it opens files to hash, profile, read
narrative files and match data classes). The step runs of the last three are in RE's registry; the seam says how a step
asks for their times. The implementation is RE's (`trellis_analytics_re.ods.OdsReader`).
"""
import inspect

from trellis_analytics.readers import ODS_READS, OdsRead


def test_the_own_reads_read_is_on_the_seam():
    assert "filesystem_own_reads" in ODS_READS


def test_its_shape_is_slug_and_since_only():
    sig = inspect.signature(OdsRead.filesystem_own_reads)
    assert list(sig.parameters) == ["self", "slug", "since"]
    assert sig.parameters["since"].default == ""          # "" = every run, so no earlier walk is not "no runs"


def test_the_file_system_reads_are_exactly_these():
    assert [n for n in ODS_READS if n.startswith("filesystem_")] == [
        "filesystem_walk_runs", "filesystem_walk_files", "filesystem_walk_not_walked", "filesystem_hash_matches",
        "filesystem_own_reads"]
