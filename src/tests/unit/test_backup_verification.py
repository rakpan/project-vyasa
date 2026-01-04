"""
Unit tests for backup verification script.

Tests verify_backups.sh behavior using temporary directories.
No live containers or real backups required.
"""

import os
import subprocess
import tempfile
from pathlib import Path
import pytest


class TestBackupVerification:
    """Tests for backup verification script."""

    @pytest.fixture
    def script_path(self):
        """Path to verify_backups.sh script."""
        project_root = Path(__file__).parent.parent.parent.parent
        script = project_root / "scripts" / "verify_backups.sh"
        assert script.exists(), f"Script not found: {script}"
        return script

    @pytest.fixture
    def temp_backup_dirs(self, tmp_path):
        """Create temporary backup directories."""
        arango_dir = tmp_path / "arangodb"
        qdrant_dir = tmp_path / "qdrant"
        arango_dir.mkdir()
        qdrant_dir.mkdir()
        return {
            "arango": arango_dir,
            "qdrant": qdrant_dir,
        }

    def test_verify_passes_with_valid_arango_tarball(self, script_path, temp_backup_dirs):
        """Test verification passes when ArangoDB backup tarball exists and is valid."""
        # Create a dated tarball
        backup_date = "2024-01-15"
        tarball = temp_backup_dirs["arango"] / f"{backup_date}.tar.gz"
        
        # Create a temporary directory with content for tar
        temp_content = temp_backup_dirs["arango"] / "temp_content"
        temp_content.mkdir()
        (temp_content / "test.json").write_text('{"test": "data"}')
        
        # Create a valid tar.gz
        subprocess.run(["tar", "-czf", str(tarball), "-C", str(temp_content), "."], check=True)
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_content)
        
        # Create a dated Qdrant backup directory with snapshot
        qdrant_backup_dir = temp_backup_dirs["qdrant"] / backup_date
        qdrant_backup_dir.mkdir()
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").parent.mkdir(parents=True)
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").write_bytes(b"fake snapshot data")
        
        # Run verification
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Verification failed: {result.stderr}"
        assert "ArangoDB backup verified" in result.stdout
        assert "Qdrant backup verified" in result.stdout

    def test_verify_passes_with_valid_arango_directory(self, script_path, temp_backup_dirs):
        """Test verification passes when ArangoDB backup directory exists with files."""
        # Create a dated backup directory with dump files
        backup_date = "2024-01-15"
        backup_dir = temp_backup_dirs["arango"] / backup_date
        backup_dir.mkdir()
        (backup_dir / "database.structure.json").write_text('{"collections": []}')
        (backup_dir / "database.data.json").write_text('[]')
        
        # Create Qdrant backup
        qdrant_backup_dir = temp_backup_dirs["qdrant"] / backup_date
        qdrant_backup_dir.mkdir()
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").parent.mkdir(parents=True)
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").write_bytes(b"fake snapshot data")
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "ArangoDB backup verified" in result.stdout

    def test_verify_fails_when_arango_backup_missing(self, script_path, temp_backup_dirs):
        """Test verification fails when ArangoDB backup is missing."""
        # Create Qdrant backup only
        backup_date = "2024-01-15"
        qdrant_backup_dir = temp_backup_dirs["qdrant"] / backup_date
        qdrant_backup_dir.mkdir()
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").parent.mkdir(parents=True)
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").write_bytes(b"fake snapshot data")
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode != 0
        assert "No ArangoDB backup found" in result.stdout or "ArangoDB backup" in result.stderr

    def test_verify_fails_when_qdrant_backup_missing(self, script_path, temp_backup_dirs):
        """Test verification fails when Qdrant backup is missing."""
        # Create ArangoDB backup only
        backup_date = "2024-01-15"
        backup_dir = temp_backup_dirs["arango"] / backup_date
        backup_dir.mkdir()
        (backup_dir / "database.structure.json").write_text('{"collections": []}')
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode != 0
        assert "No Qdrant backup found" in result.stdout or "Qdrant backup" in result.stderr

    def test_verify_fails_when_arango_directory_empty(self, script_path, temp_backup_dirs):
        """Test verification fails when ArangoDB backup directory is empty."""
        backup_date = "2024-01-15"
        backup_dir = temp_backup_dirs["arango"] / backup_date
        backup_dir.mkdir()
        # Directory exists but is empty
        
        # Create Qdrant backup
        qdrant_backup_dir = temp_backup_dirs["qdrant"] / backup_date
        qdrant_backup_dir.mkdir()
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").parent.mkdir(parents=True)
        (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").write_bytes(b"fake snapshot data")
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode != 0
        assert "empty" in result.stdout.lower() or "empty" in result.stderr.lower()

    def test_verify_fails_when_qdrant_no_snapshots(self, script_path, temp_backup_dirs):
        """Test verification fails when Qdrant backup directory has no snapshot files."""
        # Create ArangoDB backup
        backup_date = "2024-01-15"
        backup_dir = temp_backup_dirs["arango"] / backup_date
        backup_dir.mkdir()
        (backup_dir / "database.structure.json").write_text('{"collections": []}')
        
        # Create Qdrant backup directory but no snapshots
        qdrant_backup_dir = temp_backup_dirs["qdrant"] / backup_date
        qdrant_backup_dir.mkdir()
        # Directory exists but no .snapshot files
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode != 0
        assert "no snapshot files" in result.stdout.lower() or "snapshot" in result.stderr.lower()

    def test_verify_finds_latest_backup(self, script_path, temp_backup_dirs):
        """Test verification finds the latest backup when multiple exist."""
        # Create multiple dated backups
        for date in ["2024-01-10", "2024-01-15", "2024-01-20"]:
            backup_dir = temp_backup_dirs["arango"] / date
            backup_dir.mkdir()
            (backup_dir / "database.structure.json").write_text('{"collections": []}')
            
            qdrant_backup_dir = temp_backup_dirs["qdrant"] / date
            qdrant_backup_dir.mkdir()
            (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").parent.mkdir(parents=True)
            (qdrant_backup_dir / "vyasa" / "snapshot.snapshot").write_bytes(b"fake snapshot data")
        
        env = os.environ.copy()
        env["BACKUP_ROOT_ARANGO"] = str(temp_backup_dirs["arango"])
        env["BACKUP_ROOT_QDRANT"] = str(temp_backup_dirs["qdrant"])
        env["LOG_FILE"] = str(temp_backup_dirs["arango"].parent / "test.log")
        
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        # Should verify the latest (2024-01-20)
        assert "2024-01-20" in result.stdout

