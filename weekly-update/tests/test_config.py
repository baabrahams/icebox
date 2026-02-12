import os
import tempfile
import pytest
import yaml
from config import load_config


def test_load_config_returns_all_fields():
    config_data = {
        "slack": {
            "channels": ["#engineering", "#product"],
            "my_user_id": "U12345678",
        },
        "google": {
            "folder_ids": ["folder_abc123"],
        },
        "lookback_days": 7,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()
        config = load_config(f.name)

    assert config["slack"]["channels"] == ["#engineering", "#product"]
    assert config["slack"]["my_user_id"] == "U12345678"
    assert config["google"]["folder_ids"] == ["folder_abc123"]
    assert config["lookback_days"] == 7
    os.unlink(f.name)


def test_load_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")
