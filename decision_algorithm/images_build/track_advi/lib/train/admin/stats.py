class AverageMeter:
    """Minimal compatibility shim for legacy checkpoint metadata."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count if self.count else 0


class StatValue:
    """Minimal compatibility shim for legacy checkpoint metadata."""

    def __init__(self, val=0):
        self.val = val

    def reset(self):
        self.val = 0

    def update(self, val):
        self.val = val
