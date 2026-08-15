#ifndef MIDWARE_CAMERA_H
#define MIDWARE_CAMERA_H

#include <stdint.h>

#include "midware_control.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND (-40)
#define MIDWARE_CAMERA_ERR_INVALID_PARAMS (-41)
#define MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL (-42)

int midware_camera_command_to_frame(const midware_control_command_t* command,
                                    uint8_t* out_frame,
                                    uint32_t out_capacity,
                                    uint32_t* out_len);

#ifdef __cplusplus
}
#endif

#endif
