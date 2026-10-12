from importlib.metadata import version

from packaging.version import Version

import vto


def test_package_importable():
    assert vto.__version__


def test_version_is_pep440_and_matches_metadata():
    assert str(Version(vto.__version__)) == vto.__version__
    assert version("vto") == vto.__version__
