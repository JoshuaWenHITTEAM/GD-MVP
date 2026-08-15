CC = gcc
CFLAGS = -Wall -O2 -fPIC
TARGET_LIB = libmidware.so
TARGET_SHM_TEST = test_shm_zerocopy
TARGET_IMAGE_TEST = test_image_rebuild
TARGET_NET_TEST = test_net
TARGET_CONTROL_TEST = test_control
TARGET_BOARD_MOCK = control_feedback_board_mock

all: $(TARGET_LIB) $(TARGET_SHM_TEST) $(TARGET_IMAGE_TEST) $(TARGET_NET_TEST) $(TARGET_CONTROL_TEST) $(TARGET_BOARD_MOCK)

$(TARGET_LIB): midware_shm.c midware_shm.h midware_packet.c midware_packet.h midware_image.c midware_image.h midware_net.c midware_net.h midware_control.c midware_control.h midware_camera.c midware_camera.h midware_generated_commands.h
	$(CC) $(CFLAGS) -shared -o $(TARGET_LIB) midware_shm.c midware_packet.c midware_image.c midware_net.c midware_control.c midware_camera.c

$(TARGET_SHM_TEST): test_shm_zerocopy.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_SHM_TEST) test_shm_zerocopy.c -L. -lmidware -Wl,-rpath=.

$(TARGET_IMAGE_TEST): test_image_rebuild.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_IMAGE_TEST) test_image_rebuild.c -L. -lmidware -Wl,-rpath=.

$(TARGET_NET_TEST): test_net.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_NET_TEST) test_net.c -L. -lmidware -Wl,-rpath=.

$(TARGET_CONTROL_TEST): test_control.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_CONTROL_TEST) test_control.c -L. -lmidware -Wl,-rpath=.

$(TARGET_BOARD_MOCK): control_feedback_board_mock.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_BOARD_MOCK) control_feedback_board_mock.c -L. -lmidware -Wl,-rpath=.

test: all
	./$(TARGET_SHM_TEST)
	./$(TARGET_IMAGE_TEST)
	./$(TARGET_NET_TEST)
	./$(TARGET_CONTROL_TEST)

clean:
	rm -f $(TARGET_LIB) $(TARGET_SHM_TEST) $(TARGET_IMAGE_TEST) $(TARGET_NET_TEST) $(TARGET_CONTROL_TEST) $(TARGET_BOARD_MOCK)
