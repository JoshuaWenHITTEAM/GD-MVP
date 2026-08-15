class EnvironmentSettings:
    """Minimal compatibility shim for legacy checkpoint metadata."""

    def __init__(self):
        self.workspace_dir = ""
        self.tensorboard_dir = ""
        self.pretrained_networks = ""
        self.lasot_dir = ""
        self.got10k_dir = ""
        self.trackingnet_dir = ""
        self.coco_dir = ""


class Settings:
    """Minimal compatibility shim for legacy checkpoint metadata."""

    def __init__(self):
        self.env = EnvironmentSettings()


def env_settings():
    return EnvironmentSettings()
