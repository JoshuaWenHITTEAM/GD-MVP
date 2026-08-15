# Mixed Tracking Sequences

This directory is a unified sequence set built from:

- `Anti-UAV-Tracking-V0`
- `VOTLT-2022/train` non-UAV sequences

All entries here are symlinks, not copied image files.

## Naming

- `anti_uav_videoXX` -> Anti-UAV sequence directory
- `votlt_NAME` -> `VOTLT-2022/train/NAME/color`

## Excluded VOTLT sequences

To keep the VOTLT subset focused on non-UAV content, these sequences were excluded:

- `airplane`
- `drone`
- `flyboard`
- `helicopter`
- `parachute`
- `parrot`
- `seagull`

## Counts

- Anti-UAV sequences: `20`
- VOTLT non-UAV sequences: `43`
- Total mixed sequences: `63`
