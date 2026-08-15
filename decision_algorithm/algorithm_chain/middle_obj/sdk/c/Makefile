CC = gcc
CFLAGS = -Wall -O2 -fPIC
TARGET_LIB = libmidware.so
TARGET_SHM_TEST = test_shm_zerocopy
TARGET_IMAGE_TEST = test_image_rebuild

all: $(TARGET_LIB) $(TARGET_SHM_TEST) $(TARGET_IMAGE_TEST)

$(TARGET_LIB): midware_shm.c midware_shm.h midware_packet.c midware_packet.h midware_image.c midware_image.h
	$(CC) $(CFLAGS) -shared -o $(TARGET_LIB) midware_shm.c midware_packet.c midware_image.c

$(TARGET_SHM_TEST): test_shm_zerocopy.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_SHM_TEST) test_shm_zerocopy.c -L. -lmidware -Wl,-rpath=.

$(TARGET_IMAGE_TEST): test_image_rebuild.c $(TARGET_LIB)
	$(CC) $(CFLAGS) -o $(TARGET_IMAGE_TEST) test_image_rebuild.c -L. -lmidware -Wl,-rpath=.

test: all
	./$(TARGET_SHM_TEST)
	./$(TARGET_IMAGE_TEST)

clean:
	rm -f $(TARGET_LIB) $(TARGET_SHM_TEST) $(TARGET_IMAGE_TEST)
