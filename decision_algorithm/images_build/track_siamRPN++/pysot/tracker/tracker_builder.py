# Copyright (c) SenseTime. All Rights Reserved.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from pysot.tracker.siamrpn_tracker import SiamRPNTracker


def build_tracker(model):
    return SiamRPNTracker(model)
