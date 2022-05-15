//++====================================================================================++//
//||     Only the 5V and GND pins are used in this script, add what you want to it      ||//
//++====================================================================================++//

// Reference from StackOverflow
// https://stackoverflow.com/questions/57823528/how-do-i-transfer-an-image-taken-by-esp32-cam-over-sockets
// Remember to replace options in line 33-36 to adopt your own setup

#include "esp_camera.h"
#include "Arduino.h"
#include "WiFi.h"

// Pin definition for CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

// Variables
camera_fb_t *fb = NULL;
const char *ssid = "your_WiFi_name_here";
const char *password = "WiFi_password_here";
const char *serverIP = "your_server_ip_here";
const int *serverPort = 80;

void setup()
{
    Serial.begin(115200);

    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi.");
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(1000);
        Serial.print(".");
    }

    Serial.println("\nConnected!");
    Serial.println(WiFi.localIP());

    // These are camera parameters, DO NOT CHANGE
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;

    if (psramFound())
    {
        config.frame_size = FRAMESIZE_UXGA;
        config.jpeg_quality = 10;
        config.fb_count = 2;
    }
    else
    {
        config.frame_size = FRAMESIZE_SVGA;
        config.jpeg_quality = 12;
        config.fb_count = 1;
    }

    // Init Camera
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed with error 0x%x", err);
        return;
    }
}

//++======================================================++//
//||                    Main Program Loop                 ||//
//++======================================================++//
void loop()
{
    // Setup WiFi client
    WiFiClient client;
    IPAddress ip;
    ip.fromString(serverIP);

    // Try connect to server host
    if (!client.connect(ip, serverPort))
    {
        Serial.println("Host not online");
        delay(1000);
        return;
    }

    Serial.println("Connected to server successful!");

    // capture camera frame
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        Serial.println("Camera capture failed");
        return;
    }
    else
    {
        Serial.println("Camera capture successful!");
    }
    const char *data = (const char *)fb->buf;
    // Image metadata
    Serial.print("Size of image:");
    Serial.println(fb->len);
    Serial.print("Shape->width:");
    Serial.print(fb->width);
    Serial.print("height:");
    Serial.println(fb->height);
    // // Here I commented out the following lines so that ESP32-CAM just send the image data
    // // so we don't have to worry about spliting up receiving data at server side
    // client.print("Shape->width:");
    // client.print(fb->width);
    // client.print("height:");
    // client.println(fb->height);
    // // TODO: send more info to server, needs cooperation with Python script
    Serial.println("Sending data to server...");
    client.write(data, fb->len);
    Serial.println("Done!");
    // // Give the server a chance to receive the information
    delay(3000);
    esp_camera_fb_return(fb);
    Serial.println("Disconnecting...");
    client.stop();
    // Here I didn't do in-depth test to these time gaps
    // so the 5s may be longer than what you need
    // TODO: adjust the time gap between captures
    // TODO: or rewrite the mechanism on serverside to distinguish two captures in sequence
    delay(2000);
}